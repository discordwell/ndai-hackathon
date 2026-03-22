/**
 * Session store for Double Ratchet state.
 *
 * Uses sessionStorage — state is lost when all tabs close. This is intentional
 * for privacy: the user re-derives everything from their passphrase on next login.
 * Sessions that cannot be recovered trigger a new X3DH handshake.
 */
import type { RatchetState } from "./doubleratchet";

const PREFIX = "zdayzk_ratchet_";

export function saveSession(conversationId: string, state: RatchetState): void {
  try {
    sessionStorage.setItem(PREFIX + conversationId, JSON.stringify(state));
  } catch {
    // sessionStorage full — evict oldest sessions
    const keys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (key?.startsWith(PREFIX)) keys.push(key);
    }
    if (keys.length > 0) {
      sessionStorage.removeItem(keys[0]);
      sessionStorage.setItem(PREFIX + conversationId, JSON.stringify(state));
    }
  }
}

export function loadSession(conversationId: string): RatchetState | null {
  const raw = sessionStorage.getItem(PREFIX + conversationId);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as RatchetState;
  } catch {
    return null;
  }
}

export function clearSession(conversationId: string): void {
  sessionStorage.removeItem(PREFIX + conversationId);
}

export function clearAllSessions(): void {
  const toRemove: string[] = [];
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (key?.startsWith(PREFIX)) toRemove.push(key);
  }
  toRemove.forEach((k) => sessionStorage.removeItem(k));
}
