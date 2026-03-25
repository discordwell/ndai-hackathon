export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1];
    if (!base64) return null;
    const padded = base64.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

export function msUntilExpiry(token: string): number | null {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== "number") return null;
  return Math.max(0, payload.exp * 1000 - Date.now());
}

export function isTokenValid(token: string): boolean {
  const ms = msUntilExpiry(token);
  return ms === null || ms > 0;
}
