// src/components/AuthModal.tsx
"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth";

interface Props {
  open: boolean;
  onClose: () => void;
  mode?: "login" | "register";
}

export default function AuthModal({ open, onClose, mode = "login" }: Props) {
  const { login, register } = useAuth();
  const [view, setView] = useState<"login" | "register">(mode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const submit = async () => {
    setErr(null);
    setLoading(true);
    try {
      if (view === "login") await login(email, password);
      else await register(email, password);
      onClose();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-5 shadow-lg">
        <h2 className="text-lg font-semibold mb-4">
          {view === "login" ? "Sign in" : "Create an account"}
        </h2>
        <div className="space-y-3">
          <input
            type="email"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
          <input
            type="password"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={
              view === "login" ? "current-password" : "new-password"
            }
          />
          {err && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {err}
            </div>
          )}
          <button
            onClick={submit}
            disabled={loading || !email || !password}
            className="w-full rounded-lg bg-blue-600 px-3 py-2 font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
          >
            {loading
              ? "Please wait..."
              : view === "login"
              ? "Sign in"
              : "Create account"}
          </button>
          <button
            onClick={onClose}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
        <div className="mt-4 text-center text-sm text-gray-600">
          {view === "login" ? (
            <>
              Don’t have an account?{" "}
              <button
                className="text-blue-600 hover:underline"
                onClick={() => setView("register")}
              >
                Create one
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                className="text-blue-600 hover:underline"
                onClick={() => setView("login")}
              >
                Sign in
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
