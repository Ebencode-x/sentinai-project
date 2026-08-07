import { createContext, useContext, useState, useCallback, ReactNode } from "react";

const TOKEN_KEY = "sentinai_session_token";
const USER_KEY = "sentinai_session_user";
const EXPIRY_KEY = "sentinai_session_expiry";

export interface SessionUser {
  email: string;
  role: "admin" | "viewer";
}

function isExpired(): boolean {
  const exp = localStorage.getItem(EXPIRY_KEY);
  if (!exp) return true;
  return Date.now() > new Date(exp).getTime();
}

function readStoredUser(): SessionUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

interface AuthContextValue {
  token: string | null;
  user: SessionUser | null;
  isAuthenticated: boolean;
  login: (token: string, user: SessionUser, expiresAt: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => {
    if (isExpired()) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(EXPIRY_KEY);
      return null;
    }
    return localStorage.getItem(TOKEN_KEY);
  });
  const [user, setUser] = useState<SessionUser | null>(() => (isExpired() ? null : readStoredUser()));

  const login = useCallback((newToken: string, newUser: SessionUser, expiresAt: string) => {
    localStorage.setItem(TOKEN_KEY, newToken);
    localStorage.setItem(USER_KEY, JSON.stringify(newUser));
    localStorage.setItem(EXPIRY_KEY, expiresAt);
    setToken(newToken);
    setUser(newUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(EXPIRY_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

export function getStoredToken(): string | null {
  if (isExpired()) return null;
  return localStorage.getItem(TOKEN_KEY);
}
