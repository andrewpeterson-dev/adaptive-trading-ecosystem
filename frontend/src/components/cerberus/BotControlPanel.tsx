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
  DeployConfigModal,
  type DeployConfig,
} from "@/components/bots/DeployConfigModal";
import {
  Bot,
  Play,
  Square,
  RefreshCw,
  Rocket,
  Activity,
  Loader2,
  ArrowRight,
  ClipboardCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { useTradingMode } from "@/hooks/useTradingMode";
import { useCerberusWorkspaceStatus } from "@/hooks/useCerberusWorkspaceStatus";

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
  const { mode } = useTradingMode();
  const { status } = useCerberusWorkspaceStatus(mode);
  const { toast } = useToast();
  const [bots, setBots] = useState<BotSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deployTarget, setDeployTarget] = useState<BotSummary | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const fetchBots = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const data = await listBots();
      setBots(data);
    } catch (error) {
      console.error("Failed to load bots:", error);
      setLoadError(
        error instanceof Error ? error.message : "Failed to load bots"
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBots();
  }, [fetchBots]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchBots();
      setLastUpdated(new Date());
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchBots]);

  // Tick every 10s to keep the "updated X seconds ago" label fresh
  const [, setTick] = useState(0);
  useEffect(() => {
    const ticker = setInterval(() => setTick((t) => t + 1), 10000);
    return () => clearInterval(ticker);
  }, []);

  const handleDeployClick = (bot: BotSummary) => {
    setDeployTarget(bot);
  };

  const handleDeployConfirm = async (config: DeployConfig) => {
    if (!deployTarget) return;
    const bot = deployTarget;
    setActioningId(bot.id);
    try {
      await deployBot(
        bot.id,
        config.universeConfig as unknown as Record<string, unknown>,
        config.overrideLevel,
        config.allocatedCapital,
      );
      setBots((prev) =>
        prev.map((item) =>
          item.id === bot.id ? { ...item, status: "running" } : item
        )
      );
      toast(
        bot.status === "paused" ? `${bot.name} resumed` : `${bot.name} deployed`,
        "success"
      );
      setDeployTarget(null);
    } catch (error) {
      console.error("Deploy error:", error);
      const actionLabel = bot.status === "paused" ? "resume" : "deploy";
      const message =
        error instanceof Error ? error.message : `Failed to ${actionLabel} bot`;
      toast(`Failed to ${actionLabel} ${bot.name}: ${message}`, "error");
    } finally {
      setActioningId(null);
    }
  };

  const handleStop = async (bot: BotSummary) => {
    if (!confirm("Stop bot? This will cancel any pending orders and halt signal monitoring.")) return;
    setActioningId(bot.id);
    try {
      await stopBot(bot.id);
      setBots((prev) =>
        prev.map((item) =>
          item.id === bot.id ? { ...item, status: "stopped" } : item
        )
      );
      toast(`${bot.name} stopped`, "success");
    } catch (error) {
      console.error("Stop error:", error);
      const message =
        error instanceof Error ? error.message : "Failed to stop bot";
      toast(`Failed to stop ${bot.name}: ${message}`, "error");
    } finally {
      setActioningId(null);
    }
  };

  const runningCount = bots.filter((bot) => bot.status === "running").length;

  return (
    <div className="flex h-full flex-col space-y-4 overflow-y-auto p-4 sm:p-5">
      <div className="rounded-[24px] border border-border/60 bg-muted/20 p-4">
        <div className="flex flex-col gap-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="app-label">Deploy Strategy</p>
              <h3 className="mt-2 text-lg font-semibold text-foreground">
                Move a saved strategy into the Cerberus bot fleet
              </h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Deploying here creates a bot version, registers it with Cerberus, and exposes execution controls. It does not place a trade on its own.
              </p>
            </div>
            <Button asChild variant="primary" size="sm">
              <Link href="/strategies">
                Deploy strategy
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
          <div className="grid gap-2 rounded-[20px] border border-border/60 bg-background/60 p-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <ClipboardCheck className="h-3.5 w-3.5 text-primary" />
              Saved strategy
            </div>
            <div className="flex items-center gap-2">
              <ClipboardCheck className={`h-3.5 w-3.5 ${status?.marketDataConnected ? "text-emerald-400" : "text-amber-400"}`} />
              {status?.marketDataConnected
                ? "Market data connected"
                : "Market data connection recommended before deploying"}
            </div>
            <div className="flex items-center gap-2">
              <ClipboardCheck className={`h-3.5 w-3.5 ${status?.portfolioConnected ? "text-emerald-400" : "text-amber-400"}`} />
              {status?.portfolioConnected
                ? "Broker connection available"
                : "Broker connection required for live execution later"}
            </div>
          </div>
        </div>
      </div>

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
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            Updated {Math.round((Date.now() - lastUpdated.getTime()) / 1000) < 5 ? "just now" : `${Math.round((Date.now() - lastUpdated.getTime()) / 1000)}s ago`}
          </span>
          <Button variant="secondary" size="sm" onClick={() => { fetchBots(); setLastUpdated(new Date()); }} disabled={isLoading}>
            {isLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Refresh
          </Button>
        </div>
      </div>

      {loadError && (
        <div className="rounded-2xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">
          {loadError}
        </div>
      )}

      {bots.length === 0 && !isLoading && (
        <EmptyState
          icon={<Bot className="h-5 w-5 text-muted-foreground" />}
          title="No bots deployed yet"
          description="Deploy a saved strategy to create a bot with live learning telemetry, deployable versions, and execution controls."
          action={
            <Button asChild variant="primary" size="sm">
              <Link href="/strategies">Deploy strategy</Link>
            </Button>
          }
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
                        {bot.status === "running" && (
                          <span className="mr-1.5 h-2 w-2 rounded-full bg-emerald-400 animate-pulse-dot inline-block" />
                        )}
                        {bot.status}
                      </Badge>
                      {bot.latestDecision && (
                        <>
                          <Badge
                            variant={
                              bot.latestDecision.ai_confidence > 0.7
                                ? "positive"
                                : bot.latestDecision.ai_confidence >= 0.4
                                  ? "warning"
                                  : "negative"
                            }
                          >
                            AI {(bot.latestDecision.ai_confidence * 100).toFixed(0)}%
                          </Badge>
                          <Badge
                            variant={
                              bot.latestDecision.context_risk_level === "LOW"
                                ? "positive"
                                : bot.latestDecision.context_risk_level === "MEDIUM"
                                  ? "warning"
                                  : "negative"
                            }
                          >
                            {bot.latestDecision.context_risk_level.toLowerCase()} risk
                          </Badge>
                        </>
                      )}
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
                          bot.allocatedCapital
                            ? `$${bot.allocatedCapital.toLocaleString()}`
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
                          void handleDeployClick(bot);
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
                      <button
                        className="rounded-full bg-red-500 px-4 py-2 text-sm font-semibold text-white hover:bg-red-600 transition-colors inline-flex items-center gap-2 disabled:opacity-50 disabled:pointer-events-none"
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
                      </button>
                    )}
                    {bot.status === "paused" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleDeployClick(bot);
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

                <div className="grid gap-3 rounded-[20px] border border-border/70 bg-muted/30 p-4 md:grid-cols-4">
                  <div>
                    <p className="app-label">P&L</p>
                    <p className={`mt-2 font-mono text-lg ${(bot.performance.total_net_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      ${(bot.performance.total_net_pnl ?? 0).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="app-label">Trades</p>
                    <p className="mt-2 font-mono text-lg text-foreground">
                      {bot.performance.trade_count ?? 0}
                      {bot.performance.open_count
                        ? ` (${bot.performance.open_count} open)`
                        : ""}
                    </p>
                  </div>
                  <div>
                    <p className="app-label">Win Rate</p>
                    <p className="mt-2 font-mono text-lg text-foreground">
                      {bot.performance.closed_count
                        ? `${(bot.performance.win_rate * 100).toFixed(0)}%`
                        : "N/A"}
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

      <DeployConfigModal
        open={deployTarget !== null}
        onClose={() => setDeployTarget(null)}
        onDeploy={(config) => void handleDeployConfirm(config)}
        botName={deployTarget?.name}
        isDeploying={actioningId !== null}
      />
    </div>
  );
}
