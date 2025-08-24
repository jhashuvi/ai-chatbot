// src/components/ChatInterface.tsx - Updated to show RAG sources
"use client";

import React, { useState, useRef, useEffect } from "react";
import { chatApi, ensureSessionId } from "@/lib/api";
import type { ChatSession, ChatResponse } from "@/lib/api";
import MessageBubble from "./MessageBubble";
import { Send } from "lucide-react";

interface ExtendedMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  ragResponse?: ChatResponse; // Store full RAG response for assistant messages
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<ExtendedMessage[]>([]);
  const [currentMessage, setCurrentMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(
    null
  );
  const [error, setError] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Initialize session on component mount
  useEffect(() => {
    initializeSession();
  }, []);

  const initializeSession = async () => {
    try {
      ensureSessionId();
      const session = await chatApi.createSession("New Chat");
      setCurrentSession(session);
      console.log("Initialized session:", session);
    } catch (error) {
      console.error("Failed to initialize session:", error);
      setError("Failed to initialize chat session");
    }
  };

  const sendMessage = async () => {
    if (!currentMessage.trim() || !currentSession || isLoading) return;

    const userMessage: ExtendedMessage = {
      id: Date.now(),
      role: "user",
      content: currentMessage,
      created_at: new Date().toISOString(),
    };

    // Add user message immediately
    setMessages((prev) => [...prev, userMessage]);
    const messageToSend = currentMessage;
    setCurrentMessage("");
    setIsLoading(true);
    setError("");

    try {
      // Send to backend
      const response = await chatApi.sendMessage(
        messageToSend,
        currentSession.id
      );
      console.log("Full RAG response:", response);

      // Add assistant response with full RAG data
      const assistantMessage: ExtendedMessage = {
        id: response.message_id || Date.now() + 1,
        role: "assistant",
        content: response.answer,
        created_at: new Date().toISOString(),
        ragResponse: response, // Store full RAG response for the MessageBubble
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error: any) {
      console.error("Failed to send message:", error);
      setError("Failed to send message. Please try again.");

      // Add error message
      const errorMessage: ExtendedMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">AI Assistant</h1>
          {currentSession && (
            <div className="text-sm text-gray-500">
              Session: {currentSession.title} (ID: {currentSession.id})
            </div>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="max-w-4xl mx-auto">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center min-h-[60vh]">
              <div className="text-center max-w-2xl mx-auto px-4">
                {/* Gradient background with subtle animation */}
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
                  {/* Subtle glow effect */}
                  <div className="absolute inset-0 w-20 h-20 bg-gradient-to-br from-blue-400 to-purple-500 rounded-2xl mx-auto blur-xl opacity-20 animate-pulse"></div>
                </div>

                {/* Modern typography with gradient text */}
                <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-gray-800 to-gray-900 bg-clip-text text-transparent mb-4">
                  How can I help you today?
                </h1>

                <p className="text-lg text-gray-600 mb-8 leading-relaxed font-light">
                  I'm here to assist you with questions about our services,
                  accounts, and policies. Just start typing below to get
                  started.
                </p>

                {/* Subtle call-to-action with icon */}
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
                  <span className="text-sm font-medium">Ask me anything</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  ragResponse={message.ragResponse}
                />
              ))}
            </div>
          )}

          {/* Loading indicator */}
          {isLoading && (
            <div className="flex justify-start mb-6">
              <div className="flex space-x-3">
                <div className="w-8 h-8 rounded-full bg-gray-700 text-white flex items-center justify-center">
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                    />
                  </svg>
                </div>
                <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3 shadow-sm">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"></div>
                    <div
                      className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"
                      style={{ animationDelay: "0.2s" }}
                    ></div>
                    <div
                      className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"
                      style={{ animationDelay: "0.4s" }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="px-6 py-2">
          <div className="max-w-4xl mx-auto bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
            {error}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="bg-white border-t border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex space-x-3">
            <div className="flex-1 relative">
              <textarea
                value={currentMessage}
                onChange={(e) => setCurrentMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me anything about our services..."
                disabled={isLoading}
                className="w-full resize-none border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 placeholder-gray-500"
                rows={1}
                style={{
                  minHeight: "50px",
                  maxHeight: "150px",
                }}
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
  );
}
