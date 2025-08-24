// src/types/api.ts
export interface User {
  id: string;
  email?: string;
  is_anonymous: boolean;
  created_at: string;
}

export interface ChatSession {
  id: string;
  user_id: string;
  title?: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  session_id: string;
  content: string;
  role: "user" | "assistant";
  created_at: string;
  rag_sources?: RAGSource[];
  confidence_score?: number;
  intent_category?: string;
}

export interface RAGSource {
  title: string;
  content: string;
  confidence: number;
  metadata?: Record<string, any>;
}

export interface ChatResponse {
  response: string;
  intent_category: string;
  confidence_score: number;
  rag_sources: RAGSource[];
  message_id: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}
