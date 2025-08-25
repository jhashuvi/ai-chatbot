// src/components/Sidebar.tsx
/**
 * Sidebar component for chat session management and user authentication.
 * Displays session list, new chat button, and user account controls.
 */
"use client";

import React from "react";
import { Plus, MessageSquare, User, LogOut, Menu } from "lucide-react";
import type { ChatSession } from "@/types/api";
import { useAuth } from "@/lib/auth";
import AuthModal from "./AuthModal";

interface SidebarProps {
  sessions: ChatSession[];
  currentSession: ChatSession | null;
  onSelectSession: (session: ChatSession) => void;
  onNewSession: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

export default function Sidebar({
  sessions,
  currentSession,
  onSelectSession,
  onNewSession,
  isOpen,
  onToggle,
}: SidebarProps) {
  // Authentication state and actions
  const { isAuthenticated, email, logout } = useAuth();
  const [authOpen, setAuthOpen] = React.useState(false);

  /**
   * Get display title for a session, fallback to "New chat" if empty
   */
  const titleFor = (s: ChatSession) =>
    s.title?.trim() ? s.title.trim() : "New chat";

  return (
    <>
      {/* Mobile backdrop overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onToggle}
        />
      )}

      {/* Main sidebar container */}
      <div
        className={`fixed lg:static inset-y-0 left-0 z-50 w-80 transform transition-transform duration-300 ease-in-out
        ${isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        bg-gray-900 text-white flex flex-col`}
      >
        {/* Sidebar header with title and new chat button */}
        <div className="p-4 border-b border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-lg font-semibold">AI Assistant</h1>
            {/* Mobile menu toggle button */}
            <button
              onClick={onToggle}
              className="lg:hidden p-1 rounded-md hover:bg-gray-800 transition-colors"
              aria-label="Toggle sidebar"
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>

          {/* New chat creation button */}
          <button
            onClick={onNewSession}
            className="w-full flex items-center space-x-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors font-medium"
          >
            <Plus className="h-4 w-4" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Scrollable sessions list */}
        <div className="flex-1 overflow-y-auto py-4">
          {sessions.length === 0 ? (
            // Empty state when no sessions exist
            <div className="px-4 py-8 text-center">
              <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-40" />
              <p className="text-sm text-gray-400">No conversations yet</p>
            </div>
          ) : (
            // List of chat sessions
            <div className="px-2 space-y-1">
              {sessions.map((s) => {
                const active = currentSession?.id === s.id;
                return (
                  <button
                    key={s.id}
                    onClick={() => onSelectSession(s)}
                    className={`w-full text-left px-3 py-2 rounded-lg transition-colors relative ${
                      active
                        ? "bg-gray-800 text-white"
                        : "text-gray-300 hover:bg-gray-800 hover:text-white"
                    }`}
                    title={titleFor(s)}
                  >
                    <div className="flex items-center space-x-3">
                      <MessageSquare className="h-4 w-4 flex-shrink-0 opacity-60" />
                      <div className="truncate text-sm font-medium">
                        {titleFor(s)}
                      </div>
                    </div>
                    {/* Active session indicator */}
                    {active && (
                      <div className="absolute left-0 inset-y-0 w-1 bg-blue-500 rounded-r" />
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer with user authentication controls */}
        <div className="border-t border-gray-700 p-4 space-y-2">
          {/* Sign in/account button */}
          <button
            className="w-full flex items-center space-x-3 px-3 py-2 text-gray-300 hover:bg-gray-800 hover:text-white rounded-lg transition-colors text-sm"
            onClick={() => setAuthOpen(true)}
          >
            <User className="h-4 w-4" />
            <span>
              {isAuthenticated ? email || "Account" : "Sign in / Register"}
            </span>
          </button>

          {/* Sign out button (only shown when authenticated) */}
          {isAuthenticated && (
            <button
              className="w-full flex items-center space-x-3 px-3 py-2 text-gray-300 hover:bg-gray-800 hover:text-white rounded-lg transition-colors text-sm"
              onClick={logout}
            >
              <LogOut className="h-4 w-4" />
              <span>Sign out</span>
            </button>
          )}
        </div>
      </div>

      {/* Authentication modal */}
      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />
    </>
  );
}
