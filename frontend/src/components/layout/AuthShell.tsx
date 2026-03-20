"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { BrandLogo } from "./BrandLogo";

/* ═══════════════════════════════════════════════════════════════════════════
   DATA — ticker tape, system status, activity feed, Cerberus insights
   ═══════════════════════════════════════════════════════════════════════════ */

const TICKER_ITEMS = [
  { symbol: "SPY", change: "+1.24%", positive: true },
  { symbol: "NVDA", change: "+3.41%", positive: true },
  { symbol: "TSLA", change: "-0.83%", positive: false },
  { symbol: "AAPL", change: "+0.52%", positive: true },
  { symbol: "AMD", change: "+2.17%", positive: true },
  { symbol: "META", change: "+1.73%", positive: true },
  { symbol: "GOOGL", change: "+0.31%", positive: true },
  { symbol: "AMZN", change: "-0.21%", positive: false },
  { symbol: "MSFT", change: "+0.88%", positive: true },
  { symbol: "QQQ", change: "+1.05%", positive: true },
  { symbol: "BRK.B", change: "+0.44%", positive: true },
  { symbol: "JPM", change: "-0.37%", positive: false },
  { symbol: "GS", change: "+1.62%", positive: true },
  { symbol: "VIX", change: "-4.20%", positive: false },
];

const SYSTEM_STATUS = [
  { label: "Broker Sync", value: "Active", ok: true },
  { label: "Execution", value: "42ms", ok: true },
  { label: "Data Feed", value: "Live", ok: true },
  { label: "Security", value: "Verified", ok: true },
  { label: "Strategies", value: "3 running", ok: true },
  { label: "Last Update", value: "0.8s ago", ok: true },
];

const ACTIVITY_FEED = [
  { time: "09:31:04", event: "Momentum Alpha entered NVDA long — confidence 84%", type: "entry" as const },
  { time: "09:30:58", event: "ReasoningEngine approved trade — drawdown within limits", type: "system" as const },
  { time: "09:30:42", event: "Sentiment score for TSLA shifted bearish (-1.8)", type: "signal" as const },
  { time: "09:30:31", event: "VIX regime change detected: trending → neutral", type: "signal" as const },
  { time: "09:30:15", event: "Oversold Bounce triggered exit on DIA — +2.4% realized", type: "exit" as const },
  { time: "09:29:47", event: "Kelly sizing recalculated — optimal position: 12.3%", type: "system" as const },
  { time: "09:29:22", event: "MACD Crossover scanning 11 symbols on 1H timeframe", type: "system" as const },
  { time: "09:28:55", event: "Sector cap check: Technology at 27% (limit: 30%)", type: "system" as const },
];

const CERBERUS_INSIGHTS = [
  "Volatility compression detected across tech sector. Breakout probability increasing — monitoring for directional confirmation.",
  "SPY holding above 50-day EMA with improving breadth. Risk-on regime favors momentum entries.",
  "NVDA approaching prior resistance with rising volume. Position sizing adjusted for elevated conviction.",
];

/* ═══════════════════════════════════════════════════════════════════════════
   STATUS INDICATOR — pulsing dot
   ═══════════════════════════════════════════════════════════════════════════ */

function StatusDot({ ok, delay = 0 }: { ok: boolean; delay?: number }) {
  return (
    <motion.span
      className="relative flex h-2 w-2"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay }}
    >
      <span
        className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
        style={{
          backgroundColor: ok ? "hsl(152 72% 45%)" : "hsl(0 78% 58%)",
          animationDuration: "2.5s",
        }}
      />
      <span
        className="relative inline-flex h-2 w-2 rounded-full"
        style={{
          backgroundColor: ok ? "hsl(152 72% 45%)" : "hsl(0 78% 58%)",
        }}
      />
    </motion.span>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SYSTEM STATUS MODULE
   ═══════════════════════════════════════════════════════════════════════════ */

function SystemStatusModule() {
  return (
    <motion.div
      className="auth-module"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
    >
      <div className="auth-module-header">
        <span className="auth-module-label">System Status</span>
        <StatusDot ok delay={0.5} />
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2.5">
        {SYSTEM_STATUS.map((item, i) => (
          <motion.div
            key={item.label}
            className="flex items-center justify-between gap-2"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: 0.4 + i * 0.06 }}
          >
            <span className="text-[11px] text-muted-foreground/70">{item.label}</span>
            <span className="font-mono text-[11px] font-medium text-foreground/90">{item.value}</span>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   ACTIVITY FEED MODULE
   ═══════════════════════════════════════════════════════════════════════════ */

const EVENT_COLORS = {
  entry: "hsl(152 72% 45%)",
  exit: "hsl(213 96% 63%)",
  signal: "hsl(39 92% 57%)",
  system: "hsl(217 14% 55%)",
};

function ActivityFeedModule() {
  const [visibleCount, setVisibleCount] = useState(4);

  useEffect(() => {
    const timer = setInterval(() => {
      setVisibleCount((c) => (c >= ACTIVITY_FEED.length ? 4 : c + 1));
    }, 3500);
    return () => clearInterval(timer);
  }, []);

  const visible = ACTIVITY_FEED.slice(0, visibleCount);

  return (
    <motion.div
      className="auth-module"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
    >
      <div className="auth-module-header">
        <span className="auth-module-label">Activity Feed</span>
        <span className="font-mono text-[10px] text-muted-foreground/50">LIVE</span>
      </div>
      <div className="space-y-0 max-h-[168px] overflow-hidden">
        <AnimatePresence mode="popLayout">
          {visible.map((item) => (
            <motion.div
              key={item.time + item.event}
              className="flex items-start gap-2.5 py-1.5"
              initial={{ opacity: 0, height: 0, y: -8 }}
              animate={{ opacity: 1, height: "auto", y: 0 }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.35 }}
              layout
            >
              <span
                className="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: EVENT_COLORS[item.type] }}
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[11px] leading-[1.4] text-foreground/75">
                  {item.event}
                </p>
              </div>
              <span className="shrink-0 font-mono text-[10px] text-muted-foreground/40">
                {item.time}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   CERBERUS AI MODULE
   ═══════════════════════════════════════════════════════════════════════════ */

function CerberusModule() {
  const [insightIdx, setInsightIdx] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setInsightIdx((i) => (i + 1) % CERBERUS_INSIGHTS.length);
    }, 6000);
    return () => clearInterval(timer);
  }, []);

  return (
    <motion.div
      className="auth-module auth-module-cerberus"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.7 }}
    >
      <div className="auth-module-header">
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded-md bg-primary/10 border border-primary/20">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="hsl(213 96% 63%)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a4 4 0 0 1 4 4c0 1.1-.6 2.2-1.2 3L12 12l-2.8-3C8.6 8.2 8 7.1 8 6a4 4 0 0 1 4-4Z" />
              <path d="m12 12 5 3-2 6H9l-2-6 5-3Z" />
            </svg>
          </div>
          <span className="auth-module-label">Cerberus AI</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground/50">Confidence</span>
          <span className="font-mono text-[11px] font-semibold text-primary">78%</span>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-2.5">
        <span className="auth-regime-badge">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Trending
        </span>
        <span className="auth-regime-badge">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
          Risk-On
        </span>
      </div>

      <AnimatePresence mode="wait">
        <motion.p
          key={insightIdx}
          className="text-[12px] leading-[1.6] text-foreground/65 italic"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.4 }}
        >
          &ldquo;{CERBERUS_INSIGHTS[insightIdx]}&rdquo;
        </motion.p>
      </AnimatePresence>
    </motion.div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN AUTH SHELL
   ═══════════════════════════════════════════════════════════════════════════ */

interface AuthShellProps {
  title: string;
  description: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export function AuthShell({ title, description, children, footer }: AuthShellProps) {
  const tickerItems = [...TICKER_ITEMS, ...TICKER_ITEMS];

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      {/* ── Inline styles ─────────────────────────────────────────────────── */}
      <style>{`
        @keyframes auth-ticker-scroll {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .auth-module {
          padding: 14px 16px;
          border-radius: 14px;
          border: 1px solid hsl(var(--border) / 0.5);
          background: linear-gradient(
            180deg,
            hsl(var(--surface-2) / 0.55),
            hsl(var(--surface-1) / 0.55)
          );
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          transition: border-color 250ms ease, box-shadow 250ms ease;
        }
        .auth-module:hover {
          border-color: hsl(var(--border) / 0.8);
          box-shadow: 0 0 24px -8px hsl(var(--primary) / 0.08);
        }
        .auth-module-cerberus {
          border-color: hsl(var(--primary) / 0.15);
          background: linear-gradient(
            135deg,
            hsl(var(--surface-2) / 0.6),
            hsl(var(--primary) / 0.04) 80%,
            hsl(var(--surface-1) / 0.55)
          );
        }
        .auth-module-cerberus:hover {
          border-color: hsl(var(--primary) / 0.3);
          box-shadow: 0 0 32px -8px hsl(var(--primary) / 0.15);
        }
        .auth-module-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 10px;
        }
        .auth-module-label {
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.16em;
          color: hsl(var(--muted-foreground));
        }
        .auth-regime-badge {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 3px 10px;
          border-radius: 999px;
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 0.04em;
          color: hsl(var(--foreground) / 0.75);
          background: hsl(var(--surface-3) / 0.7);
          border: 1px solid hsl(var(--border) / 0.4);
        }
        .auth-form-card {
          border-radius: 28px;
          border: 1px solid hsl(var(--border) / 0.5);
          background: linear-gradient(
            180deg,
            hsl(var(--surface-2) / 0.85),
            hsl(var(--surface-3) / 0.85)
          );
          backdrop-filter: blur(32px);
          -webkit-backdrop-filter: blur(32px);
          box-shadow:
            0 32px 80px -20px hsl(var(--shadow-color) / 0.6),
            0 0 1px 0 hsl(0 0% 100% / 0.06) inset,
            0 1px 0 0 hsl(0 0% 100% / 0.04) inset;
          transition: border-color 300ms ease, box-shadow 300ms ease;
        }
        .auth-form-card:hover {
          border-color: hsl(var(--border) / 0.7);
          box-shadow:
            0 40px 100px -20px hsl(var(--shadow-color) / 0.7),
            0 0 1px 0 hsl(0 0% 100% / 0.08) inset,
            0 1px 0 0 hsl(0 0% 100% / 0.05) inset,
            0 0 40px -10px hsl(var(--primary) / 0.06);
        }
      `}</style>

      {/* Background: handled by AmbientIntelligenceLayer in AppShell */}

      {/* ── Ticker tape ──────────────────────────────────────────────────── */}
      <div
        aria-hidden="true"
        className="relative w-full overflow-hidden"
        style={{
          zIndex: 10,
          height: "32px",
          borderBottom: "1px solid hsl(var(--border) / 0.3)",
          background: "hsl(var(--surface-1) / 0.7)",
          backdropFilter: "blur(16px)",
        }}
      >
        <div
          className="pointer-events-none absolute inset-y-0 left-0 z-10 w-20"
          style={{ background: "linear-gradient(90deg, hsl(var(--background)), transparent)" }}
        />
        <div
          className="pointer-events-none absolute inset-y-0 right-0 z-10 w-20"
          style={{ background: "linear-gradient(270deg, hsl(var(--background)), transparent)" }}
        />
        <div
          className="flex h-full items-center whitespace-nowrap"
          style={{ animation: "auth-ticker-scroll 42s linear infinite", width: "max-content" }}
        >
          {tickerItems.map((item, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1.5 px-5 text-[11px] tracking-wide"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              <span className="font-semibold text-muted-foreground/60">{item.symbol}</span>
              <span style={{ color: item.positive ? "hsl(var(--positive))" : "hsl(var(--negative))", fontWeight: 500 }}>
                {item.change}
              </span>
              {i < tickerItems.length - 1 && (
                <span className="ml-3 text-muted-foreground/20" style={{ fontSize: "8px" }}>&#9679;</span>
              )}
            </span>
          ))}
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div className="relative flex flex-1 items-center justify-center px-4 py-8 sm:px-6 lg:px-8" style={{ zIndex: 10 }}>
        <div className="grid w-full max-w-[1200px] gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">

          {/* ── Left: branding + live system modules ─────────────────────── */}
          <section className="hidden space-y-6 lg:block">

            {/* Logo + brand */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
            >
              <Link href="/" className="inline-flex items-center gap-4 group">
                <div
                  className="relative flex items-center justify-center rounded-2xl"
                  style={{
                    width: 72,
                    height: 72,
                    background: "linear-gradient(135deg, hsl(var(--surface-2) / 0.9), hsl(var(--surface-3) / 0.9))",
                    border: "1px solid hsl(var(--border) / 0.5)",
                  }}
                >
                  {/* Glow ring */}
                  <div
                    className="absolute inset-0 rounded-2xl animate-pulse"
                    style={{
                      boxShadow: "0 0 20px 4px rgba(59,130,246,0.12), 0 0 48px 12px rgba(59,130,246,0.04)",
                      animationDuration: "3s",
                    }}
                  />
                  <BrandLogo size={56} className="h-14 w-14 relative" />
                </div>
                <div>
                  <p className="text-lg font-semibold tracking-tight text-foreground group-hover:text-primary transition-colors duration-200">
                    Adaptive Trading
                  </p>
                  <p className="text-sm text-muted-foreground/70">
                    AI-powered systematic execution
                  </p>
                </div>
              </Link>
            </motion.div>

            {/* Hero text */}
            <motion.div
              className="space-y-4"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              <h1 className="max-w-lg text-[2.6rem] font-semibold leading-[1.1] tracking-tight text-foreground">
                Your trading{" "}
                <span className="bg-gradient-to-r from-blue-400 via-blue-500 to-cyan-400 bg-clip-text text-transparent">
                  intelligence
                </span>{" "}
                is already running.
              </h1>
              <p className="max-w-md text-[15px] leading-[1.7] text-muted-foreground/80">
                Strategies executing. Risk monitoring. Market context updating.
                Sign in to take the controls.
              </p>
            </motion.div>

            {/* Live system modules */}
            <div className="space-y-3">
              <SystemStatusModule />
              <ActivityFeedModule />
              <CerberusModule />
            </div>
          </section>

          {/* ── Right: login form card ────────────────────────────────────── */}
          <motion.section
            className="w-full"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.15, ease: [0.25, 0.46, 0.45, 0.94] }}
          >
            <div className="auth-form-card p-1.5">
              <div className="rounded-[24px] p-6 sm:p-8" style={{
                background: "linear-gradient(180deg, hsl(var(--surface-2) / 0.5), hsl(var(--surface-3) / 0.5))",
              }}>
                <div className="mb-8 space-y-4">
                  {/* Mobile logo */}
                  <div className="inline-flex items-center gap-3 lg:hidden">
                    <div
                      className="flex items-center justify-center rounded-xl"
                      style={{
                        width: 52,
                        height: 52,
                        background: "linear-gradient(135deg, hsl(var(--surface-2) / 0.9), hsl(var(--surface-3) / 0.9))",
                        border: "1px solid hsl(var(--border) / 0.5)",
                      }}
                    >
                      <BrandLogo size={40} className="h-10 w-10" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-foreground">Adaptive Trading</p>
                      <p className="text-xs text-muted-foreground">AI-powered trading workspace</p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="app-kicker">Command Access</p>
                    <h2 className="text-3xl font-semibold tracking-tight text-foreground">{title}</h2>
                    <p className="text-sm leading-7 text-muted-foreground">{description}</p>
                  </div>
                </div>

                {children}

                {footer && (
                  <div className="mt-6 border-t pt-5 text-sm text-muted-foreground" style={{ borderColor: "hsl(var(--border) / 0.4)" }}>
                    {footer}
                  </div>
                )}
              </div>
            </div>

            {/* Trust indicators below the card */}
            <motion.div
              className="mt-4 flex items-center justify-center gap-6 text-[10px] text-muted-foreground/60"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8 }}
            >
              <span className="flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                AES-256 Encrypted
              </span>
              <span className="flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/></svg>
                SOC 2 Ready
              </span>
              <span className="flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>
                99.9% Uptime
              </span>
            </motion.div>
          </motion.section>
        </div>
      </div>
    </div>
  );
}
