import { get } from "./client";

export interface AttestationResponse {
  attestation_doc: string;       // base64 COSE Sign1
  enclave_public_key: string;    // base64 P-384 DER (120 bytes)
  pcr0: string;                  // hex
  format: string;                // "cose_sign1"
  mode: string;                  // "simulated" | "nitro"
  valid?: boolean;               // nitro mode only
  error?: string;
}

export function fetchAttestation(nonce: string): Promise<AttestationResponse> {
  return get<AttestationResponse>(`/enclave/attestation?nonce=${nonce}`);
}
