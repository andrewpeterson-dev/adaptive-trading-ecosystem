"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  listBots,
  deployBot,
  stopBot,
  type BotSummary,
} from "@/lib/cerberus-api";
import {
  Bot,
  Play,
  Square,
  RefreshCw,
  Rocket,
  Activity,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

const STATUS_COLOR: Record<
  string,
  "positive" | "warning" | "neutral" | "info" | "negative"
> = {
  running: "positive",
  draft: "warning",
  stopped: "neutral",
  paused: "info",
  error: "negative",
};

export function BotControlPanel() {
  const router = useRouter();
  const [bots, setBots] = useState<BotSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [actioningId, setActioningId] = useState<string | null>(null);

  const fetchBots = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listBots();
      setBots(data);
    } catch (error) {
      console.error("Failed to load bots:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBots();
  }, [fetchBots]);

  const handleDeploy = async (bot: BotSummary) => {
    setActioningId(bot.id);
    try {
      await deployBot(bot.id);
      setBots((prev) =>
        prev.map((item) =>
          item.id === bot.id ? { ...item, status: "running" } : item
        )
      );
    } catch (error) {
      console.error("Deploy error:", error);
    } finally {
      setActioningId(null);
    }
  };

  const handleStop = async (bot: BotSummary) => {
    setActioningId(bot.id);
    try {
      await stopBot(bot.id);
      setBots((prev) =>
        prev.map((item) =>
          item.id === bot.id ? { ...item, status: "stopped" } : item
        )
      );
    } catch (error) {
      console.error("Stop error:", error);
    } finally {
      setActioningId(null);
    }
  };

  const runningCount = bots.filter((bot) => bot.status === "running").length;

  return (
    <div className="flex h-full flex-col space-y-4 overflow-y-auto p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="app-label">Fleet</p>
          <h3 className="mt-2 text-lg font-semibold text-foreground">Your bots</h3>
          {bots.length > 0 && (
            <p className="mt-1 text-sm text-muted-foreground">
              {runningCount} running across {bots.length} configured bot
              {bots.length !== 1 ? "s" : ""}
            </p>
          )}
        </div>
        <Button variant="secondary" size="sm" onClick={fetchBots} disabled={isLoading}>
          {isLoading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Refresh
        </Button>
      </div>

      {bots.length === 0 && !isLoading && (
        <EmptyState
          icon={<Bot className="h-5 w-5 text-muted-foreground" />}
          title="No bots deployed yet"
          description="Deploy a saved strategy to create a bot with live learning telemetry and execution controls."
        />
      )}

      {bots.length > 0 && (
        <div className="grid gap-4">
          {bots.map((bot) => (
            <article
              key={bot.id}
              onClick={() => router.push(`/bots/${bot.id}`)}
              className="app-card cursor-pointer p-4 transition-colors hover:border-sky-400/25 hover:bg-white/90 dark:hover:bg-slate-950/80 sm:p-5"
            >
              <div className="space-y-4">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="text-base font-semibold text-foreground">{bot.name}</h4>
                      <Badge variant={STATUS_COLOR[bot.status] || "neutral"}>
                        {bot.status}
                      </Badge>
                    </div>
                    {bot.config && (
                      <p className="font-mono text-xs text-muted-foreground">
                        {[
                          (bot.config.action as string) || "",
                          (bot.config.timeframe as string) || "",
                          Array.isArray(bot.config.symbols) &&
                          (bot.config.symbols as string[]).length > 0
                            ? (bot.config.symbols as string[]).slice(0, 3).join(", ")
                            : "",
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    )}
                    <p className="text-sm leading-6 text-muted-foreground">
                      {bot.overview || "No natural-language overview has been generated yet."}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {(bot.status === "draft" || bot.status === "stopped") && (
                      <Button
                        variant="success"
                        size="sm"
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleDeploy(bot);
                        }}
                        disabled={actioningId === bot.id}
                      >
                        {actioningId === bot.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Rocket className="h-3.5 w-3.5" />
                        )}
                        Deploy
                      </Button>
                    )}
                    {bot.status === "running" && (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleStop(bot);
                        }}
                        disabled={actioningId === bot.id}
                      >
                        {actioningId === bot.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Square className="h-3.5 w-3.5" />
                        )}
                        Stop
                      </Button>
                    )}
                    {bot.status === "paused" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleDeploy(bot);
                        }}
                        disabled={actioningId === bot.id}
                      >
                        <Play className="h-3.5 w-3.5" />
                        Resume
                      </Button>
                    )}
                    <Button asChild variant="secondary" size="sm">
                      <Link
                        href={`/bots/${bot.id}`}
                        onClick={(event) => {
                          event.stopPropagation();
                        }}
                      >
                        <Activity className="h-3.5 w-3.5" />
                        Details
                      </Link>
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 rounded-[20px] border border-border/70 bg-muted/30 p-4 md:grid-cols-3">
                  <div>
                    <p className="app-label">Win Rate</p>
                    <p className="mt-2 font-mono text-lg text-foreground">
                      {(bot.performance.win_rate * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div>
                    <p className="app-label">Sharpe</p>
                    <p className="mt-2 font-mono text-lg text-foreground">
                      {bot.performance.sharpe_ratio.toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="app-label">Learning</p>
                    <p className="mt-2 text-lg font-semibold text-emerald-300">
                      {bot.learningStatus.status}
                    </p>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
