import { post } from "./client";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/login", { email, password });
}

export function register(
  email: string,
  password: string,
  name?: string
): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/register", {
    email,
    password,
    name: name || email.split("@")[0],
    role: "user",
  });
}
