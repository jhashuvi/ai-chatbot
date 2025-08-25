// src/lib/auth.tsx
/**
 * Authentication context provider for managing user authentication state.
 */
"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { authApi, chatApi, ensureSessionId } from "@/lib/api";

// Authentication state interface
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

/**
 * Authentication provider component that wraps the app
 * and provides authentication state and methods to all children.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Authentication state management
  const [isReady, setIsReady] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userId, setUserId] = useState<number | undefined>(undefined);
  const [email, setEmail] = useState<string | undefined>(undefined);

  // Initialize authentication state on app startup
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
        // Verify token with backend and get user info
        const me = await authApi.me();
        setIsAuthenticated(true);
        setUserId(me.user_id);
        setEmail(me.email);
      } catch {
        // Token is invalid, clear it and stay anonymous
        localStorage.removeItem("auth_token");
        setIsAuthenticated(false);
        setUserId(undefined);
        setEmail(undefined);
      } finally {
        setIsReady(true);
      }
    })();
  }, []);

  /**
   * Login user with email and password
   */
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

  /**
   * Register new user account
   */
  const register = async (email: string, password: string) => {
    ensureSessionId(); // Send current anon session for in-place upgrade
    const res = await chatApi.register(email, password);
    if (typeof window !== "undefined") {
      localStorage.setItem("auth_token", res.access_token);
      if (res.session_id) localStorage.setItem("session_id", res.session_id);
    }
    const me = await authApi.me();
    setIsAuthenticated(true);
    setUserId(me.user_id);
    setEmail(me.email);
  };

  /**
   * Logout user and return to anonymous state
   */
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

/**
 * Hook to access authentication context
 * Must be used within AuthProvider component
 */
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
