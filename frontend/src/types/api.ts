// src/types/api.ts — aligned with your backend contracts

export interface User {
  id: number;
  session_id?: string; // may not be present in /auth/me
  email?: string;
  is_authenticated: boolean;
  last_login_at?: string;
  created_at: string;
  updated_at: string;
}

// src/types/api.ts
export interface ChatSession {
  id: number;
  title?: string;
  description?: string;
  summary_text?: string;
  is_active: boolean;
  message_count: number;
  assistant_message_count: number;
  last_message_at?: string; // <-- make optional to match real payloads
  ended_at?: string;
  user_id: number;
  created_at: string;
  updated_at: string;
}

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
  // (Backend SourceRef doesn't define `metadata`; omit to avoid assumptions)
}

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

  // Usage/perf
  model_used?: string;
  model_provider?: string;
  tokens_in?: number;
  tokens_out?: number;
  tokens_used?: number;
  latency_ms?: number;
  retrieval_score?: number;

  // Feedback/moderation
  user_feedback?: number; // -1 | 0 | 1
  flagged: boolean;

  created_at: string;
  updated_at: string;
}

// Narrow shape returned by GET /chat/history
export interface HistoryItem {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface HistoryResponse {
  session_id: number;
  messages: HistoryItem[]; // not full Message[]
}

export interface ChatResponse {
  answer: string;
  answer_type: "grounded" | "abstained" | "fallback";
  message_id?: number;
  session_id?: number;
  sources: SourceRef[];
  metrics?: Record<string, any>;
}

export interface AuthResponse {
  user_id: number;
  access_token: string;
  token_type: string;
  session_id?: string; // returned on /auth/register
}

// Sessions list wrapper and summary (used by /sessions and /sessions/summary)
export interface ListSessionsResponse {
  items: ChatSession[];
  next_cursor: string | null;
}

export interface SessionsSummary {
  total_sessions: number;
  active_sessions: number;
  total_messages: number;
  average_messages_per_session: number;
}
