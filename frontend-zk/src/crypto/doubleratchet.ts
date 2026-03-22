/**
 * Double Ratchet protocol implementation.
 *
 * Provides forward secrecy: each message uses a unique key. Compromising
 * the current key does not reveal past messages. Each "turn" (when the
 * sender changes) triggers a Diffie-Hellman ratchet step.
 *
 * See: https://signal.org/docs/specifications/doubleratchet/
 */
import { x25519 } from "@noble/curves/ed25519";
import { hkdf } from "@noble/hashes/hkdf";
import { sha256 } from "@noble/hashes/sha256";
import { hmac } from "@noble/hashes/hmac";
import { bytesToHex, hexToBytes, type X25519Keypair } from "./keys";

const MAX_SKIP = 100;
const RATCHET_INFO = new TextEncoder().encode("ZDAYZK_RATCHET_V1");
const CHAIN_INFO = new TextEncoder().encode("ZDAYZK_CHAIN_V1");

// ─── Types ─────────────────────────────────────────────────────────────

export interface RatchetHeader {
  dhPub: string; // sender's current DH ratchet public key (hex)
  n: number; // message number in current sending chain
  pn: number; // previous sending chain length
}

export interface RatchetState {
  DHs: { pub: string; priv: string }; // sending DH keypair (hex)
  DHr: string | null; // remote DH public key (hex)
  RK: string; // root key (hex, 32 bytes)
  CKs: string | null; // sending chain key (hex)
  CKr: string | null; // receiving chain key (hex)
  Ns: number; // sending message counter
  Nr: number; // receiving message counter
  Pn: number; // previous sending chain length
  MKSKIPPED: Record<string, string>; // "{dhPub}:{n}" → message key (hex)
}

export interface EncryptResult {
  state: RatchetState;
  header: RatchetHeader;
  ciphertext: string; // base64
}

export interface DecryptResult {
  state: RatchetState;
  plaintext: Uint8Array;
}

// ─── Initialization ────────────────────────────────────────────────────

/**
 * Initialize as the X3DH initiator (Alice).
 * Alice has the shared secret and Bob's signed prekey as the initial DHr.
 */
export function initSender(
  sharedSecret: Uint8Array,
  peerDHPub: Uint8Array,
): RatchetState {
  // Generate initial sending DH keypair
  const dhPriv = new Uint8Array(32);
  crypto.getRandomValues(dhPriv);
  const dhPub = x25519.getPublicKey(dhPriv);

  // Perform initial DH ratchet step
  const dhOutput = x25519.getSharedSecret(dhPriv, peerDHPub);
  const [rk, cks] = kdfRK(sharedSecret, dhOutput);

  return {
    DHs: { pub: bytesToHex(dhPub), priv: bytesToHex(dhPriv) },
    DHr: bytesToHex(peerDHPub),
    RK: bytesToHex(rk),
    CKs: bytesToHex(cks),
    CKr: null,
    Ns: 0,
    Nr: 0,
    Pn: 0,
    MKSKIPPED: {},
  };
}

/**
 * Initialize as the X3DH responder (Bob).
 * Bob uses his signed prekey as the initial DH keypair.
 */
export function initReceiver(
  sharedSecret: Uint8Array,
  myDHKeypair: X25519Keypair,
): RatchetState {
  return {
    DHs: { pub: bytesToHex(myDHKeypair.pub), priv: bytesToHex(myDHKeypair.priv) },
    DHr: null,
    RK: bytesToHex(sharedSecret),
    CKs: null,
    CKr: null,
    Ns: 0,
    Nr: 0,
    Pn: 0,
    MKSKIPPED: {},
  };
}

// ─── Encrypt ───────────────────────────────────────────────────────────

/**
 * Encrypt a plaintext message using the Double Ratchet.
 */
export async function ratchetEncrypt(
  state: RatchetState,
  plaintext: Uint8Array,
): Promise<EncryptResult> {
  const newState = { ...state, MKSKIPPED: { ...state.MKSKIPPED } };

  if (!newState.CKs) {
    throw new Error("Sending chain not initialized — receive a message first");
  }

  const [newCKs, mk] = kdfCK(hexToBytes(newState.CKs));
  const header: RatchetHeader = {
    dhPub: newState.DHs.pub,
    n: newState.Ns,
    pn: newState.Pn,
  };

  newState.CKs = bytesToHex(newCKs);
  newState.Ns += 1;

  const ciphertext = await aesEncrypt(mk, plaintext, serializeHeader(header));
  return { state: newState, header, ciphertext };
}

// ─── Decrypt ───────────────────────────────────────────────────────────

/**
 * Decrypt a message using the Double Ratchet.
 * Handles DH ratchet steps and out-of-order messages.
 */
export async function ratchetDecrypt(
  state: RatchetState,
  header: RatchetHeader,
  ciphertext: string,
): Promise<DecryptResult> {
  let newState = { ...state, MKSKIPPED: { ...state.MKSKIPPED } };

  // Try skipped message keys first
  const skipKey = `${header.dhPub}:${header.n}`;
  if (newState.MKSKIPPED[skipKey]) {
    const mk = hexToBytes(newState.MKSKIPPED[skipKey]);
    delete newState.MKSKIPPED[skipKey];
    const plaintext = await aesDecrypt(mk, ciphertext, serializeHeader(header));
    return { state: newState, plaintext };
  }

  // DH ratchet step if new DH key from peer
  if (header.dhPub !== newState.DHr) {
    // Skip any remaining messages in the current receiving chain
    if (newState.CKr !== null && newState.DHr !== null) {
      newState = skipMessageKeys(newState, newState.DHr, header.pn);
    }

    // Perform DH ratchet step
    newState = dhRatchetStep(newState, header.dhPub);
  }

  // Skip to the correct message in the new receiving chain
  newState = skipMessageKeys(newState, header.dhPub, header.n);

  // Derive the message key
  if (!newState.CKr) {
    throw new Error("Receiving chain not initialized");
  }
  const [newCKr, mk] = kdfCK(hexToBytes(newState.CKr));
  newState.CKr = bytesToHex(newCKr);
  newState.Nr += 1;

  const plaintext = await aesDecrypt(mk, ciphertext, serializeHeader(header));
  return { state: newState, plaintext };
}

// ─── Internal: DH Ratchet Step ─────────────────────────────────────────

function dhRatchetStep(state: RatchetState, peerDHPub: string): RatchetState {
  const newState = { ...state };
  newState.Pn = newState.Ns;
  newState.Ns = 0;
  newState.Nr = 0;
  newState.DHr = peerDHPub;

  // Derive new receiving chain key
  const dhRecv = x25519.getSharedSecret(
    hexToBytes(newState.DHs.priv),
    hexToBytes(peerDHPub),
  );
  const [rk1, ckr] = kdfRK(hexToBytes(newState.RK), dhRecv);
  newState.RK = bytesToHex(rk1);
  newState.CKr = bytesToHex(ckr);

  // Generate new sending DH keypair
  const newPriv = new Uint8Array(32);
  crypto.getRandomValues(newPriv);
  const newPub = x25519.getPublicKey(newPriv);
  newState.DHs = { pub: bytesToHex(newPub), priv: bytesToHex(newPriv) };

  // Derive new sending chain key
  const dhSend = x25519.getSharedSecret(newPriv, hexToBytes(peerDHPub));
  const [rk2, cks] = kdfRK(hexToBytes(newState.RK), dhSend);
  newState.RK = bytesToHex(rk2);
  newState.CKs = bytesToHex(cks);

  return newState;
}

// ─── Internal: Skip Message Keys ───────────────────────────────────────

function skipMessageKeys(state: RatchetState, dhPub: string, until: number): RatchetState {
  const newState = { ...state, MKSKIPPED: { ...state.MKSKIPPED } };

  if (!newState.CKr) return newState;

  while (newState.Nr < until) {
    const skippedCount = Object.keys(newState.MKSKIPPED).length;
    if (skippedCount >= MAX_SKIP) {
      // Evict oldest (approximate — just delete one)
      const oldest = Object.keys(newState.MKSKIPPED)[0];
      if (oldest) delete newState.MKSKIPPED[oldest];
    }

    const [newCKr, mk] = kdfCK(hexToBytes(newState.CKr));
    newState.MKSKIPPED[`${dhPub}:${newState.Nr}`] = bytesToHex(mk);
    newState.CKr = bytesToHex(newCKr);
    newState.Nr += 1;
  }

  return newState;
}

// ─── KDF Functions ─────────────────────────────────────────────────────

/**
 * Root key KDF: derives a new root key and chain key from DH output.
 */
function kdfRK(rk: Uint8Array, dhOutput: Uint8Array): [Uint8Array, Uint8Array] {
  const output = hkdf(sha256, dhOutput, rk, RATCHET_INFO, 64);
  return [output.slice(0, 32), output.slice(32, 64)];
}

/**
 * Chain key KDF: derives a new chain key and message key.
 */
function kdfCK(ck: Uint8Array): [Uint8Array, Uint8Array] {
  const newCK = hmac(sha256, ck, new Uint8Array([0x01]));
  const mk = hmac(sha256, ck, new Uint8Array([0x02]));
  return [newCK, mk];
}

// ─── AES-256-GCM ──────────────────────────────────────────────────────

async function aesEncrypt(
  mk: Uint8Array,
  plaintext: Uint8Array,
  aad: Uint8Array,
): Promise<string> {
  const key = await crypto.subtle.importKey("raw", mk, "AES-GCM", false, ["encrypt"]);
  const iv = new Uint8Array(12);
  crypto.getRandomValues(iv);
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: aad }, key, plaintext);
  // Encode: iv (12) + ciphertext+tag
  const result = new Uint8Array(iv.length + ct.byteLength);
  result.set(iv, 0);
  result.set(new Uint8Array(ct), iv.length);
  return btoa(String.fromCharCode(...result));
}

async function aesDecrypt(
  mk: Uint8Array,
  ciphertextB64: string,
  aad: Uint8Array,
): Promise<Uint8Array> {
  const data = Uint8Array.from(atob(ciphertextB64), (c) => c.charCodeAt(0));
  const iv = data.slice(0, 12);
  const ct = data.slice(12);
  const key = await crypto.subtle.importKey("raw", mk, "AES-GCM", false, ["decrypt"]);
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv, additionalData: aad }, key, ct);
  return new Uint8Array(pt);
}

// ─── Header Serialization ──────────────────────────────────────────────

function serializeHeader(header: RatchetHeader): Uint8Array {
  return new TextEncoder().encode(JSON.stringify(header));
}

export function headerToBase64(header: RatchetHeader): string {
  return btoa(JSON.stringify(header));
}

export function headerFromBase64(b64: string): RatchetHeader {
  return JSON.parse(atob(b64));
}

export function x3dhHeaderToBase64(header: { identityKey: string; ephemeralKey: string; otpkIndex: number | null }): string {
  return btoa(JSON.stringify(header));
}

export function x3dhHeaderFromBase64(b64: string): { identityKey: string; ephemeralKey: string; otpkIndex: number | null } {
  return JSON.parse(atob(b64));
}
