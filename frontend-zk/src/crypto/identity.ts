/**
 * Zero-knowledge identity: password-derived Ed25519 keypairs.
 *
 * The passphrase never leaves the client. PBKDF2-SHA512 derives a
 * 32-byte seed, which becomes the Ed25519 private key. The server
 * only ever sees the public key.
 */
import * as ed from "@noble/ed25519";

const SALT = "NDAI_ZK_V1";
const PBKDF2_ITERATIONS = 600000; // OWASP recommended for SHA-512
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
 * Uses Web Crypto PBKDF2-SHA512 — native, async, non-blocking.
 */
export async function deriveIdentity(passphrase: string): Promise<ZKIdentity> {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw", enc.encode(passphrase), "PBKDF2", false, ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt: enc.encode(SALT), iterations: PBKDF2_ITERATIONS, hash: "SHA-512" },
    keyMaterial,
    KEY_LEN * 8,
  );

  const privateKey = new Uint8Array(bits);
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
