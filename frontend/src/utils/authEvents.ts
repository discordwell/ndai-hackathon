const authEvents = new EventTarget();
export const AUTH_UNAUTHORIZED = "auth:unauthorized";

export function emitUnauthorized(): void {
  authEvents.dispatchEvent(new Event(AUTH_UNAUTHORIZED));
}

export function onUnauthorized(callback: () => void): () => void {
  authEvents.addEventListener(AUTH_UNAUTHORIZED, callback);
  return () => authEvents.removeEventListener(AUTH_UNAUTHORIZED, callback);
}
