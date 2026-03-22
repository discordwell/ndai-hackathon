/**
 * Zero-knowledge identity: password-derived Ed25519 keypairs.
 *
 * The passphrase never leaves the client. scrypt derives a 32-byte seed,
 * which becomes the Ed25519 private key. The server only ever sees the
 * public key.
 */
import { scrypt } from "@noble/hashes/scrypt";
import { utf8ToBytes } from "@noble/hashes/utils";
import * as ed from "@noble/ed25519";

const SALT = "NDAI_ZK_V1";

// scrypt params — N=2^15 (32 MB), r=8, p=1 — memory-hard KDF
// Balances security with browser performance (~1-2s)
const SCRYPT_N = 32768;
const SCRYPT_R = 8;
const SCRYPT_P = 1;
const KEY_LEN = 32;

export interface ZKIdentity {
  publicKey: Uint8Array;  // 32 bytes
  privateKey: Uint8Array; // 32 bytes (seed)
  publicKeyHex: string;
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Derive an Ed25519 identity from a passphrase.
 * Uses scrypt (memory-hard KDF, pure JS — no WASM needed).
 * Takes ~1-3 seconds depending on hardware.
 */
export async function deriveIdentity(passphrase: string): Promise<ZKIdentity> {
  const salt = utf8ToBytes(SALT);
  const pass = utf8ToBytes(passphrase);

  // scrypt is synchronous but CPU-intensive — wrap in a microtask
  // so the UI can show "DERIVING KEY..." before blocking
  const seed = await new Promise<Uint8Array>((resolve) => {
    setTimeout(() => {
      resolve(scrypt(pass, salt, { N: SCRYPT_N, r: SCRYPT_R, p: SCRYPT_P, dkLen: KEY_LEN }));
    }, 0);
  });

  const privateKey = new Uint8Array(seed);
  const publicKey = await ed.getPublicKeyAsync(privateKey);

  return {
    publicKey,
    privateKey,
    publicKeyHex: bytesToHex(publicKey),
  };
}

/**
 * Sign an arbitrary message with the identity's private key.
 * Returns the signature as a hex string.
 */
export async function signMessage(
  privateKey: Uint8Array,
  message: string,
): Promise<string> {
  const msgBytes = new TextEncoder().encode(message);
  const signature = await ed.signAsync(msgBytes, privateKey);
  return bytesToHex(signature);
}

/**
 * Sign a challenge nonce for authentication.
 * Message format: "NDAI_AUTH:{nonce}"
 */
export async function signChallenge(
  privateKey: Uint8Array,
  nonce: string,
): Promise<string> {
  return signMessage(privateKey, `NDAI_AUTH:${nonce}`);
}

/**
 * Sign the registration message.
 * Message format: "NDAI_REGISTER:{publicKeyHex}"
 */
export async function signRegistration(
  privateKey: Uint8Array,
  publicKeyHex: string,
): Promise<string> {
  return signMessage(privateKey, `NDAI_REGISTER:${publicKeyHex}`);
}
