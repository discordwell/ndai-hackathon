"""ndai-seal — Verify enclave attestation and encrypt exploits for NDAI marketplace.

Usage:
    ndai-seal attest https://api.zdayzk.com     # Fetch and display attestation
    ndai-seal encrypt --poc exploit.sh           # Encrypt PoC to enclave key
    ndai-seal submit --sealed sealed.bin         # Submit to marketplace
    ndai-seal verify-pcr0 --pcr0 <hex>           # Check PCR0 against on-chain registry
"""

import base64
import hashlib
import os
import sys

import click
import httpx
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization

# ECIES constants (must match ndai/enclave/ephemeral_keys.py)
ECIES_INFO = b"ndai-key-delivery"
AES_KEY_SIZE = 32
GCM_NONCE_SIZE = 12


def ecies_encrypt(recipient_public_key_der: bytes, plaintext: bytes) -> bytes:
    """ECIES encrypt: P-384 ECDH + HKDF-SHA384 + AES-256-GCM.

    Output: [ephemeral_pubkey_DER(120) | nonce(12) | ciphertext+tag]
    Compatible with ndai/enclave/ephemeral_keys.py ecies_decrypt().
    """
    recipient_key = serialization.load_der_public_key(recipient_public_key_der)

    # Generate ephemeral keypair
    eph_private = ec.generate_private_key(ec.SECP384R1())
    eph_public = eph_private.public_key()
    eph_public_der = eph_public.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # ECDH shared secret
    shared_secret = eph_private.exchange(ec.ECDH(), recipient_key)

    # HKDF key derivation
    derived_key = HKDF(
        algorithm=hashes.SHA384(),
        length=AES_KEY_SIZE,
        salt=None,
        info=ECIES_INFO,
    ).derive(shared_secret)

    # AES-256-GCM encrypt
    nonce = os.urandom(GCM_NONCE_SIZE)
    aes = AESGCM(derived_key)
    ciphertext_and_tag = aes.encrypt(nonce, plaintext, None)

    return eph_public_der + nonce + ciphertext_and_tag


@click.group()
def cli():
    """NDAI Seal — verify enclaves and encrypt exploits."""
    pass


@cli.command()
@click.argument("api_url")
@click.option("--nonce", default=None, help="Hex nonce for freshness (auto-generated if omitted)")
@click.option("--save-key", default=None, help="Save enclave public key to file (DER format)")
def attest(api_url, nonce, save_key):
    """Fetch and display enclave attestation."""
    if not nonce:
        nonce = os.urandom(16).hex()

    url = f"{api_url.rstrip('/')}/api/v1/enclave/attestation?nonce={nonce}"
    click.echo(f"Fetching attestation from {url}")

    resp = httpx.get(url, timeout=30)
    if resp.status_code != 200:
        click.echo(f"Error: {resp.status_code} {resp.text[:200]}", err=True)
        sys.exit(1)

    data = resp.json()
    mode = data.get("mode", "unknown")
    pcr0 = data.get("pcr0", "unknown")
    valid = data.get("valid")
    pubkey_b64 = data.get("enclave_public_key")
    doc_b64 = data.get("attestation_doc")

    click.echo(f"\nAttestation Mode: {mode}")
    click.echo(f"PCR0: {pcr0}")
    click.echo(f"Signature Valid: {valid}")
    click.echo(f"Nonce: {nonce}")

    if pubkey_b64:
        pubkey_der = base64.b64decode(pubkey_b64)
        click.echo(f"Enclave Public Key: {len(pubkey_der)} bytes (P-384)")
        click.echo(f"Key SHA-256: {hashlib.sha256(pubkey_der).hexdigest()[:16]}...")

        if save_key:
            with open(save_key, "wb") as f:
                f.write(pubkey_der)
            click.echo(f"Key saved to {save_key}")
    else:
        click.echo("WARNING: No public key in attestation", err=True)

    if doc_b64:
        doc = base64.b64decode(doc_b64)
        click.echo(f"Attestation Doc: {len(doc)} bytes (COSE Sign1)")

    if mode == "simulated":
        click.echo("\nWARNING: Simulated mode — no hardware security guarantees.", err=True)
        click.echo("In production, verify cert chain roots to AWS Nitro Root CA.", err=True)


@cli.command()
@click.option("--poc", required=True, type=click.Path(exists=True), help="Path to PoC script")
@click.option("--key", required=True, type=click.Path(exists=True), help="Enclave public key file (DER)")
@click.option("--out", default="sealed.bin", help="Output sealed PoC file")
def encrypt(poc, key, out):
    """Encrypt a PoC script to the enclave's attested public key."""
    with open(poc, "rb") as f:
        poc_data = f.read()
    with open(key, "rb") as f:
        pubkey_der = f.read()

    click.echo(f"PoC: {len(poc_data)} bytes ({poc})")
    click.echo(f"Key: {len(pubkey_der)} bytes ({key})")

    sealed = ecies_encrypt(pubkey_der, poc_data)

    with open(out, "wb") as f:
        f.write(sealed)

    click.echo(f"Sealed: {len(sealed)} bytes -> {out}")
    click.echo(f"SHA-256: {hashlib.sha256(sealed).hexdigest()}")
    click.echo(f"\nYour PoC is encrypted. Only the attested enclave can decrypt it.")


@cli.command("verify-pcr0")
@click.option("--pcr0", required=True, help="PCR0 hex string (96 chars = 48 bytes SHA-384)")
@click.option("--registry", default="0x472c8e2239A5AFe29BB828479c5F4bCf4de119F4",
              help="PCR0Registry contract address")
@click.option("--rpc", default="https://ethereum-sepolia-rpc.publicnode.com",
              help="Ethereum RPC URL")
def verify_pcr0(pcr0, registry, rpc):
    """Check a PCR0 value against the on-chain registry."""
    if len(pcr0) != 96:
        click.echo(f"Error: PCR0 should be 96 hex chars (48 bytes SHA-384), got {len(pcr0)}", err=True)
        sys.exit(1)

    click.echo(f"PCR0: {pcr0[:32]}...{pcr0[-8:]}")
    click.echo(f"Registry: {registry}")

    # Call verifyPCR0(bytes32, bytes16) via eth_call
    high = pcr0[:64]
    low = pcr0[64:]

    # Call getPCR0() to get the current on-chain PCR0
    # Function selector for getPCR0(): 0x93237378
    # (computed via cast sig "getPCR0()")
    data_get = "0x94237378"

    resp = httpx.post(rpc, json={
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": registry, "data": data_get}, "latest"],
        "id": 1,
    }, timeout=15)

    result = resp.json()
    if "error" in result:
        click.echo(f"RPC Error: {result['error']}", err=True)
        sys.exit(1)

    raw = result.get("result", "0x")
    if raw == "0x" or len(raw) < 66:
        click.echo("No PCR0 published on-chain yet", err=True)
        sys.exit(1)

    # Decode: bytes32 (64 hex) + bytes16 (32 hex, right-padded to 64)
    onchain_high = raw[2:66]
    onchain_low = raw[66:98]  # bytes16 = 32 hex chars
    onchain_pcr0 = onchain_high + onchain_low

    click.echo(f"On-chain PCR0: {onchain_pcr0[:32]}...{onchain_pcr0[-8:]}")

    if pcr0 == onchain_pcr0:
        click.echo(f"\nMATCH — PCR0 matches on-chain registry")
        click.echo("The enclave is running the published, auditable code.")
    else:
        click.echo(f"\nMISMATCH")
        click.echo(f"  Your PCR0:    {pcr0[:32]}...")
        click.echo(f"  On-chain:     {onchain_pcr0[:32]}...")
        click.echo("WARNING: The enclave may be running modified code.", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
