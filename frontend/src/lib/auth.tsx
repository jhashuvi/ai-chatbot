// src/lib/auth.tsx
"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { authApi, chatApi, ensureSessionId } from "@/lib/api";

type AuthState = {
  isReady: boolean;
  isAuthenticated: boolean;
  userId?: number;
  email?: string;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isReady, setIsReady] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userId, setUserId] = useState<number | undefined>(undefined);
  const [email, setEmail] = useState<string | undefined>(undefined);

  // Boot: ensure X-Session-Id and, if token exists, verify with /auth/me
  useEffect(() => {
    (async () => {
      ensureSessionId();
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("auth_token")
          : null;
      if (!token) {
        setIsReady(true);
        return;
      }
      try {
        const me = await authApi.me();
        setIsAuthenticated(true);
        setUserId(me.user_id);
        setEmail(me.email);
      } catch {
        localStorage.removeItem("auth_token");
        setIsAuthenticated(false);
        setUserId(undefined);
        setEmail(undefined);
      } finally {
        setIsReady(true);
      }
    })();
  }, []);

  const login = async (email: string, password: string) => {
    const res = await chatApi.login(email, password); // { access_token, user_id, token_type }
    if (typeof window !== "undefined") {
      localStorage.setItem("auth_token", res.access_token);
    }
    const me = await authApi.me();
    setIsAuthenticated(true);
    setUserId(me.user_id);
    setEmail(me.email);
  };

  const register = async (email: string, password: string) => {
    ensureSessionId(); // send current anon session for in-place upgrade
    const res = await chatApi.register(email, password); // { access_token, user_id, token_type, session_id }
    if (typeof window !== "undefined") {
      localStorage.setItem("auth_token", res.access_token);
      // backend echoes effective session_id; persist it
      if (res.session_id) localStorage.setItem("session_id", res.session_id);
    }
    const me = await authApi.me();
    setIsAuthenticated(true);
    setUserId(me.user_id);
    setEmail(me.email);
  };

  const logout = () => {
    authApi.logout();
    // Stay anonymous; keep session_id so chat history remains
    setIsAuthenticated(false);
    setUserId(undefined);
    setEmail(undefined);
  };

  return (
    <AuthContext.Provider
      value={{
        isReady,
        isAuthenticated,
        userId,
        email,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
