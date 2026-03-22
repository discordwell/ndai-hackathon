import React, { createContext, useContext, useState, useCallback } from "react";
import { deriveIdentity, signRegistration, signChallenge } from "../crypto/identity";
import type { ZKIdentity } from "../crypto/identity";
import * as zkApi from "../api/zkAuth";
import { generatePrekeyBundle } from "../crypto/keys";
import { uploadPrekeys, getPrekeyStatus } from "../api/messaging";

const TOKEN_KEY = "zdayzk_token";
const PUBKEY_KEY = "zdayzk_pubkey";

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  publicKeyHex: string | null;
  isDerivingKey: boolean;
}

interface AuthContextValue extends AuthState {
  login: (passphrase: string) => Promise<void>;
  register: (passphrase: string) => Promise<string>;
  logout: () => void;
  privateKey: Uint8Array | null;
  publicKey: Uint8Array | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [identity, setIdentity] = useState<ZKIdentity | null>(null);
  const [auth, setAuth] = useState<AuthState>(() => {
    const token = sessionStorage.getItem(TOKEN_KEY);
    const pubkey = sessionStorage.getItem(PUBKEY_KEY);
    // After page reload, token may survive in sessionStorage but the private
    // key is gone (memory only). We don't mark as authenticated — user must
    // re-enter passphrase to restore the private key.
    return {
      token,
      isAuthenticated: false,
      publicKeyHex: pubkey,
      isDerivingKey: false,
    };
  });

  // Upload prekey bundle if needed (after auth, non-blocking)
  const ensurePrekeys = useCallback(async (id: ZKIdentity) => {
    try {
      const status = await getPrekeyStatus();
      if (status.remaining_otpks < 5 || status.signed_prekey_age_hours > 168) {
        // Need to replenish — determine next OTPK index
        const spkIndex = status.signed_prekey_age_hours > 168 ? 1 : 0;
        const otpkStart = 20 - status.remaining_otpks + 20; // approximate next batch
        const bundle = await generatePrekeyBundle(id.privateKey, id.publicKey, spkIndex, otpkStart, 20);
        await uploadPrekeys({
          identity_x25519_pub: bundle.identityX25519Pub,
          signed_prekey_pub: bundle.signedPrekeyPub,
          signed_prekey_sig: bundle.signedPrekeySig,
          signed_prekey_id: bundle.signedPrekeyId,
          one_time_prekeys: bundle.oneTimePrekeys,
        });
      }
    } catch {
      // Prekey upload failure is non-fatal — will retry on next connect
    }
  }, []);

  // Upload initial prekey bundle (on first registration)
  const uploadInitialPrekeys = useCallback(async (id: ZKIdentity) => {
    try {
      const bundle = await generatePrekeyBundle(id.privateKey, id.publicKey, 0, 0, 20);
      await uploadPrekeys({
        identity_x25519_pub: bundle.identityX25519Pub,
        signed_prekey_pub: bundle.signedPrekeyPub,
        signed_prekey_sig: bundle.signedPrekeySig,
        signed_prekey_id: bundle.signedPrekeyId,
        one_time_prekeys: bundle.oneTimePrekeys,
      });
    } catch {
      // Non-fatal
    }
  }, []);

  const login = useCallback(async (passphrase: string) => {
    setAuth((prev) => ({ ...prev, isDerivingKey: true }));

    try {
      // 1. Derive Ed25519 keypair from passphrase (argon2id, ~2-4s)
      const id = await deriveIdentity(passphrase);

      // 2. Register (idempotent — creates identity if new, no-ops if exists)
      const regSig = await signRegistration(id.privateKey, id.publicKeyHex);
      await zkApi.register(id.publicKeyHex, regSig);

      // 3. Request challenge nonce
      const { nonce } = await zkApi.challenge(id.publicKeyHex);

      // 4. Sign challenge and verify
      const authSig = await signChallenge(id.privateKey, nonce);
      const { access_token } = await zkApi.verify(id.publicKeyHex, nonce, authSig);

      // 5. Store token in sessionStorage (clears on tab close)
      sessionStorage.setItem(TOKEN_KEY, access_token);
      sessionStorage.setItem(PUBKEY_KEY, id.publicKeyHex);

      // 6. Keep identity in memory only (private key never persisted)
      setIdentity(id);
      setAuth({
        token: access_token,
        isAuthenticated: true,
        publicKeyHex: id.publicKeyHex,
        isDerivingKey: false,
      });

      // 7. Ensure prekey bundle is uploaded (non-blocking)
      ensurePrekeys(id);
    } catch (e) {
      setAuth((prev) => ({ ...prev, isDerivingKey: false }));
      throw e;
    }
  }, [ensurePrekeys]);

  const register = useCallback(async (passphrase: string): Promise<string> => {
    setAuth((prev) => ({ ...prev, isDerivingKey: true }));

    try {
      // 1. Derive Ed25519 keypair from passphrase (argon2id, ~2-4s)
      const id = await deriveIdentity(passphrase);

      // 2. Sign and register
      const regSig = await signRegistration(id.privateKey, id.publicKeyHex);
      await zkApi.register(id.publicKeyHex, regSig);

      // 3. Immediately authenticate: challenge → sign → verify → JWT
      const { nonce } = await zkApi.challenge(id.publicKeyHex);
      const authSig = await signChallenge(id.privateKey, nonce);
      const { access_token } = await zkApi.verify(id.publicKeyHex, nonce, authSig);

      // 4. Store token in sessionStorage
      sessionStorage.setItem(TOKEN_KEY, access_token);
      sessionStorage.setItem(PUBKEY_KEY, id.publicKeyHex);

      // 5. Keep identity in memory
      setIdentity(id);
      setAuth({
        token: access_token,
        isAuthenticated: true,
        publicKeyHex: id.publicKeyHex,
        isDerivingKey: false,
      });

      // 6. Upload initial prekey bundle (non-blocking)
      uploadInitialPrekeys(id);

      return id.publicKeyHex;
    } catch (e) {
      setAuth((prev) => ({ ...prev, isDerivingKey: false }));
      throw e;
    }
  }, [uploadInitialPrekeys]);

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(PUBKEY_KEY);
    setIdentity(null);
    setAuth({
      token: null,
      isAuthenticated: false,
      publicKeyHex: null,
      isDerivingKey: false,
    });
    window.location.hash = "#/";
  }, []);

  return (
    <AuthContext.Provider
      value={{
        ...auth,
        login,
        register,
        logout,
        privateKey: identity?.privateKey ?? null,
        publicKey: identity?.publicKey ?? null,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
