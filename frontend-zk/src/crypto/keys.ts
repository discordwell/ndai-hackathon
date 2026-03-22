/**
 * Key derivation and Ed25519 ↔ X25519 conversion for Signal protocol.
 *
 * All messaging keys are deterministically derived from the Ed25519 identity
 * private key (itself derived from the passphrase via argon2id). This means
 * no persistent client-side key storage is needed beyond the passphrase.
 */
import { edwardsToMontgomeryPriv, edwardsToMontgomeryPub } from "@noble/curves/ed25519";
import { x25519 } from "@noble/curves/ed25519";
import { hkdf } from "@noble/hashes/hkdf";
import { sha256 } from "@noble/hashes/sha256";
import * as ed from "@noble/ed25519";

// ─── Hex helpers ───────────────────────────────────────────────────────

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

// ─── Ed25519 → X25519 conversion ──────────────────────────────────────

/**
 * Convert an Ed25519 private key to X25519 for Diffie-Hellman.
 * Uses the birational map between Edwards and Montgomery curves.
 */
export function ed25519PrivToX25519(edPriv: Uint8Array): Uint8Array {
  return edwardsToMontgomeryPriv(edPriv);
}

/**
 * Convert an Ed25519 public key to X25519 for Diffie-Hellman.
 */
export function ed25519PubToX25519(edPub: Uint8Array): Uint8Array {
  return edwardsToMontgomeryPub(edPub);
}

// ─── X25519 key operations ─────────────────────────────────────────────

export interface X25519Keypair {
  pub: Uint8Array;
  priv: Uint8Array;
}

/**
 * Generate an X25519 keypair from a 32-byte seed.
 */
export function x25519KeypairFromSeed(seed: Uint8Array): X25519Keypair {
  const priv = seed.slice(0, 32);
  const pub = x25519.getPublicKey(priv);
  return { pub, priv };
}

/**
 * Perform X25519 Diffie-Hellman: shared_secret = DH(myPriv, theirPub)
 */
export function x25519DH(myPriv: Uint8Array, theirPub: Uint8Array): Uint8Array {
  return x25519.getSharedSecret(myPriv, theirPub);
}

/**
 * Generate a fresh ephemeral X25519 keypair using crypto.getRandomValues.
 */
export function generateEphemeralX25519(): X25519Keypair {
  const priv = new Uint8Array(32);
  crypto.getRandomValues(priv);
  const pub = x25519.getPublicKey(priv);
  return { pub, priv };
}

// ─── Deterministic prekey derivation ───────────────────────────────────

/**
 * Derive a signed prekey from the Ed25519 private key and a rotation index.
 * Deterministic — same passphrase + same index = same SPK.
 */
export function deriveSignedPrekey(edPriv: Uint8Array, index: number): X25519Keypair {
  const info = new TextEncoder().encode(`ZDAYZK_SPK_V1:${index}`);
  const seed = hkdf(sha256, edPriv, new Uint8Array(0), info, 32);
  return x25519KeypairFromSeed(seed);
}

/**
 * Derive a one-time prekey from the Ed25519 private key and a monotonic index.
 * Deterministic — same passphrase + same index = same OTPK.
 */
export function deriveOneTimePrekey(edPriv: Uint8Array, index: number): X25519Keypair {
  const info = new TextEncoder().encode(`ZDAYZK_OTPK_V1:${index}`);
  const seed = hkdf(sha256, edPriv, new Uint8Array(0), info, 32);
  return x25519KeypairFromSeed(seed);
}

/**
 * Sign a prekey's public key with the Ed25519 identity key.
 * The recipient verifies this to ensure the prekey belongs to the claimed identity.
 */
export async function signPrekey(edPriv: Uint8Array, spkPub: Uint8Array): Promise<string> {
  const msg = new TextEncoder().encode(`ZDAYZK_SPK:${bytesToHex(spkPub)}`);
  const sig = await ed.signAsync(msg, edPriv);
  return bytesToHex(sig);
}

/**
 * Verify a prekey signature against an Ed25519 public key.
 */
export async function verifyPrekeySignature(
  edPub: Uint8Array,
  spkPub: Uint8Array,
  signature: string,
): Promise<boolean> {
  const msg = new TextEncoder().encode(`ZDAYZK_SPK:${bytesToHex(spkPub)}`);
  return ed.verifyAsync(hexToBytes(signature), msg, edPub);
}

// ─── Full prekey bundle generation ─────────────────────────────────────

export interface PrekeyBundle {
  identityX25519Pub: string; // hex
  signedPrekeyPub: string; // hex
  signedPrekeySig: string; // hex
  signedPrekeyId: number;
  oneTimePrekeys: { pub: string; index: number }[];
}

/**
 * Generate a complete prekey bundle for upload to the server.
 */
export async function generatePrekeyBundle(
  edPriv: Uint8Array,
  edPub: Uint8Array,
  spkIndex: number,
  otpkStartIndex: number,
  otpkCount: number = 20,
): Promise<PrekeyBundle> {
  const identityX25519 = ed25519PubToX25519(edPub);
  const spk = deriveSignedPrekey(edPriv, spkIndex);
  const sig = await signPrekey(edPriv, spk.pub);

  const otpks: { pub: string; index: number }[] = [];
  for (let i = 0; i < otpkCount; i++) {
    const idx = otpkStartIndex + i;
    const otpk = deriveOneTimePrekey(edPriv, idx);
    otpks.push({ pub: bytesToHex(otpk.pub), index: idx });
  }

  return {
    identityX25519Pub: bytesToHex(identityX25519),
    signedPrekeyPub: bytesToHex(spk.pub),
    signedPrekeySig: sig,
    signedPrekeyId: spkIndex,
    oneTimePrekeys: otpks,
  };
}
