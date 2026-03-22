/**
 * Zero-knowledge identity: password-derived Ed25519 keypairs.
 *
 * The passphrase never leaves the client. argon2id derives a 32-byte seed,
 * which becomes the Ed25519 private key. The server only ever sees the
 * public key.
 */
import argon2 from "argon2-browser";
import * as ed from "@noble/ed25519";

const SALT = "NDAI_ZK_V1";

// argon2id params — 256 MB memory makes offline brute-force impractical
const ARGON2_MEM = 262144; // 256 MB in KiB
const ARGON2_TIME = 3;
const ARGON2_PARALLELISM = 4;
const ARGON2_HASH_LEN = 32;

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
 * Takes ~2-4 seconds depending on hardware (256 MB argon2id).
 */
export async function deriveIdentity(passphrase: string): Promise<ZKIdentity> {
  const result = await argon2.hash({
    pass: passphrase,
    salt: SALT,
    type: argon2.ArgonType.Argon2id,
    mem: ARGON2_MEM,
    time: ARGON2_TIME,
    parallelism: ARGON2_PARALLELISM,
    hashLen: ARGON2_HASH_LEN,
  });

  const privateKey = new Uint8Array(result.hash);
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
