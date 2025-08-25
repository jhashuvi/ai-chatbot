// src/types/api.ts
/**
 * TypeScript type definitions for the chatbot API.
 * These interfaces match the backend API contracts and response structures.
 */

// User account information
export interface User {
  id: number;
  session_id?: string; // May not be present in /auth/me
  email?: string;
  is_authenticated: boolean;
  last_login_at?: string;
  created_at: string;
  updated_at: string;
}

// Chat session information
export interface ChatSession {
  id: number;
  title?: string;
  description?: string;
  summary_text?: string;
  is_active: boolean;
  message_count: number;
  assistant_message_count: number;
  last_message_at?: string; // Optional to match real payloads
  ended_at?: string;
  user_id: number;
  created_at: string;
  updated_at: string;
}

// Source reference for RAG citations
// Matches schemas/common.SourceRef (all optional except id)
export interface SourceRef {
  id: string;
  category?: string;
  score?: number;
  title?: string;
  preview?: string;
  content_hash?: string;
  rank?: number;
  score_norm?: number;
  confidence_bucket?: "high" | "medium" | "low";
  index_name?: string;
  namespace?: string;
  model_name?: string;
  // Backend SourceRef doesn't define `metadata`; omit to avoid assumptions
}

// Complete message with all metadata
export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  chat_session_id: number;

  // Assistant-only optional metadata
  sources?: SourceRef[];
  retrieval_params?: Record<string, any>;
  retrieval_stats?: Record<string, any>;
  context_policy?: Record<string, any>;
  answer_type?: "grounded" | "abstained" | "fallback";
  error_type?: string;
  citations?: Record<string, any>;

  // Usage and performance metrics
  model_used?: string;
  model_provider?: string;
  tokens_in?: number;
  tokens_out?: number;
  tokens_used?: number;
  latency_ms?: number;
  retrieval_score?: number;

  // Feedback and moderation
  user_feedback?: number; // -1 | 0 | 1
  flagged: boolean;

  created_at: string;
  updated_at: string;
}

// Simplified message shape for chat history
// Narrow shape returned by GET /chat/history
export interface HistoryItem {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

// Chat history response wrapper
export interface HistoryResponse {
  session_id: number;
  messages: HistoryItem[]; // Not full Message objects
}

// Response from sending a message to the chatbot
export interface ChatResponse {
  answer: string;
  answer_type: "grounded" | "abstained" | "fallback";
  message_id?: number;
  session_id?: number;
  sources: SourceRef[];
  metrics?: Record<string, any>;
}

// Authentication response from login/register
export interface AuthResponse {
  user_id: number;
  access_token: string;
  token_type: string;
  session_id?: string; // Returned on /auth/register
}

// Registration response (always includes session_id)
export interface RegisterResponse {
  user_id: number;
  access_token: string;
  token_type: string; // "bearer"
  session_id: string; // Always returned by /auth/register
}

// Login response (no session_id)
export interface LoginResponse {
  user_id: number;
  access_token: string;
  token_type: string; // "bearer"
}

// Current user information from /auth/me
export interface MeResponse {
  user_id: number;
  email?: string;
  is_authenticated: boolean;
}

// Sessions list wrapper and summary
// Used by /sessions and /sessions/summary endpoints
export interface ListSessionsResponse {
  items: ChatSession[];
  next_cursor: string | null;
}

// Summary statistics for all sessions
export interface SessionsSummary {
  total_sessions: number;
  active_sessions: number;
  total_messages: number;
  average_messages_per_session: number;
}
