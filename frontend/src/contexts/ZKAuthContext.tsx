import React, { createContext, useContext, useState, useCallback } from "react";
import { deriveIdentity, signRegistration, signChallenge } from "../crypto/identity";
import type { ZKIdentity } from "../crypto/identity";

interface ZKAuthState {
  publicKeyHex: string | null;
  isAuthenticated: boolean;
  isDerivingKey: boolean;
  /** True when token exists from prior session but private key is gone (page reload). */
  needsReauth: boolean;
}

interface ZKAuthContextValue extends ZKAuthState {
  login: (passphrase: string) => Promise<void>;
  logout: () => void;
  identity: ZKIdentity | null;
}

const ZKAuthContext = createContext<ZKAuthContextValue | null>(null);

const ZK_API = "/api/v1/zk-auth";

export function ZKAuthProvider({ children }: { children: React.ReactNode }) {
  const [identity, setIdentity] = useState<ZKIdentity | null>(null);
  const [auth, setAuth] = useState<ZKAuthState>(() => {
    const token = sessionStorage.getItem("zkToken");
    const pubkey = sessionStorage.getItem("zkPubkey");
    // After page reload, token survives in sessionStorage but private key is
    // gone. We mark this as needsReauth so the UI can prompt re-login rather
    // than letting users hit confusing errors when signing operations fail.
    const hasToken = !!token;
    return {
      publicKeyHex: pubkey,
      isAuthenticated: false, // require fresh login — private key is gone
      isDerivingKey: false,
      needsReauth: hasToken, // show "re-enter passphrase" prompt
    };
  });

  const login = useCallback(async (passphrase: string) => {
    setAuth((prev) => ({ ...prev, isDerivingKey: true }));

    try {
      // 1. Derive Ed25519 keypair from passphrase (argon2id, ~2-4s)
      const id = await deriveIdentity(passphrase);

      // 2. Register (idempotent — creates identity if new, no-ops if exists)
      const regSig = await signRegistration(id.privateKey, id.publicKeyHex);
      const regRes = await fetch(`${ZK_API}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          public_key: id.publicKeyHex,
          signature: regSig,
        }),
      });
      if (!regRes.ok) {
        const err = await regRes.json().catch(() => ({}));
        throw new Error(err.detail || "Registration failed");
      }

      // 3. Request challenge nonce
      const challengeRes = await fetch(`${ZK_API}/challenge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ public_key: id.publicKeyHex }),
      });
      if (!challengeRes.ok) throw new Error("Challenge request failed");
      const { nonce } = await challengeRes.json();

      // 4. Sign challenge and verify
      const authSig = await signChallenge(id.privateKey, nonce);
      const verifyRes = await fetch(`${ZK_API}/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          public_key: id.publicKeyHex,
          nonce,
          signature: authSig,
        }),
      });
      if (!verifyRes.ok) throw new Error("Verification failed");
      const { access_token } = await verifyRes.json();

      // 5. Store token in sessionStorage (clears on tab close)
      sessionStorage.setItem("zkToken", access_token);
      sessionStorage.setItem("zkPubkey", id.publicKeyHex);

      // 6. Keep identity in memory only (private key never persisted)
      setIdentity(id);
      setAuth({
        publicKeyHex: id.publicKeyHex,
        isAuthenticated: true,
        isDerivingKey: false,
        needsReauth: false,
      });
    } catch (e) {
      setAuth((prev) => ({ ...prev, isDerivingKey: false }));
      throw e;
    }
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem("zkToken");
    sessionStorage.removeItem("zkPubkey");
    setIdentity(null);
    setAuth({ publicKeyHex: null, isAuthenticated: false, isDerivingKey: false, needsReauth: false });
  }, []);

  return (
    <ZKAuthContext.Provider value={{ ...auth, login, logout, identity }}>
      {children}
    </ZKAuthContext.Provider>
  );
}

export function useZKAuth(): ZKAuthContextValue {
  const ctx = useContext(ZKAuthContext);
  if (!ctx) throw new Error("useZKAuth must be used within ZKAuthProvider");
  return ctx;
}
