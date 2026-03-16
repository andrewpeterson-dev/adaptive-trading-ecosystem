"use client";

import { useState } from "react";
import { ShieldAlert } from "lucide-react";
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

  const handleModeRequest = async (targetMode: "paper" | "live") => {
    if (switching || mode === targetMode) return;
    if (targetMode === "live") {
      setConfirmLiveOpen(true);
      return;
    }
    try {
      await setMode(targetMode);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to switch trading mode";
      toast(`Unable to switch to ${targetMode} mode: ${message}`, "error");
    }
  };

  const handleConfirmLive = async () => {
    setConfirmLiveOpen(false);
    try {
      await setMode("live");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to switch trading mode";
      toast(`Unable to switch to live mode: ${message}`, "error");
    }
  };

  return (
    <>
      <div
        className={cn(
          "fixed top-0 left-0 right-0 z-50 flex items-center justify-center gap-4 px-4",
          "h-[var(--status-bar-height)] text-xs font-medium",
          mode === "live" ? "status-bar-live" : "status-bar-paper"
        )}
      >
        {mode === "live" ? (
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse-dot" />
            <span className="font-semibold tracking-wide text-amber-900 dark:text-amber-200">
              LIVE TRADING ACTIVE
            </span>
          </div>
        ) : (
          <span className="tracking-wide text-slate-500 dark:text-slate-400">
            PAPER TRADING — Simulated capital only
          </span>
        )}

        <div className="flex items-center gap-1 rounded-full border border-border/50 bg-background/60 p-0.5 backdrop-blur-sm">
          <button
            type="button"
            onClick={() => void handleModeRequest("paper")}
            disabled={switching || mode === "paper"}
            className={cn(
              "rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-wider transition-all",
              mode === "paper"
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Paper
          </button>
          <button
            type="button"
            onClick={() => void handleModeRequest("live")}
            disabled={switching}
            className={cn(
              "rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-wider transition-all",
              mode === "live"
                ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                : "text-amber-600 dark:text-amber-400 hover:bg-amber-500/10"
            )}
          >
            {mode === "live" ? "Live On" : "Enable Live"}
          </button>
        </div>
      </div>

      <Dialog open={confirmLiveOpen} onOpenChange={setConfirmLiveOpen}>
        <DialogContent className="max-w-md border border-amber-500/20 bg-card">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-foreground">
              <ShieldAlert className="h-5 w-5 text-amber-400" />
              Enable Live Trading
            </DialogTitle>
            <DialogDescription className="pt-2 text-sm leading-6 text-muted-foreground">
              You are about to enable live trading with real capital. Orders will be
              routed to your brokerage connection. Confirm?
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-[20px] border border-amber-500/15 bg-amber-500/6 p-4 text-sm text-muted-foreground">
            Current execution state:{" "}
            <span className="font-semibold text-foreground">
              {mode === "live" ? "LIVE ON" : "LIVE OFF"}
            </span>
          </div>

          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmLiveOpen(false)}
              className="app-button-ghost"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleConfirmLive()}
              disabled={switching}
              className="rounded-full border border-emerald-500/25 bg-emerald-500/12 px-5 py-2.5 text-sm font-semibold text-emerald-300 transition-colors hover:border-emerald-400/35 hover:bg-emerald-500/18 disabled:opacity-50"
            >
              Confirm Live
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
