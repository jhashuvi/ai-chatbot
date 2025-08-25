// src/components/MessageBubble.tsx
/**
 * Message bubble component for displaying chat messages.
 * Shows user and assistant messages with metadata, sources, and feedback options.
 */
"use client";

import React, { useState } from "react";
import {
  User,
  Bot,
  ChevronDown,
  ChevronUp,
  Shield,
  CheckCircle,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import type { Message, SourceRef, HistoryItem } from "@/types/api";
import { chatApi } from "@/lib/api";

type ChatTurn = HistoryItem & Partial<Message>;

interface MessageBubbleProps {
  message: ChatTurn;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  // Component state for UI interactions
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [feedback, setFeedback] = useState<number | null>(
    message.user_feedback ?? null
  );
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  // Determine if message is from user or assistant
  const isUser = message.role === "user";

  const sources = message.sources ?? [];
  const answerType = message.answer_type;
  const hasRAGData = sources.length > 0 || !!answerType;

  // Show only top 5 most relevant sources to avoid clutter --> product sense!
  const visibleSources = React.useMemo(
    () => (sources ?? []).slice(0, 5),
    [sources]
  );

  /**
   * Handle user feedback submission (thumbs up/down)
   */
  const handleFeedback = async (value: 1 | -1 | 0) => {
    if (submittingFeedback || !message.id || isUser) return; // assistant only
    try {
      setSubmittingFeedback(true);
      await chatApi.submitFeedback(message.id, value);
      setFeedback(value === 0 ? null : value);
    } catch (error) {
      console.error("Failed to submit feedback:", error);
    } finally {
      setSubmittingFeedback(false);
    }
  };

  /**
   * Get color styling for confidence levels
   */
  const getConfidenceColor = (source: SourceRef) => {
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

  /**
   * Format confidence score for display
   */
  const formatConfidence = (source: SourceRef) => {
    if (typeof source.score_norm === "number") {
      return `${Math.round(source.score_norm * 100)}%`;
    }
    if (source.confidence_bucket) {
      const bucketMap: Record<
        NonNullable<SourceRef["confidence_bucket"]>,
        string
      > = {
        high: "90%",
        medium: "70%",
        low: "40%",
      };
      return bucketMap[source.confidence_bucket];
    }
    return "N/A";
  };

  /**
   * Get styling and label for answer types
   */
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
        {/* User/Assistant avatar */}
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

        {/* Message content and metadata */}
        <div className="flex-1 min-w-0">
          {/* Message text */}
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

          {/* Assistant message metadata and sources */}
          {!isUser && hasRAGData && (
            <div className="mt-3 space-y-2">
              {/* Metadata row with answer type, timestamp, and feedback */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {/* Answer type indicator */}
                  {answerTypeInfo && (
                    <div
                      className={`inline-flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium ${answerTypeInfo.color}`}
                    >
                      <answerTypeInfo.icon className="w-3 h-3" />
                      <span>{answerTypeInfo.label}</span>
                    </div>
                  )}
                  {/* Timestamp */}
                  <div className="text-xs text-gray-500">
                    {new Date(message.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                  {/* Response latency */}
                  {typeof message.latency_ms === "number" && (
                    <div className="text-xs text-gray-500">
                      {Math.round(message.latency_ms)}ms
                    </div>
                  )}
                  {/* Error indicator */}
                  {message.error_type && (
                    <div className="text-xs text-red-500 bg-red-50 px-2 py-1 rounded">
                      Error: {message.error_type}
                    </div>
                  )}
                </div>

                {/* Feedback buttons */}
                <div className="flex items-center space-x-1">
                  <button
                    onClick={() => handleFeedback(1)}
                    disabled={submittingFeedback}
                    className={`p-1 rounded hover:bg-gray-100 transition-colors ${
                      feedback === 1
                        ? "text-green-600"
                        : "text-gray-400 hover:text-green-600"
                    }`}
                    title="Helpful"
                  >
                    <ThumbsUp className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleFeedback(-1)}
                    disabled={submittingFeedback}
                    className={`p-1 rounded hover:bg-gray-100 transition-colors ${
                      feedback === -1
                        ? "text-red-600"
                        : "text-gray-400 hover:text-red-600"
                    }`}
                    title="Not helpful"
                  >
                    <ThumbsDown className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Expandable sources section */}
              {visibleSources.length > 0 && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg overflow-hidden">
                  {/* Sources toggle button */}
                  <button
                    onClick={() => setSourcesExpanded((v) => !v)}
                    className="w-full px-4 py-3 text-left hover:bg-gray-100 transition-colors flex items-center justify-between"
                  >
                    <div className="flex items-center space-x-2">
                      <Shield className="w-4 h-4 text-blue-600" />
                      <span className="text-sm font-medium text-gray-900">
                        {visibleSources.length}
                        {sources.length > 5 ? ` of ${sources.length}` : ""} most
                        relevant source
                        {visibleSources.length !== 1 ? "s" : ""}
                      </span>
                    </div>
                    {sourcesExpanded ? (
                      <ChevronUp className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-gray-500" />
                    )}
                  </button>

                  {/* Expanded sources list */}
                  {sourcesExpanded && (
                    <div className="border-t border-gray-200 bg-white">
                      <div className="p-4 space-y-3">
                        {visibleSources.map((source, i) => (
                          <div
                            key={source.id ?? i}
                            className="border border-gray-200 rounded-lg p-3 bg-gray-50"
                          >
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex-1">
                                {/* Source title and category */}
                                <h4 className="text-sm font-medium text-gray-900">
                                  {source.title || `Source ${i + 1}`}
                                </h4>
                                {source.category && (
                                  <div className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded mt-1 inline-block">
                                    {source.category}
                                  </div>
                                )}
                              </div>
                              {/* Confidence score */}
                              <div className="ml-2 flex items-center space-x-2">
                                <div
                                  className={`px-2 py-1 rounded-full text-xs font-medium border ${getConfidenceColor(
                                    source
                                  )}`}
                                >
                                  {formatConfidence(source)}
                                </div>
                              </div>
                            </div>

                            {/* Source preview text */}
                            <p className="text-xs text-gray-600 leading-relaxed mb-2">
                              {source.preview || "No preview available"}
                            </p>
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
