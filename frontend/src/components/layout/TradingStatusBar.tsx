"use client";

import { useState, useEffect, useRef } from "react";
import { ShieldAlert, AlertTriangle, Shield } from "lucide-react";
import { useTradingMode } from "@/hooks/useTradingMode";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function TradingStatusBar() {
  const { mode, setMode, switching } = useTradingMode();
  const { toast } = useToast();
  const [confirmLiveOpen, setConfirmLiveOpen] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [justSwitched, setJustSwitched] = useState(false);
  const prevModeRef = useRef(mode);

  // Flash effect on mode change
  useEffect(() => {
    if (prevModeRef.current !== mode) {
      setJustSwitched(true);
      const timer = setTimeout(() => setJustSwitched(false), 600);
      prevModeRef.current = mode;
      return () => clearTimeout(timer);
    }
  }, [mode]);

  const handleModeRequest = async (targetMode: "paper" | "live") => {
    if (switching || mode === targetMode) return;
    if (targetMode === "live") {
      setConfirmText("");
      setConfirmLiveOpen(true);
      return;
    }
    try {
      await setMode(targetMode);
      toast("Switched to paper trading — simulated capital only", "success");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to switch trading mode";
      toast(`Unable to switch to ${targetMode} mode: ${message}`, "error");
    }
  };

  const handleConfirmLive = async () => {
    setConfirmLiveOpen(false);
    setConfirmText("");
    try {
      await setMode("live");
      toast("LIVE TRADING ENABLED — Real capital is at risk", "warning");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to switch trading mode";
      toast(`Unable to switch to live mode: ${message}`, "error");
    }
  };

  const canConfirmLive = confirmText.toUpperCase() === "CONFIRM";

  return (
    <>
      <div
        className={cn(
          "fixed top-0 left-0 right-0 z-50 flex items-center justify-center gap-4 px-4",
          "h-[var(--status-bar-height)] text-xs font-medium transition-colors duration-150",
          mode === "live" ? "status-bar-live" : "status-bar-paper",
          justSwitched && "mode-switching"
        )}
      >
        {mode === "live" ? (
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-600" />
            </span>
            <span className="font-bold tracking-wide text-amber-900 dark:text-amber-200">
              LIVE TRADING — REAL CAPITAL AT RISK
            </span>
            <AlertTriangle className="h-3.5 w-3.5 text-amber-700 dark:text-amber-300" />
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Shield className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500" />
            <span className="tracking-wide text-slate-500 dark:text-slate-400">
              PAPER TRADING — Simulated capital only
            </span>
          </div>
        )}

        <div className="flex items-center gap-1 rounded-full border border-border/50 bg-background/60 p-0.5 backdrop-blur-sm">
          <button
            type="button"
            onClick={() => void handleModeRequest("paper")}
            disabled={switching || mode === "paper"}
            className={cn(
              "rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-wider transition-all duration-150",
              mode === "paper"
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Paper
          </button>
          <span className="h-4 w-px bg-border/50" />
          <button
            type="button"
            onClick={() => void handleModeRequest("live")}
            disabled={switching}
            className={cn(
              "rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-wider transition-all duration-150",
              mode === "live"
                ? "bg-red-500/20 text-red-400 ring-1 ring-red-500/30"
                : "border border-amber-500/30 text-amber-700 dark:text-amber-400 hover:bg-amber-500/10"
            )}
          >
            {switching ? "Switching..." : mode === "live" ? "LIVE" : "Enable Live"}
          </button>
        </div>
      </div>

      {/* Hard confirmation dialog — requires typing CONFIRM */}
      <Dialog open={confirmLiveOpen} onOpenChange={setConfirmLiveOpen}>
        <DialogContent className="max-w-md border-2 border-red-500/30 bg-card shadow-2xl shadow-red-500/10">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg text-foreground">
              <ShieldAlert className="h-6 w-6 text-red-400" />
              Enable Live Trading
            </DialogTitle>
            <DialogDescription className="pt-2 text-sm leading-6 text-muted-foreground">
              You are about to switch to <strong className="text-foreground">real money trading</strong>.
              All orders will be executed on your live brokerage account with real capital.
              This action has financial consequences.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="rounded-xl border-2 border-red-500/20 bg-red-500/5 p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400" />
                <div className="space-y-1 text-sm">
                  <p className="font-semibold text-red-300">Real capital will be at risk</p>
                  <ul className="space-y-0.5 text-muted-foreground">
                    <li>All running bots will execute with real money</li>
                    <li>Trade proposals will route to your live broker</li>
                    <li>Losses are permanent and irreversible</li>
                  </ul>
                </div>
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Type CONFIRM to enable live trading
              </label>
              <input
                type="text"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder="CONFIRM"
                autoFocus
                className={cn(
                  "app-input w-full font-mono text-center text-lg tracking-widest",
                  canConfirmLive && "border-emerald-500/50 ring-1 ring-emerald-500/20"
                )}
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                setConfirmLiveOpen(false);
                setConfirmText("");
              }}
              className="app-button-ghost"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleConfirmLive()}
              disabled={!canConfirmLive || switching}
              className={cn(
                "rounded-full px-5 py-2.5 text-sm font-semibold transition-all duration-200",
                canConfirmLive
                  ? "border border-emerald-500/25 bg-emerald-500/12 text-emerald-300 hover:border-emerald-400/35 hover:bg-emerald-500/18"
                  : "cursor-not-allowed border border-border/50 bg-muted/30 text-muted-foreground opacity-50"
              )}
            >
              {switching ? "Switching..." : "Enable Live Trading"}
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
