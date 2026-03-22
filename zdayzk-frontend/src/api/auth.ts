import { post, get } from "./client";
import type { TokenResponse, UserProfile } from "./types";

export function register(
  email: string,
  password: string,
  displayName?: string
): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/register", {
    email,
    password,
    role: "user",
    display_name: displayName,
  });
}

export function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/login", { email, password });
}

export function getMe(): Promise<UserProfile> {
  return get<UserProfile>("/auth/me");
}
