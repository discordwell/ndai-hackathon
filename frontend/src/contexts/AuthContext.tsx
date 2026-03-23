import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import type { TokenResponse } from "../api/types";

interface AuthState {
  token: string | null;
  role: string | null;
  displayName: string | null;
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
    const role = localStorage.getItem("role");
    const displayName = localStorage.getItem("displayName");
    return { token, role, displayName, isAuthenticated: !!token };
  });

  const login = useCallback((response: TokenResponse) => {
    localStorage.setItem("token", response.access_token);
    localStorage.setItem("role", response.role);
    if ((response as any).display_name) {
      localStorage.setItem("displayName", (response as any).display_name);
    }
    setAuth({
      token: response.access_token,
      role: response.role,
      displayName: (response as any).display_name || null,
      isAuthenticated: true,
    });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("displayName");
    setAuth({ token: null, role: null, displayName: null, isAuthenticated: false });
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
