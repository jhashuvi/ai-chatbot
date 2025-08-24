// src/app/page.tsx - Updated test to match your backend
"use client";

import { useState } from "react";
import { chatApi, ensureSessionId } from "@/lib/api";
import type { ChatSession } from "@/lib/api";

export default function TestPage() {
  const [message, setMessage] = useState("What is fintech?");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(
    null
  );

  const testFullFlow = async () => {
    try {
      setLoading(true);
      setError("");
      setResponse("");

      console.log("=== TESTING FULL BACKEND FLOW ===");

      // Step 1: Health check
      console.log("1. Testing health check...");
      const health = await chatApi.healthCheck();
      console.log("✅ Health check result:", health);

      // Step 2: Ensure session ID exists
      console.log("2. Ensuring session ID...");
      ensureSessionId();
      const sessionId = localStorage.getItem("session_id");
      console.log("✅ Session ID:", sessionId);

      // Step 3: Create a new chat session
      console.log("3. Creating chat session...");
      const session = await chatApi.createSession("Test Session");
      console.log("✅ Created session:", session);
      setCurrentSession(session);

      // Step 4: Send chat message (requires session.id as integer)
      console.log("4. Sending chat message...");
      const chatResult = await chatApi.sendMessage(message, session.id);
      console.log("✅ Chat result:", chatResult);

      // Step 5: Get chat history
      console.log("5. Getting chat history...");
      const history = await chatApi.getChatHistory(session.id);
      console.log("✅ Chat history:", history);

      // Display success
      setResponse(
        JSON.stringify(
          {
            health,
            session,
            chatResult,
            history,
          },
          null,
          2
        )
      );
    } catch (err: any) {
      console.error("❌ API Error:", err);
      console.error("Error response:", err.response?.data);
      setError(
        `${err.response?.status || "Unknown"}: ${
          err.response?.data?.detail || err.message
        }`
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">
          🚀 Backend API Full Flow Test
        </h1>

        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Test Message:
            </label>
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="What is fintech?"
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <button
            onClick={testFullFlow}
            disabled={loading}
            className="w-full bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {loading
              ? "🔄 Testing Full Flow..."
              : "🧪 Test Complete Backend Flow"}
          </button>

          {currentSession && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <strong>Current Session:</strong> {currentSession.title} (ID:{" "}
              {currentSession.id})
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">
              <strong>❌ Error:</strong> {error}
              <details className="mt-2">
                <summary className="cursor-pointer text-sm">Debug Info</summary>
                <pre className="text-xs mt-2 overflow-x-auto">
                  Check browser console for detailed logs
                </pre>
              </details>
            </div>
          )}

          {response && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <strong>✅ Success! Complete Backend Response:</strong>
              <pre className="mt-2 text-xs overflow-x-auto bg-white p-3 rounded border">
                {response}
              </pre>

              <div className="mt-4 text-sm text-green-800">
                <strong>What worked:</strong>
                <ul className="list-disc list-inside mt-1">
                  <li>✅ Health check endpoint</li>
                  <li>✅ Session creation with X-Session-Id header</li>
                  <li>✅ Chat endpoint with proper request format</li>
                  <li>✅ RAG response with sources and confidence</li>
                  <li>✅ Chat history retrieval</li>
                </ul>
              </div>
            </div>
          )}
        </div>

        <div className="mt-6 text-sm text-gray-600">
          <strong>This test covers:</strong>
          <ul className="list-disc list-inside mt-2 space-y-1">
            <li>
              <code>GET /healthz</code> - Health check
            </li>
            <li>
              <code>POST /sessions</code> - Create chat session
            </li>
            <li>
              <code>POST /chat</code> - Send message with RAG
            </li>
            <li>
              <code>GET /chat/history</code> - Get conversation history
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
