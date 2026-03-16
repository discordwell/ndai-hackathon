import { post } from "./client";
import type { LoginRequest, RegisterRequest, TokenResponse } from "./types";

export function register(data: RegisterRequest): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/register", data);
}

export function login(data: LoginRequest): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/login", data);
}
