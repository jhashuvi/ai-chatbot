// src/lib/api.ts - Fixed to match your backend
import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// Add auth token and session ID to requests
api.interceptors.request.use((config) => {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  const sessionId =
    typeof window !== "undefined" ? localStorage.getItem("session_id") : null;
  if (sessionId) {
    config.headers["X-Session-Id"] = sessionId;
  }

  return config;
});

// ========== TYPES (Updated to match your backend) ==========

export interface User {
  id: number; // Your backend uses int, not string
  email?: string;
  is_authenticated?: boolean;
}

export interface ChatSession {
  id: number; // Your backend uses int
  created_at: string;
  updated_at: string;
  user_id: number;
  title?: string;
  description?: string;
  is_active: boolean;
  summary_text?: string;
  message_count: number;
  assistant_message_count: number;
  last_message_at?: string;
  ended_at?: string;
}

export interface SourceRef {
  id: string;
  title: string;
  preview: string;
  content_hash?: string;
  category?: string;
  score?: number; // Raw Pinecone score
  score_norm?: number; // Normalized confidence (0.0 to 1.0)
  confidence_bucket?: string; // "high", "medium", "low"
  rank: number;
  index_name?: string;
  namespace?: string;
  model_name?: string;
  metadata?: Record<string, any>;
}

export interface ChatMetrics {
  // Add fields based on your ChatMetrics schema
  [key: string]: any;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ChatResponse {
  answer: string; // Your backend returns "answer", not "response"
  answer_type: "grounded" | "abstained" | "fallback";
  message_id?: number;
  session_id?: number;
  sources: SourceRef[];
  metrics?: ChatMetrics;
}

export interface AuthResponse {
  user_id: number;
  access_token: string;
  token_type: string;
  session_id?: string; // For register endpoint
}

export interface HistoryResponse {
  session_id: number;
  messages: Message[];
}

// ========== API FUNCTIONS ==========

export const chatApi = {
  // Health check (fixed endpoint)
  healthCheck: async () => {
    const response = await api.get("/healthz");
    return response.data;
  },

  // Chat - requires session_id as integer
  sendMessage: async (
    message: string,
    sessionId: number
  ): Promise<ChatResponse> => {
    const requestBody = {
      session_id: sessionId, // Required integer
      message: message,
      stream: false,
      history_size: 6,
    };

    console.log("Sending chat request:", requestBody);
    const response = await api.post("/chat", requestBody);
    console.log("Chat response:", response.data);
    return response.data;
  },

  // Sessions
  createSession: async (title?: string): Promise<ChatSession> => {
    // Generate a session ID for X-Session-Id header if not exists
    if (!localStorage.getItem("session_id")) {
      localStorage.setItem(
        "session_id",
        `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      );
    }

    const response = await api.post("/sessions", { title });
    return response.data;
  },

  listSessions: async (): Promise<ChatSession[]> => {
    // Generate a session ID for X-Session-Id header if not exists
    if (!localStorage.getItem("session_id")) {
      localStorage.setItem(
        "session_id",
        `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      );
    }

    const response = await api.get("/sessions");
    return response.data.items; // Your backend returns {items: [...]}
  },

  // Chat history
  getChatHistory: async (sessionId: number): Promise<Message[]> => {
    const response = await api.get("/chat/history", {
      params: { session_id: sessionId },
    });
    return response.data.messages;
  },

  // Auth
  register: async (email: string, password: string): Promise<AuthResponse> => {
    const response = await api.post("/auth/register", { email, password });
    return response.data;
  },

  login: async (email: string, password: string): Promise<AuthResponse> => {
    const response = await api.post("/auth/login", { email, password });
    return response.data;
  },

  // Feedback
  submitFeedback: async (
    messageId: number,
    value: 1 | -1 | 0
  ): Promise<void> => {
    await api.post(`/messages/${messageId}/feedback`, { value });
  },
};

// Helper to ensure session ID exists
export const ensureSessionId = () => {
  if (typeof window !== "undefined" && !localStorage.getItem("session_id")) {
    localStorage.setItem(
      "session_id",
      `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    );
  }
};
