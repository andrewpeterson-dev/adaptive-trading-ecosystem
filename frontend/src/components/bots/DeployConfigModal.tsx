"use client";

import { useState, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { X, Rocket, Globe, Cpu, ShieldCheck, DollarSign, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";

// ── Types ────────────────────────────────────────────────────────────────────

export type UniverseMode = "fixed" | "sector" | "index" | "ai";

export interface UniverseConfig {
  mode: UniverseMode;
  symbols?: string[];
  sectors?: string[];
  index?: string;
  blacklist?: string[];
}

export type OverrideLevel = "advisory" | "soft" | "full";

export interface AIBrainConfig {
  primaryModel: string;
  dataSources: string[];
  tradingThesis?: string;
  comparisonModels?: string[];
}

export interface DeployConfig {
  universeConfig: UniverseConfig;
  overrideLevel: OverrideLevel;
  allocatedCapital: number | null;
  extendedHours: boolean;
  aiBrainConfig?: AIBrainConfig;
}

interface DeployConfigModalProps {
  open: boolean;
  onClose: () => void;
  onDeploy: (config: DeployConfig) => void;
  botName?: string;
  isDeploying?: boolean;
}

// ── Constants ────────────────────────────────────────────────────────────────

const SECTORS = [
  "Technology",
  "Healthcare",
  "Financial",
  "Energy",
  "Consumer Discretionary",
  "Industrials",
  "Materials",
  "Utilities",
  "Real Estate",
  "Communication",
] as const;

const INDEX_OPTIONS = ["S&P 500", "Nasdaq 100"] as const;

const OVERRIDE_OPTIONS: { value: OverrideLevel; label: string; description: string }[] = [
  {
    value: "advisory",
    label: "Advisory",
    description: "AI logs recommendations but never modifies trades",
  },
  {
    value: "soft",
    label: "Soft Override",
    description: "AI can delay or reduce position size, but never cancel",
  },
  {
    value: "full",
    label: "Full Autonomy",
    description: "AI analyzes markets and makes all trading decisions autonomously",
  },
];

const AI_MODELS = [
  { value: "gpt-5.4", label: "GPT-5.4 (Primary)" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "gpt-4.1", label: "GPT-4.1 (Fast)" },
  { value: "deepseek-r1", label: "DeepSeek R1" },
];

const DATA_SOURCE_OPTIONS = [
  { value: "technical", label: "Technical", desc: "RSI, MACD, BBands, support/resistance" },
  { value: "sentiment", label: "Sentiment", desc: "News, social media, options flow" },
  { value: "fundamental", label: "Fundamental", desc: "Earnings, P/E, revenue" },
  { value: "macro", label: "Macro", desc: "VIX, Fed calendar, market breadth" },
  { value: "portfolio", label: "Portfolio", desc: "Current positions, exposure, P&L" },
];

// ── Component ────────────────────────────────────────────────────────────────

export function DeployConfigModal({
  open,
  onClose,
  onDeploy,
  botName,
  isDeploying = false,
}: DeployConfigModalProps) {
  const [universeMode, setUniverseMode] = useState<UniverseMode>("fixed");
  const [symbolsText, setSymbolsText] = useState("");
  const [selectedSectors, setSelectedSectors] = useState<Set<string>>(new Set());
  const [selectedIndex, setSelectedIndex] = useState<string>(INDEX_OPTIONS[0]);
  const [blacklistText, setBlacklistText] = useState("");
  const [overrideLevel, setOverrideLevel] = useState<OverrideLevel>("soft");
  const [capitalInput, setCapitalInput] = useState("");
  const [extendedHours, setExtendedHours] = useState(false);
  const [primaryModel, setPrimaryModel] = useState("gpt-5.4");
  const [dataSources, setDataSources] = useState<string[]>(["technical", "sentiment", "fundamental", "macro", "portfolio"]);
  const [tradingThesis, setTradingThesis] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [comparisonModels, setComparisonModels] = useState<string[]>([]);

  // Reset all form state when modal opens to prevent stale config from previous deploy
  useEffect(() => {
    if (open) {
      setUniverseMode("fixed");
      setSymbolsText("");
      setSelectedSectors(new Set());
      setSelectedIndex(INDEX_OPTIONS[0]);
      setBlacklistText("");
      setOverrideLevel("soft");
      setCapitalInput("");
      setExtendedHours(false);
      setPrimaryModel("gpt-5.4");
      setDataSources(["technical", "sentiment", "fundamental", "macro", "portfolio"]);
      setTradingThesis("");
      setShowAdvanced(false);
      setComparisonModels([]);
    }
  }, [open]);

  const toggleSector = useCallback((sector: string) => {
    setSelectedSectors((prev) => {
      const next = new Set(prev);
      if (next.has(sector)) {
        next.delete(sector);
      } else {
        next.add(sector);
      }
      return next;
    });
  }, []);

  const parseCommaSeparated = (text: string): string[] =>
    text
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

  const [validationError, setValidationError] = useState<string | null>(null);

  const handleDeploy = () => {
    // Validate universe configuration
    if (universeMode === "fixed") {
      const symbols = parseCommaSeparated(symbolsText);
      if (symbols.length === 0) {
        setValidationError("Enter at least one symbol to trade.");
        return;
      }
    } else if (universeMode === "sector" && selectedSectors.size === 0) {
      setValidationError("Select at least one sector.");
      return;
    }

    setValidationError(null);
    const blacklist = parseCommaSeparated(blacklistText);

    const universeConfig: UniverseConfig = { mode: universeMode };

    if (universeMode === "fixed") {
      universeConfig.symbols = parseCommaSeparated(symbolsText);
    } else if (universeMode === "sector") {
      universeConfig.sectors = Array.from(selectedSectors);
    } else if (universeMode === "index") {
      universeConfig.index = selectedIndex;
    }

    if (blacklist.length > 0) {
      universeConfig.blacklist = blacklist;
    }

    const parsedCapital = capitalInput.trim() ? parseFloat(capitalInput.replace(/[,$]/g, "")) : null;
    const allocatedCapital = parsedCapital && !isNaN(parsedCapital) && parsedCapital > 0 ? parsedCapital : null;

    const config: DeployConfig = { universeConfig, overrideLevel, allocatedCapital, extendedHours };

    if (overrideLevel === "full") {
      config.aiBrainConfig = {
        primaryModel,
        dataSources,
        tradingThesis: tradingThesis.trim() || undefined,
        comparisonModels: comparisonModels.length > 0 ? comparisonModels : undefined,
      };
    }

    onDeploy(config);
  };

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={`Deploy configuration for ${botName || "bot"}`}
      onClick={(e) => { e.stopPropagation(); onClose(); }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div
        className="app-panel mx-4 w-full max-w-lg p-5 sm:p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-5 flex items-start justify-between">
          <div>
            <p className="app-label">Deploy Configuration</p>
            <h3 className="mt-1.5 text-lg font-semibold text-foreground">
              {botName || "Configure Bot"}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-muted-foreground hover:bg-muted/60 hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-5">
          {/* ── Universe Configuration ─────────────────────────────────── */}
          <section>
            <div className="mb-3 flex items-center gap-2">
              <Globe className="h-4 w-4 text-sky-400" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Universe Configuration
              </p>
            </div>

            {/* Mode selector */}
            <div className="app-segmented mb-3">
              {(
                [
                  { value: "fixed", label: "Fixed" },
                  { value: "sector", label: "Sector" },
                  { value: "index", label: "Index" },
                  { value: "ai", label: "AI Selected" },
                ] as const
              ).map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setUniverseMode(option.value)}
                  className={`app-segment ${universeMode === option.value ? "app-toggle-active" : ""}`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            {/* Mode-specific inputs */}
            {universeMode === "fixed" && (
              <div>
                <label className="app-label mb-1.5 block">Symbols</label>
                <input
                  type="text"
                  value={symbolsText}
                  onChange={(e) => setSymbolsText(e.target.value)}
                  placeholder="AAPL, MSFT, TSLA, NVDA"
                  className="app-input"
                />
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  Comma-separated ticker symbols
                </p>
              </div>
            )}

            {universeMode === "sector" && (
              <div>
                <label className="app-label mb-1.5 block">Sectors</label>
                <div className="flex flex-wrap gap-2">
                  {SECTORS.map((sector) => (
                    <button
                      key={sector}
                      type="button"
                      onClick={() => toggleSector(sector)}
                      className={`app-pill cursor-pointer transition-colors ${
                        selectedSectors.has(sector)
                          ? "border-sky-400/40 bg-sky-400/10 text-sky-400"
                          : "hover:text-foreground"
                      }`}
                    >
                      {sector}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {universeMode === "index" && (
              <div>
                <label className="app-label mb-1.5 block">Index</label>
                <select
                  value={selectedIndex}
                  onChange={(e) => setSelectedIndex(e.target.value)}
                  className="app-select"
                >
                  {INDEX_OPTIONS.map((idx) => (
                    <option key={idx} value={idx}>
                      {idx}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {universeMode === "ai" && (
              <div className="rounded-2xl border border-border/60 bg-muted/15 px-3 py-3">
                <div className="flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-violet-400" />
                  <p className="text-sm text-muted-foreground">
                    Cerberus will dynamically select the symbol universe based on market conditions and strategy fit.
                  </p>
                </div>
              </div>
            )}

            {/* Blacklist */}
            <div className="mt-3">
              <label className="app-label mb-1.5 block">Symbol Blacklist (optional)</label>
              <input
                type="text"
                value={blacklistText}
                onChange={(e) => setBlacklistText(e.target.value)}
                placeholder="COIN, GME, AMC"
                className="app-input"
              />
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Symbols excluded from trading regardless of universe mode
              </p>
            </div>
          </section>

          {/* ── Capital Allocation ────────────────────────────────────── */}
          <section>
            <div className="mb-3 flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-emerald-400" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Capital Allocation
              </p>
            </div>
            <div>
              <label className="app-label mb-1.5 block">Allocated Capital ($)</label>
              <input
                type="text"
                inputMode="decimal"
                value={capitalInput}
                onChange={(e) => setCapitalInput(e.target.value)}
                placeholder="e.g. 10000"
                className="app-input"
              />
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Maximum capital this bot can trade with. Leave empty to use full account equity.
              </p>
            </div>
          </section>

          {/* ── AI Override Level ──────────────────────────────────────── */}
          <section>
            <div className="mb-3 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-amber-400" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                AI Override Level
              </p>
            </div>

            <div className="space-y-2">
              {OVERRIDE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setOverrideLevel(option.value)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors ${
                    overrideLevel === option.value
                      ? "border-sky-400/40 bg-sky-400/8"
                      : "border-border/60 bg-muted/15 hover:border-border"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={`h-3 w-3 rounded-full border-2 ${
                        overrideLevel === option.value
                          ? "border-sky-400 bg-sky-400"
                          : "border-muted-foreground/40 bg-transparent"
                      }`}
                    />
                    <span
                      className={`text-sm font-semibold ${
                        overrideLevel === option.value
                          ? "text-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      {option.label}
                    </span>
                  </div>
                  <p className="mt-1 pl-5 text-xs text-muted-foreground">
                    {option.description}
                  </p>
                </button>
              ))}
            </div>

            {overrideLevel === "full" && (
              <div className="space-y-4 mt-4 p-4 rounded-lg bg-zinc-800/50 border border-zinc-700">
                <h4 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                  <Cpu className="w-4 h-4" /> AI Brain Configuration
                </h4>

                {/* Model Selection */}
                <div>
                  <label className="text-xs text-zinc-400 block mb-1">AI Model</label>
                  <select
                    value={primaryModel}
                    onChange={(e) => setPrimaryModel(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
                  >
                    {AI_MODELS.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                </div>

                {/* Data Sources */}
                <div>
                  <label className="text-xs text-zinc-400 block mb-2">Data Sources</label>
                  <div className="grid grid-cols-2 gap-2">
                    {DATA_SOURCE_OPTIONS.map((src) => (
                      <label
                        key={src.value}
                        className={`flex items-start gap-2 p-2 rounded border cursor-pointer transition-colors ${
                          dataSources.includes(src.value)
                            ? "border-blue-500 bg-blue-500/10"
                            : "border-zinc-700 bg-zinc-900 hover:border-zinc-600"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={dataSources.includes(src.value)}
                          onChange={(e) => {
                            setDataSources(
                              e.target.checked
                                ? [...dataSources, src.value]
                                : dataSources.filter((s) => s !== src.value)
                            );
                          }}
                          className="mt-0.5 accent-blue-500"
                        />
                        <div>
                          <span className="text-sm text-white">{src.label}</span>
                          <p className="text-xs text-zinc-500">{src.desc}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Trading Thesis */}
                <div>
                  <label className="text-xs text-zinc-400 block mb-1">Trading Thesis</label>
                  <textarea
                    value={tradingThesis}
                    onChange={(e) => setTradingThesis(e.target.value)}
                    placeholder="e.g., Trade large-cap tech stocks based on earnings surprises and options flow..."
                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white h-20 resize-none focus:border-blue-500 focus:outline-none"
                  />
                </div>

                {/* Advanced Toggle */}
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  {showAdvanced ? "Hide" : "Show"} Advanced Options
                </button>

                {showAdvanced && (
                  <div className="space-y-3 pt-2 border-t border-zinc-700">
                    <div>
                      <label className="text-xs text-zinc-400 block mb-1">Comparison Models (shadow paper runs)</label>
                      <div className="space-y-1">
                        {AI_MODELS.filter((m) => m.value !== primaryModel).map((m) => (
                          <label key={m.value} className="flex items-center gap-2 text-sm text-zinc-300">
                            <input
                              type="checkbox"
                              checked={comparisonModels.includes(m.value)}
                              onChange={(e) => {
                                setComparisonModels(
                                  e.target.checked
                                    ? [...comparisonModels, m.value]
                                    : comparisonModels.filter((v) => v !== m.value)
                                );
                              }}
                              className="accent-blue-500"
                            />
                            {m.label}
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* ── Extended Hours ────────────────────────────────────────── */}
          <section>
            <div className="mb-3 flex items-center gap-2">
              <Clock className="h-4 w-4 text-sky-400" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Extended Hours
              </p>
            </div>
            <label className="flex items-center gap-3 cursor-pointer group">
              <div className="relative">
                <input
                  type="checkbox"
                  checked={extendedHours}
                  onChange={(e) => setExtendedHours(e.target.checked)}
                  className="peer sr-only"
                />
                <div className="h-5 w-9 rounded-full border border-border/60 bg-muted/30 transition-colors peer-checked:border-sky-400/40 peer-checked:bg-sky-400/20" />
                <div className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-muted-foreground/60 transition-all peer-checked:translate-x-4 peer-checked:bg-sky-400" />
              </div>
              <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                Enable pre-market &amp; after-hours trading
              </span>
            </label>
            <p className="mt-2 pl-12 text-[11px] text-muted-foreground">
              Trades 4 AM &ndash; 8 PM ET instead of 9:30 AM &ndash; 4 PM. Position sizes auto-reduce 50% outside regular hours due to lower liquidity.
            </p>
          </section>

          {/* ── Validation Error ──────────────────────────────────────── */}
          {validationError && (
            <div className="rounded-xl border border-red-400/30 bg-red-400/8 px-4 py-2.5 text-sm text-red-400">
              {validationError}
            </div>
          )}

          {/* ── Actions ───────────────────────────────────────────────── */}
          <div className="flex gap-3 pt-1">
            <Button variant="secondary" size="md" onClick={onClose} className="flex-1">
              Cancel
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={handleDeploy}
              disabled={isDeploying}
              className="flex-1"
            >
              {isDeploying ? (
                <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground" />
              ) : (
                <Rocket className="h-3.5 w-3.5" />
              )}
              {isDeploying ? "Deploying..." : "Deploy"}
            </Button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
