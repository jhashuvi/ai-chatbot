// src/components/ChatInterface.tsx
"use client";

import React, { useEffect, useRef, useState } from "react";
import { chatApi, ensureSessionId } from "@/lib/api";
import MessageBubble from "./MessageBubble";
import Sidebar from "./Sidebar";
import { Send, Menu, X } from "lucide-react";

import type {
  ChatResponse,
  HistoryItem,
  Message,
  SourceRef,
  ChatSession,
} from "@/types/api";

// A flexible item that can be either a minimal HistoryItem
// or a richer Message produced optimistically after sends.
type ChatTurn = HistoryItem & Partial<Message>;

type ViewState = "booting" | "switching" | "ready";

const ACTIVE_SESSION_KEY = "active_session_id";

export default function ChatInterface() {
  const [viewState, setViewState] = useState<ViewState>("booting");
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(
    null
  );
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ---- Helpers: persist/restore active session id ----
  const saveActiveSessionId = (id: number) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(ACTIVE_SESSION_KEY, String(id));
    }
  };
  const loadActiveSessionId = (): number | null => {
    if (typeof window === "undefined") return null;
    const raw = localStorage.getItem(ACTIVE_SESSION_KEY);
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  };

  // ---- Scroll to bottom on new messages ----
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ---- Boot: ensure session header, fetch sessions, select one, load history ----
  useEffect(() => {
    (async () => {
      try {
        setViewState("booting");
        ensureSessionId();

        const list = await chatApi.listSessions();
        setSessions(list);

        let selected: ChatSession | null = null;
        const preferred = loadActiveSessionId();

        if (preferred) {
          selected = list.find((s) => s.id === preferred) ?? null;
        }
        if (!selected) {
          if (list.length > 0) {
            selected = list[0];
          } else {
            // No sessions: create the first one (no title)
            selected = await chatApi.createSession();
            setSessions([selected]);
          }
        }

        setCurrentSession(selected);
        saveActiveSessionId(selected.id);

        // Load history for selected session
        const history = await chatApi.getChatHistory(selected.id);
        setMessages(history);
        setViewState("ready");
      } catch (err: any) {
        console.error("Boot error:", err);
        setError(
          err?.response?.data?.detail ||
            err?.message ||
            "Failed to load sessions"
        );
        setViewState("ready"); // show empty state with error
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- Switch session (keep current view until swapped) ----
  const selectSession = async (session: ChatSession) => {
    if (currentSession?.id === session.id) {
      setSidebarOpen(false);
      return;
    }
    try {
      setSidebarOpen(false);
      setViewState("switching");
      setError("");
      setCurrentSession(session);
      saveActiveSessionId(session.id);

      const history = await chatApi.getChatHistory(session.id);
      setMessages(history); // swap atomically
      setViewState("ready");
    } catch (err: any) {
      console.error("Failed to load chat history:", err);
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to load chat history"
      );
      setMessages([]); // safe fallback
      setViewState("ready");
    }
  };

  // ---- Create new session ----
  const createNewSession = async () => {
    try {
      setError("");
      const s = await chatApi.createSession(); // no title
      setSessions((prev) => [s, ...prev]);
      await selectSession(s);
    } catch (err: any) {
      console.error("Failed to create session:", err);
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to create session"
      );
    }
  };

  // Make a nice title candidate from the user’s first message
  const makeTitleCandidate = (raw: string) => {
    let candidate = raw.trim().replace(/\s+/g, " ");
    if (candidate.length > 60) {
      const head = candidate.slice(0, 60);
      const cut = head.lastIndexOf(" ");
      candidate = cut >= 30 ? head.slice(0, cut) : head;
    }
    return candidate
      ? candidate[0].toUpperCase() + candidate.slice(1)
      : "New chat";
  };

  // ---- Send message (optimistic UI) ----
  const sendMessage = async () => {
    if (!currentMessage.trim() || !currentSession || isLoading) return;

    const nowISO = new Date().toISOString();
    const tempUserId = Date.now();

    // Optimistic user turn
    const userTurn: ChatTurn = {
      id: tempUserId,
      role: "user",
      content: currentMessage,
      created_at: nowISO,
    };
    setMessages((prev) => [...prev, userTurn]);

    // Optimistically update title if empty
    if (
      !currentSession.title ||
      currentSession.title.toLowerCase() === "new chat"
    ) {
      const candidate = makeTitleCandidate(currentMessage);
      setCurrentSession((s) => (s ? { ...s, title: candidate } : s));
      setSessions((prev) =>
        prev.map((s) =>
          s.id === currentSession.id ? { ...s, title: candidate } : s
        )
      );
    }

    const toSend = currentMessage;
    setCurrentMessage("");
    setIsLoading(true);
    setError("");

    try {
      const resp: ChatResponse = await chatApi.sendMessage(
        toSend,
        currentSession.id
      );

      const assistantTurn: ChatTurn = {
        id: resp.message_id || tempUserId + 1,
        role: "assistant",
        content: resp.answer,
        created_at: new Date().toISOString(),
        // Optional RAG bits for rendering
        sources: (resp.sources as SourceRef[]) || [],
        answer_type: resp.answer_type,
        retrieval_stats: resp.metrics || undefined,
      };

      setMessages((prev) => [...prev, assistantTurn]);

      // Nudge list recency in UI (backend maintains truth)
      setSessions((prev) =>
        prev.map((s) =>
          s.id === currentSession.id
            ? {
                ...s,
                message_count: (s.message_count || 0) + 2,
                assistant_message_count: (s.assistant_message_count || 0) + 1,
                last_message_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              }
            : s
        )
      );
    } catch (err: any) {
      console.error("Failed to send message:", err);
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to send message. Please try again.";
      setError(msg);

      const errorTurn: ChatTurn = {
        id: Date.now() + 1,
        role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        created_at: new Date().toISOString(),
        error_type: "frontend_error",
      };
      setMessages((prev) => [...prev, errorTurn]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Convert a ChatTurn to a Message-like shape for MessageBubble
  const toMessageLike = (m: ChatTurn): Message => ({
    id: m.id,
    role: m.role,
    content: m.content,
    chat_session_id: currentSession?.id ?? 0,
    created_at: m.created_at,
    updated_at: m.updated_at ?? m.created_at,
    flagged: m.flagged ?? false,
    sources: m.sources,
    retrieval_params: m.retrieval_params,
    retrieval_stats: m.retrieval_stats,
    context_policy: m.context_policy,
    answer_type: m.answer_type,
    error_type: m.error_type,
    citations: m.citations,
    model_used: m.model_used,
    model_provider: m.model_provider,
    tokens_in: m.tokens_in,
    tokens_out: m.tokens_out,
    tokens_used: m.tokens_used,
    latency_ms: m.latency_ms,
    retrieval_score: m.retrieval_score,
    user_feedback: m.user_feedback,
  });

  // Render condition flags
  const showEmptyHero = viewState === "ready" && messages.length === 0;
  const showThinking = isLoading || viewState === "switching";

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        currentSession={currentSession}
        onSelectSession={selectSession}
        onNewSession={createNewSession}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="lg:hidden p-1 rounded-md hover:bg-gray-100 transition-colors"
            >
              {sidebarOpen ? (
                <X className="h-5 w-5 text-gray-600" />
              ) : (
                <Menu className="h-5 w-5 text-gray-600" />
              )}
            </button>
            <h1 className="text-lg font-semibold text-gray-900">
              {currentSession
                ? currentSession.title?.trim() || "New chat"
                : "AI Assistant"}
            </h1>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-4 lg:px-6 py-4">
          <div className="max-w-4xl mx-auto relative">
            {showEmptyHero ? (
              <div className="flex items-center justify-center min-h-[60vh]">
                <div className="text-center max-w-2xl mx-auto px-4">
                  <div className="relative mb-8">
                    <div className="w-20 h-20 bg-gradient-to-br from-blue-500 via-blue-600 to-purple-600 rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-blue-500/25 animate-pulse">
                      <svg
                        className="w-10 h-10 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                        />
                      </svg>
                    </div>
                    <div className="absolute inset-0 w-20 h-20 bg-gradient-to-br from-blue-400 to-purple-500 rounded-2xl mx-auto blur-xl opacity-20 animate-pulse" />
                  </div>

                  <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-gray-800 to-gray-900 bg-clip-text text-transparent mb-4">
                    How can I help you today?
                  </h1>

                  <p className="text-lg text-gray-600 mb-8 leading-relaxed font-light">
                    Ask about accounts, transactions, policies, or docs. I’ll
                    pull relevant sources and explain clearly.
                  </p>

                  <div className="flex items-center justify-center space-x-2 text-gray-500">
                    <svg
                      className="w-4 h-4 text-blue-500"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 10V3L4 14h7v7l9-11h-7z"
                      />
                    </svg>
                    <span className="text-sm font-medium">
                      Press Enter to send, Shift+Enter for newline
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-1">
                {messages.map((m) => (
                  <MessageBubble key={m.id} message={toMessageLike(m)} />
                ))}
                {viewState === "switching" && (
                  <div className="absolute inset-0 bg-white/40 backdrop-blur-[1px] pointer-events-none" />
                )}
              </div>
            )}

            {showThinking && !showEmptyHero && (
              <div className="flex justify-start mb-6 mt-3">
                <div className="flex space-x-3">
                  <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3 shadow-sm">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"></div>
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"
                        style={{ animationDelay: "0.2s" }}
                      />
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"
                        style={{ animationDelay: "0.4s" }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {error && (
          <div className="px-4 lg:px-6 py-2">
            <div className="max-w-4xl mx-auto bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
              {error}
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="bg-white border-t border-gray-200 px-4 lg:px-6 py-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex space-x-3">
              <div className="flex-1 relative">
                <textarea
                  value={currentMessage}
                  onChange={(e) => setCurrentMessage(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask me anything about our fintech services..."
                  disabled={isLoading}
                  className="w-full resize-none border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 placeholder-gray-500"
                  rows={1}
                  style={{ minHeight: "50px", maxHeight: "150px" }}
                />
              </div>
              <button
                onClick={sendMessage}
                disabled={!currentMessage.trim() || isLoading}
                className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center space-x-2 font-medium transition-colors shadow-sm"
              >
                <Send className="h-4 w-4" />
                <span>{isLoading ? "Sending..." : "Send"}</span>
              </button>
            </div>
            <div className="text-xs text-gray-500 mt-2 text-center">
              Press Enter to send, Shift+Enter for new line
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
