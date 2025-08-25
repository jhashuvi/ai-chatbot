// src/lib/api.ts
/**
 * API client for communicating with the backend chatbot service.
 */
import axios from "axios";

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

// Create axios instance with base configuration
const api = axios.create({
  baseURL: API_BASE_URL,
});

// Authentication API functions
export const authApi = {
  /**
   * Get current user information
   */
  me: async () => {
    const res = await api.get("/auth/me");
    return res.data as {
      user_id: number;
      email?: string;
      is_authenticated: boolean;
    };
  },
  /**
   * Logout user and clear auth token
   */
  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("auth_token");
    }
  },
};

// Request interceptor to add authentication and session headers
api.interceptors.request.use((config) => {
  // Add Authorization header if auth token exists
  const token =
    typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Add session ID header for tracking chat sessions
  const sessionId =
    typeof window !== "undefined" ? localStorage.getItem("session_id") : null;
  if (sessionId) {
    // Exact header name as backend expects (convert_underscores=False)
    config.headers["X-Session-Id"] = sessionId;
  }
  return config;
});

// ---------- Chat API Functions ----------

export const chatApi = {
  /**
   * Check if the backend service is healthy
   */
  healthCheck: async () => {
    const { data } = await api.get("/healthz");
    return data;
  },

  /**
   * Send a message to the chatbot
   */
  sendMessage: async (message: string, sessionId: number) => {
    const body = {
      session_id: sessionId,
      message,
      stream: false,
      history_size: 6,
    };
    const { data } = await api.post("/chat", body);
    return data as import("@/types/api").ChatResponse;
  },

  /**
   * Create a new chat session
   */
  createSession: async () => {
    ensureSessionId();
    const { data } = await api.post("/sessions", {}); // No title initially
    return data as import("@/types/api").ChatSession;
  },

  /**
   * Get list of all chat sessions
   */
  listSessions: async () => {
    ensureSessionId();
    const { data } = await api.get("/sessions");
    // Backend returns { items: ChatSession[], next_cursor: null }
    return (data.items ?? []) as import("@/types/api").ChatSession[];
  },

  /**
   * Get summary statistics for all sessions
   */
  getSessionsSummary: async () => {
    ensureSessionId();
    const { data } = await api.get("/sessions/summary");
    return data as import("@/types/api").SessionsSummary;
  },

  /**
   * Get chat history for a specific session
   */
  getChatHistory: async (sessionId: number) => {
    const { data } = await api.get("/chat/history", {
      params: { session_id: sessionId, limit: 100 },
    });
    return data.messages as import("@/types/api").HistoryItem[];
  },

  /**
   * Register a new user account
   */
  register: async (email: string, password: string) => {
    ensureSessionId(); // Upgrade anonymous → authenticated in place
    const { data } = await api.post("/auth/register", { email, password });
    return data as import("@/types/api").AuthResponse;
  },

  /**
   * Login with existing credentials
   */
  login: async (email: string, password: string) => {
    const { data } = await api.post("/auth/login", { email, password });
    return data as import("@/types/api").AuthResponse;
  },

  /**
   * Submit feedback for a specific message
   */
  submitFeedback: async (messageId: number, value: -1 | 0 | 1) => {
    await api.post(`/messages/${messageId}/feedback`, { value });
  },
};

/**
 * Ensure a browser session ID exists for tracking anonymous users.
 * Used for X-Session-Id header in API requests.
 */
export const ensureSessionId = () => {
  if (typeof window !== "undefined" && !localStorage.getItem("session_id")) {
    localStorage.setItem(
      "session_id",
      `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
    );
  }
};
