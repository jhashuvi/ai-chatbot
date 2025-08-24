// src/components/MessageBubble.tsx - Enhanced message with RAG sources
"use client";

import React, { useState } from "react";
import {
  User,
  Bot,
  ChevronDown,
  ChevronUp,
  Shield,
  CheckCircle,
} from "lucide-react";
import type { SourceRef, ChatResponse } from "@/lib/api";

interface ExtendedMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  // RAG-specific fields from your backend
  sources?: SourceRef[];
  answer_type?: "grounded" | "abstained" | "fallback";
  metrics?: any;
}

interface MessageBubbleProps {
  message: ExtendedMessage;
  ragResponse?: ChatResponse; // Full response from backend for assistant messages
}

export default function MessageBubble({
  message,
  ragResponse,
}: MessageBubbleProps) {
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const isUser = message.role === "user";

  // Get sources and metadata from either message or ragResponse
  const sources = ragResponse?.sources || message.sources || [];
  const answerType = ragResponse?.answer_type || message.answer_type;
  const hasRAGData = sources.length > 0 || answerType;

  const getConfidenceColor = (source: SourceRef) => {
    // Use confidence_bucket for color coding
    switch (source.confidence_bucket) {
      case "high":
        return "text-green-600 bg-green-50 border-green-200";
      case "medium":
        return "text-yellow-600 bg-yellow-50 border-yellow-200";
      case "low":
        return "text-red-600 bg-red-50 border-red-200";
      default:
        return "text-gray-600 bg-gray-50 border-gray-200";
    }
  };

  const formatConfidence = (source: SourceRef) => {
    // Use score_norm for percentage display
    if (source.score_norm !== undefined && source.score_norm !== null) {
      return `${Math.round(source.score_norm * 100)}%`;
    }
    // Fallback to confidence_bucket
    if (source.confidence_bucket) {
      const bucketMap: Record<string, string> = {
        high: "90%",
        medium: "70%",
        low: "40%",
      };
      return bucketMap[source.confidence_bucket] || "N/A";
    }
    return "N/A";
  };

  const getAnswerTypeInfo = (type?: string) => {
    switch (type) {
      case "grounded":
        return {
          label: "Source-backed answer",
          color: "text-green-600 bg-green-50",
          icon: CheckCircle,
        };
      case "abstained":
        return {
          label: "Insufficient information",
          color: "text-yellow-600 bg-yellow-50",
          icon: Shield,
        };
      case "fallback":
        return {
          label: "General response",
          color: "text-blue-600 bg-blue-50",
          icon: Bot,
        };
      default:
        return null;
    }
  };

  const answerTypeInfo = getAnswerTypeInfo(answerType);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-6`}>
      <div
        className={`flex max-w-3xl ${
          isUser ? "flex-row-reverse" : "flex-row"
        } space-x-3`}
      >
        {/* Avatar */}
        <div className={`flex-shrink-0 ${isUser ? "ml-3" : "mr-3"}`}>
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center ${
              isUser ? "bg-blue-600 text-white" : "bg-gray-700 text-white"
            }`}
          >
            {isUser ? (
              <User className="h-4 w-4" />
            ) : (
              <Bot className="h-4 w-4" />
            )}
          </div>
        </div>

        {/* Message Content */}
        <div className="flex-1 min-w-0">
          {/* Main Message Bubble */}
          <div
            className={`rounded-2xl px-4 py-3 ${
              isUser
                ? "bg-blue-600 text-white"
                : "bg-white border border-gray-200 text-gray-900 shadow-sm"
            }`}
          >
            <div className="prose prose-sm max-w-none">
              <p className="whitespace-pre-wrap leading-relaxed m-0">
                {message.content}
              </p>
            </div>
          </div>

          {/* Assistant Message Metadata */}
          {!isUser && hasRAGData && (
            <div className="mt-3 space-y-2">
              {/* Answer Type Badge */}
              {answerTypeInfo && (
                <div className="flex items-center space-x-2">
                  <div
                    className={`inline-flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium ${answerTypeInfo.color}`}
                  >
                    <answerTypeInfo.icon className="w-3 h-3" />
                    <span>{answerTypeInfo.label}</span>
                  </div>
                  <div className="text-xs text-gray-500">
                    {new Date(message.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                </div>
              )}

              {/* Sources Section */}
              {sources.length > 0 && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setSourcesExpanded(!sourcesExpanded)}
                    className="w-full px-4 py-3 text-left hover:bg-gray-100 transition-colors flex items-center justify-between"
                  >
                    <div className="flex items-center space-x-2">
                      <Shield className="w-4 h-4 text-blue-600" />
                      <span className="text-sm font-medium text-gray-900">
                        {sources.length} source{sources.length !== 1 ? "s" : ""}{" "}
                        found
                      </span>
                    </div>
                    {sourcesExpanded ? (
                      <ChevronUp className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-gray-500" />
                    )}
                  </button>

                  {/* Expandable Sources */}
                  {sourcesExpanded && (
                    <div className="border-t border-gray-200 bg-white">
                      <div className="p-4 space-y-3">
                        {sources.map((source, index) => (
                          <div
                            key={index}
                            className="border border-gray-200 rounded-lg p-3 bg-gray-50"
                          >
                            <div className="flex items-start justify-between mb-2">
                              <h4 className="text-sm font-medium text-gray-900 flex-1">
                                {source.title || `Source ${index + 1}`}
                              </h4>
                              <div
                                className={`ml-2 px-2 py-1 rounded-full text-xs font-medium border ${getConfidenceColor(
                                  source
                                )}`}
                              >
                                {formatConfidence(source)}
                              </div>
                            </div>
                            <p className="text-xs text-gray-600 line-clamp-3 leading-relaxed">
                              {source.preview || "No preview available"}
                            </p>
                            {source.metadata &&
                              Object.keys(source.metadata).length > 0 && (
                                <div className="mt-2 text-xs text-gray-500">
                                  <details>
                                    <summary className="cursor-pointer hover:text-gray-700">
                                      Metadata
                                    </summary>
                                    <pre className="mt-1 text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                                      {JSON.stringify(source.metadata, null, 2)}
                                    </pre>
                                  </details>
                                </div>
                              )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
