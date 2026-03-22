import React, { createContext, useContext, useState, useCallback } from "react";
import type { TokenResponse } from "../api/auth";

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
}

interface AuthContextValue extends AuthState {
  login: (response: TokenResponse) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(() => {
    const token = localStorage.getItem("token");
    return { token, isAuthenticated: !!token };
  });

  const login = useCallback((response: TokenResponse) => {
    localStorage.setItem("token", response.access_token);
    setAuth({ token: response.access_token, isAuthenticated: true });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setAuth({ token: null, isAuthenticated: false });
    window.location.hash = "#/";
  }, []);

  return (
    <AuthContext.Provider value={{ ...auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
