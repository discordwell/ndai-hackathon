/**
 * ECIES encryption compatible with ndai/enclave/ephemeral_keys.py
 *
 * Scheme:
 *   - ECDH: P-384 (secp384r1)
 *   - KDF: HKDF-SHA384, info = "ndai-key-delivery"
 *   - Encryption: AES-256-GCM
 *   - Output: [ephemeral_pubkey_DER(120) | nonce(12) | ciphertext+tag]
 */

import { p384 } from "@noble/curves/p384";
import { hkdf } from "@noble/hashes/hkdf";
import { sha384 } from "@noble/hashes/sha2";

const ECIES_INFO = new TextEncoder().encode("ndai-key-delivery");
const AES_KEY_SIZE = 32;
const GCM_NONCE_SIZE = 12;

// Fixed DER header for P-384 SubjectPublicKeyInfo (23 bytes)
// SEQUENCE { SEQUENCE { OID ecPublicKey, OID secp384r1 }, BIT STRING { uncompressed point } }
const P384_SPKI_DER_HEADER = new Uint8Array([
  0x30, 0x76, // SEQUENCE (118 bytes)
  0x30, 0x10, // SEQUENCE (16 bytes)
  0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01, // OID 1.2.840.10045.2.1 (ecPublicKey)
  0x06, 0x05, 0x2b, 0x81, 0x04, 0x00, 0x22,               // OID 1.3.132.0.34 (secp384r1)
  0x03, 0x62, 0x00, // BIT STRING (98 bytes, 0 unused bits)
]);

/**
 * Build a SubjectPublicKeyInfo DER encoding from an uncompressed P-384 point.
 * @param uncompressedPoint 97 bytes (0x04 || x(48) || y(48))
 * @returns 120-byte DER encoding
 */
function buildP384DER(uncompressedPoint: Uint8Array): Uint8Array {
  const der = new Uint8Array(P384_SPKI_DER_HEADER.length + uncompressedPoint.length);
  der.set(P384_SPKI_DER_HEADER, 0);
  der.set(uncompressedPoint, P384_SPKI_DER_HEADER.length);
  return der;
}

/**
 * Extract the uncompressed point from a P-384 SubjectPublicKeyInfo DER encoding.
 * @param der 120-byte DER encoding
 * @returns 97 bytes (0x04 || x(48) || y(48))
 */
function extractPointFromDER(der: Uint8Array): Uint8Array {
  return der.slice(P384_SPKI_DER_HEADER.length);
}

/**
 * Encrypt plaintext to a P-384 public key using ECIES.
 *
 * Compatible with Python's ecies_decrypt() in ndai/enclave/ephemeral_keys.py.
 *
 * @param recipientPubKeyDER 120-byte SubjectPublicKeyInfo DER
 * @param plaintext bytes to encrypt
 * @returns [ephemeral_pubkey_DER(120) | nonce(12) | ciphertext+tag]
 */
export async function eciesEncrypt(
  recipientPubKeyDER: Uint8Array,
  plaintext: Uint8Array,
): Promise<Uint8Array> {
  // 1. Extract recipient's uncompressed point from DER
  const recipientPoint = extractPointFromDER(recipientPubKeyDER);

  // 2. Generate ephemeral P-384 keypair
  const ephPrivKey = p384.utils.randomPrivateKey();
  const ephPubUncompressed = p384.getPublicKey(ephPrivKey, false); // 97 bytes

  // 3. ECDH shared secret (raw shared point)
  const sharedPoint = p384.getSharedSecret(ephPrivKey, recipientPoint);
  // sharedPoint is 97 bytes (04 || x || y). Extract x-coordinate only (bytes 1-49).
  const sharedSecret = sharedPoint.slice(1, 49); // 48 bytes

  // 4. HKDF-SHA384 to derive AES-256 key
  const derivedKey = hkdf(sha384, sharedSecret, undefined, ECIES_INFO, AES_KEY_SIZE);

  // 5. AES-256-GCM encrypt via Web Crypto
  const nonce = crypto.getRandomValues(new Uint8Array(GCM_NONCE_SIZE));
  const aesKey = await crypto.subtle.importKey("raw", derivedKey, "AES-GCM", false, ["encrypt"]);
  const ciphertextBuf = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce },
    aesKey,
    plaintext,
  );

  // 6. Build ephemeral public key DER (120 bytes)
  const ephPubDER = buildP384DER(ephPubUncompressed);

  // 7. Pack: ephemeral_pubkey_DER(120) | nonce(12) | ciphertext+tag
  const ciphertextArr = new Uint8Array(ciphertextBuf);
  const result = new Uint8Array(ephPubDER.length + GCM_NONCE_SIZE + ciphertextArr.length);
  result.set(ephPubDER, 0);
  result.set(nonce, ephPubDER.length);
  result.set(ciphertextArr, ephPubDER.length + GCM_NONCE_SIZE);
  return result;
}
