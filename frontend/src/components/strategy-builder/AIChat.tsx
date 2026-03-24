"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import { useBuilderStore } from "@/stores/builder-store";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, Sparkles, Zap, TrendingUp, BarChart3, Shield, RefreshCw } from "lucide-react";

// Chat message type
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  strategyName?: string;
  createdAt: string;
}

// Suggestion chips
const SUGGESTIONS = [
  { label: "RSI mean reversion on SPY", icon: TrendingUp },
  { label: "Momentum breakout with volume confirmation", icon: Zap },
  { label: "Conservative EMA crossover strategy", icon: BarChart3 },
  { label: "High-frequency scalping on QQQ", icon: Sparkles },
  { label: "Volatility expansion breakout", icon: Shield },
];

export default function AIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isGenerating]);

  const handleGenerate = async (prompt?: string) => {
    const text = (prompt || input).trim();
    if (!text || isGenerating) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsGenerating(true);
    setError(null);

    try {
      const result = await apiFetch<{
        strategy_spec: Record<string, unknown>;
        builder_draft: Record<string, unknown>;
        compiled_strategy: Record<string, unknown>;
        validation_warnings?: string[];
      }>("/api/strategies/generate", {
        method: "POST",
        body: JSON.stringify({ prompt: text }),
      });

      // Load the generated strategy into the builder store
      const spec = result.strategy_spec as any;
      if (spec) {
        // Use loadFromSpec which expects the StrategySpec format
        const { parseStrategySpec } = await import("@/lib/strategy-spec");
        const parsed = parseStrategySpec(JSON.stringify(spec));
        if (parsed.ok) {
          useBuilderStore.getState().loadFromSpec(parsed.spec);
          useBuilderStore.getState().setField("strategyType", "ai_generated");
          useBuilderStore.getState().setField("sourcePrompt", text);
        }
      }

      // Build assistant response
      const strategyName = spec?.name || "Generated Strategy";
      const overview = spec?.overview || spec?.description || "";
      const assumptions = (spec?.assumptions as string[]) || [];
      const warnings = result.validation_warnings || [];

      let responseContent = `**${strategyName}**\n\n${overview}`;

      if (assumptions.length > 0) {
        responseContent += `\n\n**Assumptions:**\n${assumptions.map((a: string) => `- ${a}`).join("\n")}`;
      }

      if (warnings.length > 0) {
        responseContent += `\n\n**Warnings:**\n${warnings.map((w: string) => `- ${w}`).join("\n")}`;
      }

      responseContent += `\n\n*Strategy loaded into the builder. Review the preview panel on the right, then save or deploy.*`;

      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: responseContent,
        strategyName,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Generation failed";
      setError(detail);
      const errMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Generation failed: ${detail}\n\nTry rephrasing your strategy description or being more specific about the indicators and timeframe you want.`,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-6 px-6 max-w-lg">
              {/* Hero icon */}
              <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/20 flex items-center justify-center">
                <Sparkles className="w-8 h-8 text-blue-400" />
              </div>

              <div>
                <h2 className="text-xl font-bold text-foreground">AI Strategy Builder</h2>
                <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
                  Describe your trading idea in plain English. The AI will generate entry/exit conditions, risk controls, and a complete strategy you can review and deploy.
                </p>
              </div>

              {/* Suggestion chips */}
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Try one of these</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s.label}
                      onClick={() => handleGenerate(s.label)}
                      className="group flex items-center gap-2 rounded-xl border border-border/60 bg-card/50 px-3 py-2 text-xs text-muted-foreground hover:border-blue-500/40 hover:text-blue-400 hover:bg-blue-500/5 transition-all"
                    >
                      <s.icon className="w-3.5 h-3.5 text-muted-foreground/50 group-hover:text-blue-400 transition-colors" />
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <span className={`text-xs mb-1 font-medium ${msg.role === "user" ? "text-muted-foreground" : "text-blue-400"}`}>
              {msg.role === "user" ? "You" : "AI Builder"}
            </span>
            <div
              className={
                msg.role === "user"
                  ? "ml-auto max-w-[85%] bg-slate-800 rounded-2xl p-4 text-sm"
                  : "max-w-[85%] bg-slate-900/80 border border-blue-900/30 rounded-2xl p-4 text-sm"
              }
            >
              {msg.role === "assistant" ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
                    strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                    em: ({ children }) => <em className="text-muted-foreground italic">{children}</em>,
                    code: ({ children, className }) => {
                      const isInline = !className;
                      return isInline ? (
                        <code className="bg-slate-800 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>
                      ) : (
                        <code className={`block bg-slate-800 p-3 rounded-lg text-xs overflow-x-auto mb-2 font-mono ${className ?? ""}`}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              ) : (
                <p className="leading-relaxed">{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        {/* Generating indicator */}
        {isGenerating && (
          <div className="flex flex-col items-start">
            <span className="text-xs mb-1 font-medium text-blue-400">AI Builder</span>
            <div className="max-w-[85%] bg-slate-900/80 border border-blue-900/30 rounded-2xl p-4 text-sm">
              <div className="flex items-center gap-3">
                <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />
                <span className="text-muted-foreground">Generating strategy...</span>
              </div>
            </div>
          </div>
        )}

        {error && !messages.some(m => m.content.includes("Generation failed")) && (
          <div className="text-xs text-red-400 text-center py-1">{error}</div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-border p-4 bg-card/30">
        <div className="relative max-w-3xl mx-auto">
          <textarea
            className="w-full resize-none rounded-2xl border border-border bg-background px-4 py-3 pr-14 text-sm placeholder:text-muted-foreground/60 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 focus:outline-none transition-colors"
            rows={3}
            placeholder="Describe your strategy — e.g. &quot;Build a momentum strategy on AAPL using RSI and MACD with 2% stop loss&quot;"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isGenerating}
          />
          <button
            className="absolute right-3 bottom-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-muted disabled:text-muted-foreground p-2.5 text-white transition-colors"
            onClick={() => handleGenerate()}
            disabled={isGenerating || !input.trim()}
            aria-label="Generate strategy"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1.5 text-center">
          Enter to generate &middot; Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
