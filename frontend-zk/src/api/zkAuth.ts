import { post } from "./client";

export interface ZKRegisterResponse {
  status: string;
}

export interface ZKChallengeResponse {
  nonce: string;
}

export interface ZKVerifyResponse {
  access_token: string;
  token_type: string;
}

export function register(
  publicKey: string,
  signature: string,
): Promise<ZKRegisterResponse> {
  return post<ZKRegisterResponse>("/zk-auth/register", {
    public_key: publicKey,
    signature,
  });
}

export function challenge(publicKey: string): Promise<ZKChallengeResponse> {
  return post<ZKChallengeResponse>("/zk-auth/challenge", {
    public_key: publicKey,
  });
}

export function verify(
  publicKey: string,
  nonce: string,
  signature: string,
): Promise<ZKVerifyResponse> {
  return post<ZKVerifyResponse>("/zk-auth/verify", {
    public_key: publicKey,
    nonce,
    signature,
  });
}
