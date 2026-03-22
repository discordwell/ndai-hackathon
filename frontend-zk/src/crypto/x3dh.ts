/**
 * X3DH (Extended Triple Diffie-Hellman) key agreement.
 *
 * Implements the Signal X3DH specification for establishing a shared secret
 * between two parties who have never communicated before. The shared secret
 * is used to initialize the Double Ratchet.
 *
 * See: https://signal.org/docs/specifications/x3dh/
 */
import { hkdf } from "@noble/hashes/hkdf";
import { sha256 } from "@noble/hashes/sha256";
import {
  ed25519PrivToX25519,
  ed25519PubToX25519,
  x25519DH,
  generateEphemeralX25519,
  deriveSignedPrekey,
  deriveOneTimePrekey,
  verifyPrekeySignature,
  bytesToHex,
  hexToBytes,
  type X25519Keypair,
} from "./keys";

const X3DH_INFO = new TextEncoder().encode("ZDAYZK_X3DH_V1");

// 32 bytes of 0xFF as the X3DH "F" padding value per spec
const X3DH_F = new Uint8Array(32).fill(0xff);

export interface PeerBundle {
  identityPubkey: string; // Ed25519 hex
  identityX25519Pub: string; // X25519 hex
  signedPrekeyPub: string; // X25519 hex
  signedPrekeySig: string; // Ed25519 sig hex
  signedPrekeyId: number;
  oneTimePrekey: { pub: string; index: number } | null;
}

export interface X3DHHeader {
  identityKey: string; // initiator's Ed25519 pubkey hex
  ephemeralKey: string; // initiator's ephemeral X25519 pubkey hex
  otpkIndex: number | null; // which OTPK was used (null if none available)
}

export interface X3DHResult {
  sharedSecret: Uint8Array; // 32 bytes, used to initialize Double Ratchet
  x3dhHeader: X3DHHeader; // sent with the first message
  peerDHPub: Uint8Array; // peer's signed prekey (used as initial DHr in ratchet)
}

/**
 * Initiator side of X3DH.
 *
 * Alice wants to message Bob. She fetches Bob's prekey bundle from the server,
 * verifies the signature, and computes a shared secret.
 */
export async function initiateX3DH(
  myEdPriv: Uint8Array,
  myEdPub: Uint8Array,
  peerBundle: PeerBundle,
): Promise<X3DHResult> {
  // Verify the signed prekey signature
  const valid = await verifyPrekeySignature(
    hexToBytes(peerBundle.identityPubkey),
    hexToBytes(peerBundle.signedPrekeyPub),
    peerBundle.signedPrekeySig,
  );
  if (!valid) {
    throw new Error("Invalid signed prekey signature");
  }

  // Convert identity keys to X25519
  const myIKPriv = ed25519PrivToX25519(myEdPriv);
  const peerIKPub = hexToBytes(peerBundle.identityX25519Pub);
  const peerSPKPub = hexToBytes(peerBundle.signedPrekeyPub);

  // Generate ephemeral keypair
  const ek = generateEphemeralX25519();

  // Compute the four DH values
  const dh1 = x25519DH(myIKPriv, peerSPKPub); // DH(IK_a, SPK_b)
  const dh2 = x25519DH(ek.priv, peerIKPub); // DH(EK_a, IK_b)
  const dh3 = x25519DH(ek.priv, peerSPKPub); // DH(EK_a, SPK_b)

  let dhConcat: Uint8Array;
  let otpkIndex: number | null = null;

  if (peerBundle.oneTimePrekey) {
    const otpkPub = hexToBytes(peerBundle.oneTimePrekey.pub);
    const dh4 = x25519DH(ek.priv, otpkPub); // DH(EK_a, OTPK_b)
    otpkIndex = peerBundle.oneTimePrekey.index;
    dhConcat = concat(X3DH_F, dh1, dh2, dh3, dh4);
  } else {
    dhConcat = concat(X3DH_F, dh1, dh2, dh3);
  }

  // Derive shared secret via HKDF
  const sharedSecret = hkdf(sha256, dhConcat, new Uint8Array(32), X3DH_INFO, 32);

  return {
    sharedSecret,
    x3dhHeader: {
      identityKey: bytesToHex(myEdPub),
      ephemeralKey: bytesToHex(ek.pub),
      otpkIndex,
    },
    peerDHPub: peerSPKPub,
  };
}

/**
 * Responder side of X3DH.
 *
 * Bob receives Alice's first message with an X3DH header. He re-derives
 * his SPK and OTPK private keys deterministically from his passphrase,
 * then computes the same shared secret.
 */
export function respondX3DH(
  myEdPriv: Uint8Array,
  myEdPub: Uint8Array,
  spkIndex: number,
  x3dhHeader: X3DHHeader,
): Uint8Array {
  // Convert identity keys to X25519
  const myIKPriv = ed25519PrivToX25519(myEdPriv);
  const peerIKPub = ed25519PubToX25519(hexToBytes(x3dhHeader.identityKey));
  const peerEKPub = hexToBytes(x3dhHeader.ephemeralKey);

  // Re-derive signed prekey private
  const spk = deriveSignedPrekey(myEdPriv, spkIndex);

  // Compute the four DH values (mirrored)
  const dh1 = x25519DH(spk.priv, peerIKPub); // DH(SPK_b, IK_a)
  const dh2 = x25519DH(myIKPriv, peerEKPub); // DH(IK_b, EK_a)
  const dh3 = x25519DH(spk.priv, peerEKPub); // DH(SPK_b, EK_a)

  let dhConcat: Uint8Array;

  if (x3dhHeader.otpkIndex !== null) {
    const otpk = deriveOneTimePrekey(myEdPriv, x3dhHeader.otpkIndex);
    const dh4 = x25519DH(otpk.priv, peerEKPub); // DH(OTPK_b, EK_a)
    dhConcat = concat(X3DH_F, dh1, dh2, dh3, dh4);
  } else {
    dhConcat = concat(X3DH_F, dh1, dh2, dh3);
  }

  return hkdf(sha256, dhConcat, new Uint8Array(32), X3DH_INFO, 32);
}

// ─── Helpers ──────────────────────────────────────────────────────────

function concat(...arrays: Uint8Array[]): Uint8Array {
  const total = arrays.reduce((sum, a) => sum + a.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const a of arrays) {
    result.set(a, offset);
    offset += a.length;
  }
  return result;
}
