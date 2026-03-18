"use client";

import Link from "next/link";
import { BrandLogo } from "./BrandLogo";

// Ticker symbols shown in the scrolling tape at the top
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

// Chart lines rendered in the animated background
const CHART_LINES = [
  // [top%, duration(s), delay(s), color, opacity, strokeWidth, path-variant]
  { top: 18, duration: 22, delay: 0, color: "#10b981", opacity: 0.055, height: 60, variant: 0 },
  { top: 32, duration: 31, delay: -8, color: "#3b82f6", opacity: 0.065, height: 48, variant: 1 },
  { top: 45, duration: 26, delay: -14, color: "#10b981", opacity: 0.04, height: 72, variant: 2 },
  { top: 58, duration: 38, delay: -5, color: "#ef4444", opacity: 0.045, height: 44, variant: 3 },
  { top: 68, duration: 20, delay: -19, color: "#3b82f6", opacity: 0.055, height: 56, variant: 0 },
  { top: 78, duration: 34, delay: -3, color: "#10b981", opacity: 0.035, height: 40, variant: 1 },
  { top: 25, duration: 44, delay: -22, color: "#3b82f6", opacity: 0.03, height: 64, variant: 2 },
  { top: 85, duration: 28, delay: -11, color: "#ef4444", opacity: 0.04, height: 36, variant: 3 },
];

// SVG path variants that look like stock chart segments
function getChartPath(variant: number, h: number): string {
  switch (variant) {
    case 0:
      // Uptrend with pullback
      return `M0,${h} L80,${h * 0.75} L160,${h * 0.82} L240,${h * 0.5} L320,${h * 0.6} L400,${h * 0.3} L480,${h * 0.42} L560,${h * 0.18} L640,${h * 0.28} L720,${h * 0.05} L800,${h * 0.15}`;
    case 1:
      // Volatile with spikes
      return `M0,${h * 0.5} L60,${h * 0.3} L120,${h * 0.7} L180,${h * 0.2} L240,${h * 0.65} L300,${h * 0.15} L360,${h * 0.55} L420,${h * 0.35} L480,${h * 0.6} L540,${h * 0.25} L600,${h * 0.45} L660,${h * 0.1} L720,${h * 0.4} L800,${h * 0.2}`;
    case 2:
      // Gradual downtrend
      return `M0,${h * 0.1} L100,${h * 0.2} L200,${h * 0.15} L300,${h * 0.4} L400,${h * 0.35} L500,${h * 0.55} L600,${h * 0.5} L700,${h * 0.7} L800,${h * 0.85}`;
    case 3:
      // Consolidation then breakout
      return `M0,${h * 0.6} L80,${h * 0.55} L160,${h * 0.62} L240,${h * 0.58} L320,${h * 0.6} L400,${h * 0.4} L440,${h * 0.2} L520,${h * 0.25} L600,${h * 0.1} L700,${h * 0.15} L800,${h * 0.05}`;
    default:
      return `M0,${h * 0.5} L800,${h * 0.5}`;
  }
}

// Dot grid dot positions (pre-computed to avoid runtime layout thrash)
const DOT_GRID = Array.from({ length: 12 * 8 }, (_, i) => ({
  x: (i % 12) * 8.5,
  y: Math.floor(i / 12) * 14,
  delay: ((i % 7) * 0.4 + Math.floor(i / 7) * 0.3).toFixed(1),
}));

const HIGHLIGHTS = [
  {
    title: "Real data only",
    description:
      "Portfolio, risk, and order views stay grounded in actual broker and model data.",
  },
  {
    title: "Per-user broker security",
    description:
      "Credentials remain encrypted and isolated for each account across paper and live workflows.",
  },
  {
    title: "One calm workspace",
    description:
      "Strategy design, execution, analytics, and Cerberus guidance live in the same interface.",
  },
];

interface AuthShellProps {
  title: string;
  description: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export function AuthShell({
  title,
  description,
  children,
  footer,
}: AuthShellProps) {
  // Duplicate ticker items so the seamless loop works at any viewport width
  const tickerItems = [...TICKER_ITEMS, ...TICKER_ITEMS];

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden">
      {/* ── Keyframe definitions injected as a style tag ─────────────────── */}
      <style>{`
        @keyframes auth-ticker-scroll {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        @keyframes auth-chart-drift {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(110vw); }
        }
        @keyframes auth-logo-pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0); }
          50%       { box-shadow: 0 0 28px 8px rgba(59,130,246,0.22), 0 0 56px 16px rgba(59,130,246,0.08); }
        }
        @keyframes auth-dot-pulse {
          0%, 100% { opacity: 0.18; }
          50%       { opacity: 0.06; }
        }
        @keyframes auth-fade-up {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes auth-card-in {
          from { opacity: 0; transform: translateY(16px) scale(0.985); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>

      {/* ── Animated stock chart background ──────────────────────────────── */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 overflow-hidden"
        style={{ zIndex: 0 }}
      >
        {/* Deep dark base gradient */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 80% 60% at 15% 40%, rgba(59,130,246,0.06) 0%, transparent 60%), " +
              "radial-gradient(ellipse 60% 50% at 85% 70%, rgba(16,185,129,0.04) 0%, transparent 55%)",
          }}
        />

        {/* Dot grid */}
        <div className="absolute inset-0 flex items-center justify-center">
          <svg
            width="100%"
            height="100%"
            className="absolute inset-0"
            style={{ opacity: 1 }}
          >
            {DOT_GRID.map((dot, i) => (
              <circle
                key={i}
                cx={`${dot.x}%`}
                cy={`${dot.y}%`}
                r="1"
                fill="rgba(148,163,184,0.18)"
                style={{
                  animation: `auth-dot-pulse ${2.8 + (i % 4) * 0.6}s ease-in-out infinite`,
                  animationDelay: `${dot.delay}s`,
                }}
              />
            ))}
          </svg>
        </div>

        {/* Scrolling chart lines */}
        {CHART_LINES.map((line, i) => {
          const svgW = 800;
          const path = getChartPath(line.variant, line.height);
          return (
            <div
              key={i}
              className="absolute"
              style={{
                top: `${line.top}%`,
                left: 0,
                width: "800px",
                height: `${line.height}px`,
                animation: `auth-chart-drift ${line.duration}s linear infinite`,
                animationDelay: `${line.delay}s`,
              }}
            >
              <svg
                width={svgW}
                height={line.height}
                viewBox={`0 0 ${svgW} ${line.height}`}
                fill="none"
                preserveAspectRatio="none"
              >
                <path
                  d={path}
                  fill="none"
                  stroke={line.color}
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={line.opacity}
                />
              </svg>
            </div>
          );
        })}
      </div>

      {/* ── Ticker tape ──────────────────────────────────────────────────── */}
      <div
        aria-hidden="true"
        className="relative w-full overflow-hidden border-b"
        style={{
          zIndex: 10,
          height: "30px",
          borderColor: "hsl(var(--border) / 0.4)",
          background:
            "linear-gradient(90deg, hsl(var(--surface-1) / 0.88), hsl(var(--surface-2) / 0.88))",
          backdropFilter: "blur(12px)",
        }}
      >
        {/* Left fade mask */}
        <div
          className="pointer-events-none absolute inset-y-0 left-0 z-10 w-16"
          style={{
            background:
              "linear-gradient(90deg, hsl(var(--background)) 0%, transparent 100%)",
          }}
        />
        {/* Right fade mask */}
        <div
          className="pointer-events-none absolute inset-y-0 right-0 z-10 w-16"
          style={{
            background:
              "linear-gradient(270deg, hsl(var(--background)) 0%, transparent 100%)",
          }}
        />

        <div
          className="flex h-full items-center whitespace-nowrap"
          style={{
            animation: "auth-ticker-scroll 38s linear infinite",
            width: "max-content",
          }}
        >
          {tickerItems.map((item, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1.5 px-5 text-[11px] font-medium tracking-wide"
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              <span className="font-semibold text-muted-foreground">
                {item.symbol}
              </span>
              <span
                style={{
                  color: item.positive
                    ? "hsl(var(--positive))"
                    : "hsl(var(--negative))",
                }}
              >
                {item.change}
              </span>
              {i < tickerItems.length - 1 && (
                <span
                  className="ml-3 text-muted-foreground/25"
                  style={{ fontSize: "10px" }}
                >
                  •
                </span>
              )}
            </span>
          ))}
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div
        className="relative flex flex-1 items-center justify-center px-4 py-10 sm:px-6 lg:px-8"
        style={{ zIndex: 10 }}
      >
        <div className="grid w-full max-w-6xl gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">

          {/* ── Left column: branding + highlights ─────────────────────── */}
          <section
            className="hidden space-y-8 lg:block"
            style={{ animation: "auth-fade-up 0.55s ease-out both" }}
          >
            <Link href="/" className="inline-flex items-center gap-3 group">
              {/* Logo with glow pulse */}
              <div
                className="flex items-center justify-center rounded-2xl"
                style={{
                  width: 72,
                  height: 72,
                  background:
                    "linear-gradient(135deg, hsl(var(--surface-2) / 0.9), hsl(var(--surface-3) / 0.9))",
                  border: "1px solid hsl(var(--border) / 0.5)",
                  animation: "auth-logo-pulse 3.6s ease-in-out infinite",
                }}
              >
                <BrandLogo size={64} className="h-16 w-16" />
              </div>
              <div>
                <p className="text-base font-semibold tracking-tight text-foreground group-hover:text-primary transition-colors duration-200">
                  Adaptive Trading
                </p>
                <p className="text-sm text-muted-foreground">
                  Strategy intelligence with execution discipline
                </p>
              </div>
            </Link>

            <div className="space-y-5">
              <p className="app-kicker">Trading Workspace</p>
              <h1 className="max-w-xl text-5xl font-semibold tracking-tight text-foreground">
                A calmer, sharper control room for systematic trading.
              </h1>
              <p className="max-w-xl text-base leading-8 text-muted-foreground">
                Build strategies, manage risk, and transition from paper to live
                execution inside a product that feels precise instead of noisy.
              </p>
            </div>

            <div className="grid gap-4">
              {HIGHLIGHTS.map((item, i) => (
                <div
                  key={item.title}
                  className="app-panel p-5 transition-all duration-200 hover:border-primary/20"
                  style={{
                    animation: `auth-fade-up 0.55s ease-out both`,
                    animationDelay: `${0.1 + i * 0.08}s`,
                  }}
                >
                  <div className="flex items-start gap-3">
                    {/* Accent dot */}
                    <div
                      className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: "hsl(var(--primary))" }}
                    />
                    <div>
                      <p className="text-sm font-semibold text-foreground">
                        {item.title}
                      </p>
                      <p className="mt-1 text-sm leading-7 text-muted-foreground">
                        {item.description}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ── Right column: form card ─────────────────────────────────── */}
          <section
            className="app-panel overflow-hidden p-1"
            style={{ animation: "auth-card-in 0.5s ease-out both", animationDelay: "0.05s" }}
          >
            <div className="app-card rounded-[28px] p-6 sm:p-8">
              <div className="mb-8 space-y-4">
                {/* Mobile logo */}
                <div className="inline-flex items-center gap-3 lg:hidden">
                  <div
                    className="flex items-center justify-center rounded-xl"
                    style={{
                      width: 52,
                      height: 52,
                      background:
                        "linear-gradient(135deg, hsl(var(--surface-2) / 0.9), hsl(var(--surface-3) / 0.9))",
                      border: "1px solid hsl(var(--border) / 0.5)",
                      animation: "auth-logo-pulse 3.6s ease-in-out infinite",
                    }}
                  >
                    <BrandLogo size={40} className="h-10 w-10" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      Adaptive Trading
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Strategy intelligence workspace
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="app-kicker">Account Access</p>
                  <h2 className="text-3xl font-semibold tracking-tight text-foreground">
                    {title}
                  </h2>
                  <p className="text-sm leading-7 text-muted-foreground">
                    {description}
                  </p>
                </div>
              </div>

              {children}

              {footer && (
                <div className="mt-6 border-t border-border/60 pt-5 text-sm text-muted-foreground">
                  {footer}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
