"use client";

import { useEffect, useRef, useState } from "react";
import { sendChatMessage } from "@/lib/cerberus-api";
import { parseStrategySpec } from "@/lib/strategy-spec";
import { useBuilderStore } from "@/stores/builder-store";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send } from "lucide-react";
import type { PageContext } from "@/types/cerberus";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages or loading state change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // ---------------------------------------------------------------------------
  // Send handler
  // ---------------------------------------------------------------------------

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);
    setError(null);

    const pageContext: PageContext = {
      currentPage: "strategy-builder",
      route: "/strategy-builder",
      visibleComponents: ["AIChat", "StrategyPreview"],
      focusedComponent: "AIChat",
      selectedSymbol: null,
      selectedAccountId: null,
      selectedBotId: null,
      componentState: {},
    };

    try {
      const response = await sendChatMessage({
        threadId: activeThreadId || undefined,
        mode: "strategy",
        message: text,
        pageContext,
      });

      if (!activeThreadId && response.threadId) {
        setActiveThreadId(response.threadId);
      }

      const markdown: string = response.message?.markdown || "";
      const assistantMsg: ChatMessage = {
        id: response.turnId || crypto.randomUUID(),
        role: "assistant",
        content: markdown,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Try to extract strategy JSON from the response
      const parsed = parseStrategySpec(markdown);
      if (parsed.ok) {
        useBuilderStore.getState().loadFromSpec(parsed.spec);
        useBuilderStore.getState().setField("strategyType", "ai_generated");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get response");
      const errMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Key handler
  // ---------------------------------------------------------------------------

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full">
      {/* ---- Messages area ---- */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Describe your trading strategy idea and I&apos;ll help you build it.
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <span
              className={`text-xs mb-1 ${
                msg.role === "user" ? "text-muted-foreground" : "text-blue-400"
              }`}
            >
              {msg.role === "user" ? "You" : "Cerberus"}
            </span>
            <div
              className={
                msg.role === "user"
                  ? "ml-auto max-w-[85%] bg-slate-800 rounded-xl p-3 px-4 text-sm"
                  : "max-w-[85%] bg-slate-900 border border-blue-900/50 rounded-xl p-3 px-4 text-sm"
              }
            >
              {msg.role === "assistant" ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-4 mb-2">{children}</ol>,
                    code: ({ children, className }) => {
                      const isInline = !className;
                      return isInline ? (
                        <code className="bg-slate-800 px-1 py-0.5 rounded text-xs">{children}</code>
                      ) : (
                        <code className={`block bg-slate-800 p-2 rounded text-xs overflow-x-auto mb-2 ${className ?? ""}`}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isLoading && (
          <div className="flex flex-col items-start">
            <span className="text-xs mb-1 text-blue-400">Cerberus</span>
            <div className="max-w-[85%] bg-slate-900 border border-blue-900/50 rounded-xl p-3 px-4 text-sm">
              <div className="flex space-x-1">
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div className="text-xs text-red-400 text-center py-1">{error}</div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ---- Input area ---- */}
      <div className="border-t border-slate-700 p-3">
        <div className="flex items-end gap-2">
          <textarea
            className="app-input w-full resize-none"
            rows={2}
            placeholder="Describe your trading strategy..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            className="app-button-primary shrink-0 p-2"
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            aria-label="Send message"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
