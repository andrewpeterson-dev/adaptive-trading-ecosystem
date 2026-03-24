"use client";

import { useState } from "react";
import { BrainCircuit, DollarSign, Pencil, Check, X, Shield, Sparkles, Target, TrendingUp } from "lucide-react";

import type { BotDetail, BotTrade } from "@/lib/cerberus-api";
import { updateBotCapital, updateAiCapitalManagement } from "@/lib/cerberus-api";
import {
  formatCurrency,
  formatPercent,
  formatTimeframe,
  getAiOverview,
  getBotConfig,
  getTrackedSymbols,
  humanizeLabel,
  summarizeRisk,
} from "@/lib/bot-visualization";

interface BotDetailPanelProps {
  detail: BotDetail;
  activeSymbol: string;
  onSymbolSelect: (symbol: string) => void;
  selectedTrade: BotTrade | null;
  onDetailUpdate?: (updates: Partial<BotDetail>) => void;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 px-3 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-sm text-foreground">{value}</div>
    </div>
  );
}

export function BotDetailPanel({
  detail,
  activeSymbol,
  onSymbolSelect,
  selectedTrade,
  onDetailUpdate,
}: BotDetailPanelProps) {
  const config = getBotConfig(detail);
  const aiContext = (config.ai_context ?? {}) as Record<string, unknown>;
  const assets = getTrackedSymbols(detail);
  const assumptions = Array.isArray(aiContext.assumptions)
    ? aiContext.assumptions.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];

  const positionSize = formatPercent(config.position_size_pct as number | null | undefined, 1, true);
  const stopLoss = formatPercent(config.stop_loss_pct as number | null | undefined, 1, true);
  const takeProfit = formatPercent(config.take_profit_pct as number | null | undefined, 1, true);
  const maxExposure = formatPercent(config.max_exposure_pct as number | null | undefined, 0, true);
  const maxLoss = formatPercent(config.max_loss_pct as number | null | undefined, 1, true);
  const riskPosture = summarizeRisk(config);

  // Capital editing state
  const [isEditingCapital, setIsEditingCapital] = useState(false);
  const [capitalInput, setCapitalInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleEditCapital = () => {
    setCapitalInput(detail.allocatedCapital ? String(detail.allocatedCapital) : "");
    setIsEditingCapital(true);
  };

  const handleSaveCapital = async () => {
    setIsSaving(true);
    setSaveError(null);
    try {
      const parsed = capitalInput.trim() ? parseFloat(capitalInput.replace(/[,$]/g, "")) : null;
      const value = parsed && !isNaN(parsed) && parsed > 0 ? parsed : null;
      await updateBotCapital(detail.id, value);
      onDetailUpdate?.({ allocatedCapital: value });
      setIsEditingCapital(false);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save capital");
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleAiCapital = async () => {
    const newValue = !detail.aiCapitalManagement;
    setSaveError(null);
    try {
      await updateAiCapitalManagement(detail.id, newValue);
      onDetailUpdate?.({ aiCapitalManagement: newValue });
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to toggle AI capital");
    }
  };

  return (
    <section className="app-panel h-full p-5 sm:p-6">
      <div className="mb-5 flex items-start gap-3">
        <div className="rounded-2xl bg-sky-500/10 p-3 text-sky-400">
          <BrainCircuit className="h-5 w-5" />
        </div>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Bot Detail Panel
          </div>
          <h2 className="mt-1 text-xl font-semibold text-foreground">{detail.name}</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail.overview || "No strategy summary recorded."}</p>
        </div>
      </div>

      {/* ── Capital Allocation ──────────────────────────────────────── */}
      <div className="mb-5">
        <div className="mb-3 flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-emerald-400" />
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Capital Allocation
          </div>
        </div>
        <div className="rounded-[22px] border border-border/60 bg-muted/15 p-4 space-y-3">
          {isEditingCapital ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">$</span>
              <input
                type="text"
                inputMode="decimal"
                value={capitalInput}
                onChange={(e) => setCapitalInput(e.target.value)}
                placeholder="e.g. 25000"
                className="app-input flex-1 text-sm"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveCapital();
                  if (e.key === "Escape") setIsEditingCapital(false);
                }}
              />
              <button
                type="button"
                onClick={handleSaveCapital}
                disabled={isSaving}
                className="rounded-full p-1.5 text-emerald-400 hover:bg-emerald-400/10 transition-colors"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setIsEditingCapital(false)}
                className="rounded-full p-1.5 text-muted-foreground hover:bg-muted/60 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <div className="text-lg font-semibold text-foreground">
                  {detail.allocatedCapital
                    ? `$${detail.allocatedCapital.toLocaleString()}`
                    : "Full Account"}
                </div>
                <div className="text-[11px] text-muted-foreground">
                  {detail.allocatedCapital
                    ? "Maximum capital this bot can use"
                    : "Using full broker account equity"}
                </div>
              </div>
              <button
                type="button"
                onClick={handleEditCapital}
                className="rounded-full p-2 text-muted-foreground hover:bg-muted/60 hover:text-foreground transition-colors"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {/* AI Capital Management Toggle */}
          <div className="flex items-center justify-between rounded-2xl border border-border/60 bg-background/60 px-3 py-2.5">
            <div className="flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-violet-400" />
              <div>
                <div className="text-xs font-semibold text-foreground">AI Capital Management</div>
                <div className="text-[10px] text-muted-foreground">
                  Let AI adjust capital based on performance
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={handleToggleAiCapital}
              className={`relative h-5 w-9 rounded-full transition-colors ${
                detail.aiCapitalManagement
                  ? "bg-violet-500"
                  : "bg-muted-foreground/30"
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
                  detail.aiCapitalManagement ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {saveError && (
        <div className="rounded-lg border border-red-400/30 bg-red-400/8 px-3 py-2 text-[11px] text-red-400 flex items-center gap-2">
          <X className="h-3 w-3 shrink-0 cursor-pointer" onClick={() => setSaveError(null)} />
          {saveError}
        </div>
      )}

      <div className="grid gap-3">
        <InfoRow label="Strategy" value={humanizeLabel(detail.strategyType)} />
        <InfoRow label="Timeframe" value={formatTimeframe(config.timeframe)} />
        <InfoRow label="Risk Posture" value={riskPosture} />
        <InfoRow
          label="Position Sizing"
          value={`Allocates ${positionSize} of capital per trade${maxExposure !== "N/A" ? ` with ${maxExposure} max exposure` : ""}.`}
        />
        <InfoRow
          label="Stops and Targets"
          value={`Stop loss ${stopLoss}${takeProfit !== "N/A" ? ` · take profit ${takeProfit}` : ""}`}
        />
        <InfoRow
          label="Execution Friction"
          value={`Commission ${formatPercent(config.commission_pct as number | null | undefined, 2, true)} · slippage ${formatPercent(config.slippage_pct as number | null | undefined, 2, true)}`}
        />
        <InfoRow
          label="Portfolio Guardrails"
          value={`Max loss ${maxLoss}${typeof config.max_trades_per_day === "number" && config.max_trades_per_day > 0 ? ` · ${config.max_trades_per_day} trades per day` : ""}${typeof config.cooldown_bars === "number" && config.cooldown_bars > 0 ? ` · ${config.cooldown_bars} cooldown bars` : ""}`}
        />
      </div>

      <div className="mt-6">
        <div className="mb-3 flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-emerald-400" />
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Assets Traded
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {assets.map((symbol) => (
            <button
              key={symbol}
              type="button"
              onClick={() => onSymbolSelect(symbol)}
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold tracking-[0.12em] transition-colors ${
                activeSymbol === symbol
                  ? "border-sky-400/40 bg-sky-400/10 text-sky-400"
                  : "border-border/60 bg-muted/15 text-muted-foreground hover:text-foreground"
              }`}
            >
              {symbol}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6">
        <div className="mb-3 flex items-center gap-2">
          <Shield className="h-4 w-4 text-amber-400" />
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            AI Reasoning Summary
          </div>
        </div>
        <div className="rounded-[22px] border border-border/60 bg-muted/15 p-4">
          <p className="text-sm leading-6 text-foreground">{getAiOverview(detail)}</p>
          {assumptions.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {assumptions.map((assumption) => (
                <span
                  key={assumption}
                  className="rounded-full border border-border/60 bg-background/60 px-2.5 py-1 text-[11px] text-muted-foreground"
                >
                  {assumption}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-6">
        <div className="mb-3 flex items-center gap-2">
          <Target className="h-4 w-4 text-fuchsia-400" />
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Current Focus
          </div>
        </div>
        <div className="rounded-[22px] border border-border/60 bg-muted/15 p-4">
          {selectedTrade ? (
            <>
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-foreground">
                  {selectedTrade.symbol} {selectedTrade.side.toUpperCase()}
                </div>
                <div className="text-xs text-muted-foreground">{selectedTrade.status}</div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Entry</div>
                  <div className="mt-1 text-foreground">{formatCurrency(selectedTrade.entryPrice)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">PnL</div>
                  <div className={`mt-1 ${selectedTrade.netPnl != null && selectedTrade.netPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {formatCurrency(selectedTrade.netPnl)}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm leading-6 text-muted-foreground">
              Select a trade from the chart or log to inspect its execution path, projected stop loss,
              take profit, and trigger context.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
