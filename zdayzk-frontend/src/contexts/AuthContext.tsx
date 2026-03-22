import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from "react";
import type { UserProfile } from "../api/types";
import * as authApi from "../api/auth";
import { TOKEN_KEY } from "../api/client";

interface AuthContextValue {
  isAuthenticated: boolean;
  user: UserProfile | null;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    displayName?: string
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => !!localStorage.getItem(TOKEN_KEY)
  );

  // Fetch user profile on mount if token exists
  useEffect(() => {
    if (!isAuthenticated) return;
    authApi
      .getMe()
      .then((profile) => setUser(profile))
      .catch(() => {
        // Token is invalid — clear it
        localStorage.removeItem(TOKEN_KEY);
        setIsAuthenticated(false);
        setUser(null);
      });
  }, [isAuthenticated]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login(email, password);
    localStorage.setItem(TOKEN_KEY, res.access_token);
    setIsAuthenticated(true);
    const profile = await authApi.getMe();
    setUser(profile);
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const res = await authApi.register(email, password, displayName);
      localStorage.setItem(TOKEN_KEY, res.access_token);
      setIsAuthenticated(true);
      const profile = await authApi.getMe();
      setUser(profile);
    },
    []
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setIsAuthenticated(false);
    setUser(null);
    window.location.hash = "#/login";
  }, []);

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, user, login, register, logout }}
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
