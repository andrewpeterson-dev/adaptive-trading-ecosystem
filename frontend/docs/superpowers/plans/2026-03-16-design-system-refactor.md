# Design System Unification & Full UI Refactor

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the adaptive-trading-ecosystem frontend into a cohesive, professional design system with consistent tokens, components, and layout patterns across all 7 major pages.

**Architecture:** The existing Next.js 14 + Tailwind + CVA + Radix UI + Zustand stack is solid. This refactor standardizes existing design tokens (globals.css), promotes internal components (DashboardPanel, SubNav) to shared/reusable components, and applies consistent patterns across all pages. No framework changes, no new dependencies.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS 3.4, Radix UI, CVA (class-variance-authority), Zustand, react-grid-layout, lightweight-charts, Recharts, Vitest

---

## Chunk 1: Design Tokens & Shared Components (Foundation)

Everything else depends on this. Must be done first.

### Task 1: Standardize Design Tokens in globals.css

**Files:**
- Modify: `src/app/globals.css`
- Modify: `tailwind.config.ts`

The existing tokens are mostly good. Key changes:
1. Add explicit spacing scale CSS custom properties
2. Standardize border-radius to 12px (currently 18px which is too rounded for a trading terminal)
3. Add the spec's status colors as explicit tokens
4. Tighten panel shadows for a more terminal feel

- [ ] **Step 1: Update CSS custom properties in globals.css**

In `:root` and `.dark`, add/update:
```css
/* ── Spacing scale ─────────────────────────────── */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-6: 24px;
--space-8: 32px;
--layout-gutter: 16px;
--panel-padding: 16px;

/* ── Border radius ─────────────────────────────── */
--radius: 0.75rem;          /* 12px — was 1.125rem/18px */
--radius-sm: 0.5rem;        /* 8px */
--radius-lg: 1rem;          /* 16px */
--radius-full: 9999px;

/* ── Status colors (spec) ──────────────────────── */
--status-positive: 166 72% 50%;   /* #2DD4BF teal */
--status-caution: 38 92% 50%;     /* #F59E0B amber */
--status-danger: 349 91% 73%;     /* #FB7185 rose */
--status-muted: 220 9% 64%;       /* #9CA3AF gray */
```

- [ ] **Step 2: Update border-radius throughout globals.css**

Change all component radius values:
- `.app-panel`: `rounded-[24px]` → `rounded-xl` (uses --radius which is now 12px)
- `.app-hero`: `rounded-[26px]` → `rounded-xl`
- `.app-card`: `rounded-[20px]` → `rounded-xl`
- `.app-inset`: `rounded-[18px]` → `rounded-lg`
- `.app-input`: `rounded-2xl` → `rounded-xl`
- `.app-textarea`: `rounded-[22px]` → `rounded-xl`
- `.app-table-shell`: `rounded-[24px]` → `rounded-xl`

- [ ] **Step 3: Add spacing utilities to tailwind.config.ts**

```ts
theme: {
  extend: {
    spacing: {
      'gutter': 'var(--layout-gutter)',
      'panel': 'var(--panel-padding)',
    },
    borderRadius: {
      DEFAULT: 'var(--radius)',       // 12px
      sm: 'var(--radius-sm)',         // 8px
      lg: 'var(--radius-lg)',         // 16px
    },
  }
}
```

- [ ] **Step 4: Verify the app still builds**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npm run build 2>&1 | tail -20`
Expected: Build succeeds (warnings OK, no errors)

- [ ] **Step 5: Commit**

```bash
git add src/app/globals.css tailwind.config.ts
git commit -m "refactor: standardize design tokens — 12px radius, spacing scale, status colors"
```

---

### Task 2: Promote Panel Component to Shared UI

**Files:**
- Modify: `src/components/dashboard/DashboardPanel.tsx` (add exports)
- Create: `src/components/ui/panel.tsx` (re-export from shared location)

The existing `DashboardPanel` with `PanelContainer`/`PanelHeader`/`PanelBody` is already well-built. Promote it so all pages can import from `@/components/ui/panel`.

- [ ] **Step 1: Create shared panel re-export**

Create `src/components/ui/panel.tsx`:
```tsx
// Shared Panel component system
// Re-exports from dashboard implementation for use across all pages
export {
  PanelContainer,
  PanelHeader,
  PanelBody,
  DashboardPanel as Panel,
} from "@/components/dashboard/DashboardPanel";
export type { DashboardPanelProps as PanelProps } from "@/components/dashboard/DashboardPanel";
```

- [ ] **Step 2: Update DashboardPanel to respect layout lock state**

In `src/components/dashboard/DashboardPanel.tsx`, the PanelHeader currently always has `cursor-grab`. It should be conditional. The CSS classes `.layout-locked .dashboard-panel-header` already handle this via globals.css, so verify this works correctly — no code change needed if CSS is handling it.

- [ ] **Step 3: Commit**

```bash
git add src/components/ui/panel.tsx
git commit -m "refactor: promote Panel component to shared UI for cross-page use"
```

---

### Task 3: Create MetricTile Component

**Files:**
- Create: `src/components/ui/metric-tile.tsx`
- Test: `src/components/ui/__tests__/metric-tile.test.tsx`

Extract a reusable MetricTile from the dashboard's MetricsRow pattern.

- [ ] **Step 1: Write the test**

```tsx
// src/components/ui/__tests__/metric-tile.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MetricTile } from "../metric-tile";

describe("MetricTile", () => {
  it("renders label and value", () => {
    render(<MetricTile label="P&L" value="$1,234.56" />);
    expect(screen.getByText("P&L")).toBeInTheDocument();
    expect(screen.getByText("$1,234.56")).toBeInTheDocument();
  });

  it("applies positive color class", () => {
    const { container } = render(
      <MetricTile label="Return" value="+5.2%" sentiment="positive" />
    );
    expect(container.querySelector(".text-positive")).toBeTruthy();
  });

  it("applies negative color class", () => {
    const { container } = render(
      <MetricTile label="Drawdown" value="-2.1%" sentiment="negative" />
    );
    expect(container.querySelector(".text-negative")).toBeTruthy();
  });

  it("renders subtitle when provided", () => {
    render(<MetricTile label="Win Rate" value="68%" subtitle="Last 30 days" />);
    expect(screen.getByText("Last 30 days")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npx vitest run src/components/ui/__tests__/metric-tile.test.tsx 2>&1 | tail -20`
Expected: FAIL — module not found

- [ ] **Step 3: Implement MetricTile**

```tsx
// src/components/ui/metric-tile.tsx
import { cn } from "@/lib/utils";

interface MetricTileProps {
  label: string;
  value: string | number;
  subtitle?: string;
  sentiment?: "positive" | "negative" | "neutral";
  mono?: boolean;
  className?: string;
}

export function MetricTile({
  label,
  value,
  subtitle,
  sentiment,
  mono = true,
  className,
}: MetricTileProps) {
  return (
    <div className={cn("app-panel p-4", className)}>
      <p className="app-metric-label">{label}</p>
      <p
        className={cn(
          mono ? "app-metric-value-mono" : "app-metric-value",
          "mt-1",
          sentiment === "positive" && "text-positive",
          sentiment === "negative" && "text-negative"
        )}
      >
        {value}
      </p>
      {subtitle && (
        <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npx vitest run src/components/ui/__tests__/metric-tile.test.tsx 2>&1 | tail -20`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/metric-tile.tsx src/components/ui/__tests__/metric-tile.test.tsx
git commit -m "feat: add reusable MetricTile component with sentiment colors"
```

---

### Task 4: Create PillTabs Component (Rename SubNav)

**Files:**
- Create: `src/components/ui/pill-tabs.tsx`
- Test: `src/components/ui/__tests__/pill-tabs.test.tsx`
- Modify: `src/components/layout/SubNav.tsx` (re-export for backward compat)

The existing SubNav IS a pill tabs component. Create a proper PillTabs export that can be used with both route-based and state-based tabs.

- [ ] **Step 1: Write the test**

```tsx
// src/components/ui/__tests__/pill-tabs.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PillTabs } from "../pill-tabs";

describe("PillTabs", () => {
  it("renders all tab labels", () => {
    render(
      <PillTabs
        tabs={[
          { key: "overview", label: "Overview" },
          { key: "portfolio", label: "Portfolio" },
          { key: "risk", label: "Risk" },
        ]}
        activeKey="overview"
        onChange={() => {}}
      />
    );
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Risk")).toBeInTheDocument();
  });

  it("calls onChange when tab is clicked", () => {
    const onChange = vi.fn();
    render(
      <PillTabs
        tabs={[
          { key: "a", label: "Tab A" },
          { key: "b", label: "Tab B" },
        ]}
        activeKey="a"
        onChange={onChange}
      />
    );
    fireEvent.click(screen.getByText("Tab B"));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("marks active tab visually", () => {
    render(
      <PillTabs
        tabs={[
          { key: "a", label: "Tab A" },
          { key: "b", label: "Tab B" },
        ]}
        activeKey="a"
        onChange={() => {}}
      />
    );
    const activeTab = screen.getByText("Tab A").closest("button");
    expect(activeTab?.className).toContain("text-primary");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npx vitest run src/components/ui/__tests__/pill-tabs.test.tsx 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: Implement PillTabs**

```tsx
// src/components/ui/pill-tabs.tsx
"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface PillTab {
  key: string;
  label: string;
  icon?: LucideIcon;
}

interface PillTabsProps {
  tabs: PillTab[];
  activeKey: string;
  onChange: (key: string) => void;
  className?: string;
}

export function PillTabs({ tabs, activeKey, onChange, className }: PillTabsProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-1 rounded-full border border-border/50 bg-muted/20 p-1 w-fit",
        className
      )}
      role="tablist"
    >
      {tabs.map((tab) => {
        const active = activeKey === tab.key;
        const Icon = tab.icon;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] font-medium transition-colors",
              active
                ? "bg-primary/12 text-primary border border-primary/20"
                : "text-muted-foreground hover:text-foreground border border-transparent"
            )}
          >
            {Icon && <Icon className="h-3.5 w-3.5" />}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npx vitest run src/components/ui/__tests__/pill-tabs.test.tsx 2>&1 | tail -20`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/pill-tabs.tsx src/components/ui/__tests__/pill-tabs.test.tsx
git commit -m "feat: add reusable PillTabs component for state-based tab navigation"
```

---

### Task 5: Add StatusChip Component

**Files:**
- Create: `src/components/ui/status-chip.tsx`

Standardize all status/risk/mode chips across the product.

- [ ] **Step 1: Create StatusChip**

```tsx
// src/components/ui/status-chip.tsx
import { cn } from "@/lib/utils";

type ChipVariant = "positive" | "warning" | "danger" | "info" | "neutral" | "live" | "paper";

const variantClasses: Record<ChipVariant, string> = {
  positive: "border-emerald-500/25 bg-emerald-500/12 text-emerald-400",
  warning: "border-amber-500/25 bg-amber-500/12 text-amber-400",
  danger: "border-red-500/25 bg-red-500/12 text-red-300",
  info: "border-sky-500/25 bg-sky-500/12 text-sky-300",
  neutral: "border-border/75 bg-muted/45 text-muted-foreground",
  live: "border-emerald-500/25 bg-emerald-500/12 text-emerald-400",
  paper: "border-amber-500/25 bg-amber-500/12 text-amber-600 dark:text-amber-400",
};

interface StatusChipProps {
  variant: ChipVariant;
  label: string;
  pulse?: boolean;
  icon?: React.ReactNode;
  className?: string;
}

export function StatusChip({ variant, label, pulse, icon, className }: StatusChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-[11px] font-bold uppercase tracking-[0.14em]",
        variantClasses[variant],
        className
      )}
    >
      {pulse && (
        <span
          className={cn(
            "h-2 w-2 rounded-full animate-pulse-dot",
            variant === "live" || variant === "positive" ? "bg-emerald-400" : "bg-amber-500"
          )}
        />
      )}
      {icon}
      {label}
    </span>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/components/ui/status-chip.tsx
git commit -m "feat: add StatusChip component for consistent status indicators"
```

---

## Chunk 2: Global Shell Refinements

### Task 6: Refine TradingStatusBar

**Files:**
- Modify: `src/components/layout/TradingStatusBar.tsx`

The existing status bar works well. Minor refinements:
1. Use the new StatusChip for the mode toggle
2. Ensure the "Enable Live" button cannot be accidentally clicked (add a small gap/separator)

- [ ] **Step 1: Add safety gap and improve toggle styling**

In TradingStatusBar.tsx, add a small separator before the "Enable Live" button:
- Add `gap-2` between the paper/live buttons (already exists)
- Add a thin vertical divider `<span className="h-4 w-px bg-border/50" />` between Paper and Live buttons
- This prevents accidental clicks by creating clear visual separation

- [ ] **Step 2: Commit**

```bash
git add src/components/layout/TradingStatusBar.tsx
git commit -m "refactor: improve status bar toggle safety with visual separator"
```

---

### Task 7: Standardize PageHeader Across All Routes

**Files:**
- Modify: `src/components/layout/PageHeader.tsx`

Add optional `onRefresh` and `updatedAt` props to PageHeader so every page can show "Updated <time>" and refresh consistently.

- [ ] **Step 1: Add refresh and timestamp props**

```tsx
interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: React.ReactNode;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
  updatedAt?: Date | null;     // NEW
  onRefresh?: () => void;       // NEW
  className?: string;
}
```

In the component body, if `updatedAt` is provided and `meta` is not, auto-generate the "Updated <time>" pill. If `onRefresh` is provided and no `actions` are given, auto-add a Refresh button.

- [ ] **Step 2: Commit**

```bash
git add src/components/layout/PageHeader.tsx
git commit -m "refactor: add updatedAt and onRefresh to PageHeader for consistency"
```

---

## Chunk 3: Dashboard Layout Refinements

### Task 8: Dashboard Loading & Error States

**Files:**
- Modify: `src/app/dashboard/page.tsx`

Replace the bare `<Loader2>` spinner with `DashboardSkeleton` from the skeleton system. Replace inline error states with `EmptyState`.

- [ ] **Step 1: Use DashboardSkeleton for loading state**

Replace:
```tsx
if (loading) {
  return (
    <div className="app-page">
      <SubNav ... />
      <div className="flex items-center justify-center py-32">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    </div>
  );
}
```

With:
```tsx
if (loading) {
  return (
    <div className="app-page">
      <SubNav ... />
      <DashboardSkeleton />
    </div>
  );
}
```

- [ ] **Step 2: Use EmptyState for error and not-configured states**

Replace the inline error/not-configured blocks with `<EmptyState>` calls, keeping the same content but using the consistent component.

- [ ] **Step 3: Commit**

```bash
git add src/app/dashboard/page.tsx
git commit -m "refactor: use skeleton and EmptyState components in dashboard"
```

---

### Task 9: Dashboard Grid Lock Behavior Verification

**Files:**
- Modify: `src/app/dashboard/page.tsx`

The spec requires that clicking panel body NEVER triggers drag. The current implementation uses `draggableHandle=".dashboard-panel-header"` which is correct. Verify and add a comment.

- [ ] **Step 1: Verify draggable handle restriction**

In the ResponsiveGridLayout component, verify these props:
- `isDraggable={!isLayoutLocked}` ✓
- `isResizable={!isLayoutLocked}` ✓
- `draggableHandle=".dashboard-panel-header"` ✓

No code changes needed if these are already correct (they are). Just verify by reviewing.

- [ ] **Step 2: Ensure Lock/Unlock toggle has clear visual state**

The existing lock button uses `!isLayoutLocked && "!border-primary/40 !bg-primary/5"`. This is sufficient but could use the StatusChip pattern. Update to use clearer labeling:
- Locked: show Lock icon + "Layout Locked" text
- Unlocked: show Unlock icon + "Editing Layout" text with primary highlight

- [ ] **Step 3: Commit if changes were made**

---

## Chunk 4: Builder Page Refinements

### Task 10: Builder Mode Selection Buttons

**Files:**
- Modify: `src/components/strategy-builder/StrategyBuilder.tsx`

The builder already has Manual/AI-Assisted/Template mode buttons. Ensure they use the `app-segmented` / `app-segment` CSS classes for consistent segmented control styling.

- [ ] **Step 1: Wrap mode buttons in segmented control**

Find the mode selection section and ensure it uses:
```tsx
<div className="app-segmented">
  <button className={cn("app-segment", mode === "manual" && "app-toggle-active")}>
    Manual
  </button>
  <button className={cn("app-segment", mode === "ai" && "app-toggle-active")}>
    AI-Assisted
  </button>
  <button className={cn("app-segment", mode === "template" && "app-toggle-active")}>
    From Template
  </button>
</div>
```

- [ ] **Step 2: Ensure validation banner doesn't cause layout shift**

Find the "Finish required inputs" banner. It should:
- Use `min-h-[48px]` to reserve space
- Use `sticky bottom-0` or fixed position within the builder
- Apply `app-card` styling with amber border for consistency

- [ ] **Step 3: Commit**

```bash
git add src/components/strategy-builder/StrategyBuilder.tsx
git commit -m "refactor: use segmented controls for builder mode selection, fix validation banner"
```

---

### Task 11: Builder Form Components

**Files:**
- Modify: `src/components/strategy-builder/StrategyBuilder.tsx`

Ensure all form fields use the design system classes:
- Inputs: `app-input`
- Textareas: `app-textarea`
- Selects: `app-select`
- Labels: `app-label`

- [ ] **Step 1: Audit and update form field classes**

Search for any raw `<input>`, `<select>`, `<textarea>` that don't use the `app-*` classes and update them.

- [ ] **Step 2: Ensure error styling is consistent**

Validation errors should use:
```tsx
<p className="mt-1 text-xs text-red-400">Required field</p>
```

Not custom styles or layout-shifting elements.

- [ ] **Step 3: Commit**

```bash
git add src/components/strategy-builder/StrategyBuilder.tsx
git commit -m "refactor: standardize builder form inputs to design system classes"
```

---

### Task 12: Entry Builder Visual Hierarchy

**Files:**
- Modify: `src/components/strategy-builder/ConditionGroup.tsx`
- Modify: `src/components/strategy-builder/ConditionRow.tsx`

- [ ] **Step 1: Ensure ConditionGroup uses app-card for group containers**

Each condition group should be wrapped in `app-card` with clear labeling.

- [ ] **Step 2: Ensure condition rows have consistent select sizing**

All selects (Signal, Trigger, Threshold) should be the same width and use `app-select`.

- [ ] **Step 3: Align "Add Condition" and "Add Group" buttons**

Both buttons should use `Button variant="secondary" size="sm"` and be left-aligned.

- [ ] **Step 4: Commit**

```bash
git add src/components/strategy-builder/ConditionGroup.tsx src/components/strategy-builder/ConditionRow.tsx
git commit -m "refactor: improve entry builder visual hierarchy with consistent cards and selects"
```

---

## Chunk 5: Strategies Library & Bots Fleet

### Task 13: Strategies Page Consistency

**Files:**
- Modify: `src/app/strategies/page.tsx`

The strategies page is already well-built. Minor fixes:
1. Use `Skeleton` loaders instead of bare `Loader2` spinner
2. Ensure all badges use the `Badge` component (already mostly done)
3. Align the overflow menu with Radix UI Popover instead of manual `position: absolute`

- [ ] **Step 1: Replace loading spinner with CardSkeleton**

```tsx
{loading ? (
  <div className="space-y-3">
    <CardSkeleton />
    <CardSkeleton />
    <CardSkeleton />
  </div>
) : ...}
```

- [ ] **Step 2: Ensure "Updated <time>" badge alignment**

The `relativeTime` display already uses Badge. Verify consistent alignment — the "Updated" badge should always be at the far right or at the end of the meta row.

- [ ] **Step 3: Commit**

```bash
git add src/app/strategies/page.tsx
git commit -m "refactor: use skeleton loaders in strategies page"
```

---

### Task 14: Bots Fleet Page

**Files:**
- Modify: `src/app/bots/page.tsx`
- Modify: `src/components/cerberus/BotControlPanel.tsx`

The bots page currently just wraps BotControlPanel. Ensure the BotControlPanel uses:
1. StatusChip for bot status (running/stopped/monitoring/learning)
2. StatusChip for risk level (low/medium/high)
3. Consistent metric layout for P&L, Trades, Win Rate
4. Button component for Stop/Deploy actions

- [ ] **Step 1: Review BotControlPanel and update status indicators**

Replace any inline status styling with StatusChip:
```tsx
<StatusChip variant="positive" label="Running" pulse />
<StatusChip variant="danger" label="Stopped" />
<StatusChip variant="warning" label="Learning" />
```

- [ ] **Step 2: Use MetricTile for P&L display in bot cards**

Where P&L is shown inline, use the MetricTile pattern or at minimum the `app-metric-value-mono` class.

- [ ] **Step 3: Commit**

```bash
git add src/app/bots/page.tsx src/components/cerberus/BotControlPanel.tsx
git commit -m "refactor: standardize bot fleet status chips and metric display"
```

---

## Chunk 6: Trade Workspace Refinements

### Task 15: Chart Toolbar Standardization

**Files:**
- Modify: `src/components/charts/TradingChart.tsx`

The chart already has timeframe and indicator controls. Ensure they use the design system:
1. Timeframe buttons → `app-segmented` with `app-segment` items
2. Indicator toggles → `app-toggle` / `app-toggle-active` classes
3. Toolbar container → `app-toolbar` class

- [ ] **Step 1: Wrap timeframe buttons in segmented control**

```tsx
<div className="app-segmented">
  {["1m","5m","15m","1H","4H","1D","1W"].map(tf => (
    <button
      key={tf}
      className={cn("app-segment text-xs", timeframe === tf && "app-toggle-active")}
      onClick={() => setTimeframe(tf)}
    >
      {tf}
    </button>
  ))}
</div>
```

- [ ] **Step 2: Wrap indicator toggles in toolbar**

```tsx
<div className="app-toolbar">
  {indicators.map(ind => (
    <button
      key={ind.key}
      className={cn("app-toggle text-xs", ind.active && "app-toggle-active")}
      onClick={() => toggleIndicator(ind.key)}
    >
      {ind.label}
    </button>
  ))}
</div>
```

- [ ] **Step 3: Ensure chart doesn't overflow container**

Add `overflow-hidden` to the chart container div if not already present.

- [ ] **Step 4: Commit**

```bash
git add src/components/charts/TradingChart.tsx
git commit -m "refactor: standardize chart toolbar with design system segmented controls"
```

---

### Task 16: Connection Status Panels

**Files:**
- Modify: `src/components/trading/TradingConnectionStatus.tsx`

Ensure connection status uses StatusChip and Panel components.

- [ ] **Step 1: Use StatusChip for connection states**

```tsx
<StatusChip variant="positive" label="Connected" pulse />
<StatusChip variant="danger" label="Disconnected" />
```

- [ ] **Step 2: Commit**

```bash
git add src/components/trading/TradingConnectionStatus.tsx
git commit -m "refactor: use StatusChip in trading connection status"
```

---

### Task 17: Order Ticket Panel

**Files:**
- Modify: `src/components/trading/StockOrderTicket.tsx`

Ensure the order ticket uses design system components:
1. Buy/Sell → `app-segmented` with `app-segment`
2. Shares vs Dollars → `app-segmented` with `app-segment`
3. Order type → `app-select`
4. Inputs → `app-input`
5. Submit button → `Button variant="primary"`

- [ ] **Step 1: Audit and update order form controls**

Review StockOrderTicket and ensure all form elements use the design system classes.

- [ ] **Step 2: Commit**

```bash
git add src/components/trading/StockOrderTicket.tsx
git commit -m "refactor: standardize order ticket form to design system"
```

---

### Task 18: Watchlist Row Consistency

**Files:**
- Modify: `src/components/trading/WatchlistRow.tsx`
- Test: `src/components/trading/__tests__/watchlist-row.test.tsx`

- [ ] **Step 1: Write the test**

```tsx
// src/components/trading/__tests__/watchlist-row.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { WatchlistRow } from "../WatchlistRow";

describe("WatchlistRow", () => {
  it("renders symbol and price", () => {
    render(
      <WatchlistRow
        symbol="AAPL"
        price={182.52}
        change={1.23}
        changePercent={0.68}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    );
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("$182.52")).toBeInTheDocument();
  });

  it("shows positive change in green", () => {
    const { container } = render(
      <WatchlistRow
        symbol="AAPL"
        price={182.52}
        change={1.23}
        changePercent={0.68}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    );
    // Positive changes should use text-positive class
    const changeEl = container.querySelector(".text-positive, .app-positive, .text-emerald");
    expect(changeEl).toBeTruthy();
  });
});
```

Note: Adapt this test to match the actual WatchlistRow props — read the component first to verify the interface.

- [ ] **Step 2: Verify WatchlistRow uses consistent heights and alignment**

Each row should have:
- `h-12` or `py-3` for consistent row height
- Remove button: icon-only with `aria-label="Remove <symbol>"`
- Price display: `font-mono tabular-nums`

- [ ] **Step 3: Commit**

```bash
git add src/components/trading/WatchlistRow.tsx src/components/trading/__tests__/watchlist-row.test.tsx
git commit -m "refactor: standardize watchlist row height and alignment, add tests"
```

---

## Chunk 7: Intelligence Pages

### Task 19: Intelligence Page Skeleton Loading

**Files:**
- Modify: `src/app/ai-intelligence/page.tsx`
- Modify: `src/components/intelligence/NewsFeed.tsx`
- Modify: `src/components/intelligence/SectorMomentum.tsx`

- [ ] **Step 1: Add loading states to intelligence components**

Each intelligence component (RiskGauge, NewsFeed, SectorMomentum, etc.) should show `Skeleton` placeholders while loading. If they don't already have loading states, add them.

- [ ] **Step 2: Ensure SectorMomentum uses consistent decimal formatting**

All percentage values should format to 2 decimal places: `value.toFixed(2)`.

- [ ] **Step 3: Ensure NewsFeed rows have consistent height**

Each news item should use `py-3 border-b border-border/40` for consistent spacing.

- [ ] **Step 4: Commit**

```bash
git add src/app/ai-intelligence/page.tsx src/components/intelligence/NewsFeed.tsx src/components/intelligence/SectorMomentum.tsx
git commit -m "refactor: add skeleton loading and consistent formatting to intelligence page"
```

---

### Task 20: Models & Quant Pages

**Files:**
- Modify: `src/app/models/page.tsx`
- Modify: `src/app/quant/page.tsx`

- [ ] **Step 1: Ensure both pages use Panel component for sections**

Import Panel from `@/components/ui/panel` and wrap each content section.

- [ ] **Step 2: Use Skeleton loaders for loading states**

Replace any "Loading..." text or bare spinners with the appropriate Skeleton components.

- [ ] **Step 3: Commit**

```bash
git add src/app/models/page.tsx src/app/quant/page.tsx
git commit -m "refactor: use Panel and Skeleton components in models and quant pages"
```

---

## Chunk 8: Responsiveness & Accessibility

### Task 21: Responsive Panel Stacking

**Files:**
- Modify: `src/app/globals.css`

- [ ] **Step 1: Add responsive panel stacking rule**

Below 900px, panels should stack. The existing grid layouts mostly handle this. Add:
```css
@media (max-width: 900px) {
  .react-grid-layout {
    display: flex !important;
    flex-direction: column !important;
    height: auto !important;
  }
  .react-grid-item {
    position: relative !important;
    width: 100% !important;
    height: auto !important;
    min-height: 200px;
    transform: none !important;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add src/app/globals.css
git commit -m "refactor: add responsive panel stacking below 900px"
```

---

### Task 22: Focus States & Keyboard Navigation

**Files:**
- Modify: `src/app/globals.css`

- [ ] **Step 1: Verify focus-visible states**

The button component already has `focus-visible:ring-2 focus-visible:ring-ring/60`. Verify this applies to:
- All `app-button-*` classes
- All `app-input` / `app-select` fields
- Tab triggers

If any are missing, add `focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-0` to the relevant CSS classes.

- [ ] **Step 2: Commit if changes were made**

---

### Task 23: Final QA Pass

**Files:** All modified files

- [ ] **Step 1: Build verification**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npm run build 2>&1 | tail -30`
Expected: Build succeeds

- [ ] **Step 2: Run all tests**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npx vitest run 2>&1 | tail -30`
Expected: All tests pass

- [ ] **Step 3: Lint check**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npx next lint 2>&1 | tail -20`
Expected: No errors (warnings OK)

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "refactor: complete design system unification — all pages use consistent tokens and components"
```

---

## Execution Strategy

The 8 chunks above can be partially parallelized:

- **Chunk 1** (Tasks 1-5): MUST be first — everything depends on tokens + components
- **Chunks 2-7** (Tasks 6-20): Can run in parallel after Chunk 1 completes
- **Chunk 8** (Tasks 21-23): Must be last — final QA

Recommended subagent breakdown:
1. **Agent 1**: Chunk 1 (foundation)
2. **Agent 2**: Chunks 2+3 (shell + dashboard)
3. **Agent 3**: Chunk 4 (builder)
4. **Agent 4**: Chunks 5+6 (strategies/bots + trade)
5. **Agent 5**: Chunk 7 (intelligence)
6. **Agent 6**: Chunk 8 (responsive/a11y/QA)
