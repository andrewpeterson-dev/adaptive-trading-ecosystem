"use client";

import { useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { X, Rocket, Globe, Cpu, ShieldCheck, DollarSign } from "lucide-react";
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

export interface DeployConfig {
  universeConfig: UniverseConfig;
  overrideLevel: OverrideLevel;
  allocatedCapital: number | null;
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
    description: "AI can delay, reduce, cancel, or exit positions",
  },
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

  const handleDeploy = () => {
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
    onDeploy({ universeConfig, overrideLevel, allocatedCapital });
  };

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm"
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
          </section>

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
