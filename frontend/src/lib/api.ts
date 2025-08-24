// src/lib/api.ts
import axios from "axios";

// Re-export the canonical types from src/types/api so callers can import from either place.
export type {
  ChatSession,
  HistoryItem,
  HistoryResponse,
  Message,
  SourceRef,
  ChatResponse,
  AuthResponse,
  ListSessionsResponse,
  SessionsSummary,
} from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Attach Authorization and X-Session-Id headers
api.interceptors.request.use((config) => {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  const sessionId =
    typeof window !== "undefined" ? localStorage.getItem("session_id") : null;
  if (sessionId) {
    // exact header name as backend expects (convert_underscores=False)
    config.headers["X-Session-Id"] = sessionId;
  }
  return config;
});

// ---------- API FUNCTIONS ----------

export const chatApi = {
  // Health
  healthCheck: async () => {
    const { data } = await api.get("/healthz");
    return data;
  },

  // Chat
  sendMessage: async (message: string, sessionId: number) => {
    const body = {
      session_id: sessionId,
      message,
      // backend has defaults; these are fine but optional:
      stream: false,
      history_size: 6,
    };
    const { data } = await api.post("/chat", body);
    return data as import("@/types/api").ChatResponse;
  },

  // Sessions
  createSession: async () => {
    ensureSessionId();
    const { data } = await api.post("/sessions", {}); // no title
    return data as import("@/types/api").ChatSession;
  },

  listSessions: async () => {
    ensureSessionId();
    const { data } = await api.get("/sessions");
    // backend returns { items: ChatSession[], next_cursor: null }
    return (data.items ?? []) as import("@/types/api").ChatSession[];
  },

  getSessionsSummary: async () => {
    ensureSessionId();
    const { data } = await api.get("/sessions/summary");
    return data as import("@/types/api").SessionsSummary;
  },

  // Chat history
  getChatHistory: async (sessionId: number) => {
    const { data } = await api.get("/chat/history", {
      params: { session_id: sessionId, limit: 100 },
    });
    return data.messages as import("@/types/api").HistoryItem[];
  },

  // Auth
  register: async (email: string, password: string) => {
    ensureSessionId(); // upgrade anonymous → authenticated in place
    const { data } = await api.post("/auth/register", { email, password });
    return data as import("@/types/api").AuthResponse;
  },

  login: async (email: string, password: string) => {
    const { data } = await api.post("/auth/login", { email, password });
    return data as import("@/types/api").AuthResponse;
  },

  // Feedback (204 No Content)
  submitFeedback: async (messageId: number, value: -1 | 0 | 1) => {
    await api.post(`/messages/${messageId}/feedback`, { value });
  },
};

// Ensure a browser session id exists (used for X-Session-Id)
export const ensureSessionId = () => {
  if (typeof window !== "undefined" && !localStorage.getItem("session_id")) {
    localStorage.setItem(
      "session_id",
      `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
    );
  }
};
