# Strategy Builder Redesign — Design Spec

## Problem

The current strategy builder is a 1,500-line monolith (`StrategyBuilder.tsx`) that serves as the app homepage. It crams three distinct creation modes (Manual, AI-Assisted, From Template) into one scrollable form with local state. The AI mode is a modal dialog, not a collaborative experience. There is no template gallery. The logic tree preview is a placeholder.

## Goals

1. Make AI-Assisted the default, primary builder experience with a conversational chat interface
2. Add a visual template gallery for "From Template" mode
3. Clean up Manual mode with better layout and collapsible sections
4. Move the landing page to Dashboard — builder gets its own route
5. Break the monolith into focused, maintainable components

## Non-Goals

- Mobile-first design (desktop is primary, responsive is nice-to-have)
- Backtest integration changes
- Changing existing backend endpoints (new ones added for templates only)

## Backend Changes Required

Small additions to support template gallery:
- Add `is_system` boolean column to `StrategyTemplate` model (migration)
- Add `GET /api/strategies/templates` endpoint (list/filter system templates)
- Seed 6 starter templates via startup script (idempotent)

---

## Architecture

### Routing Changes

| Route | Before | After |
|-------|--------|-------|
| `/` | Strategy Builder | Dashboard (portfolio overview) |
| `/strategy-builder` | N/A | New strategy builder page (AI default) |
| `/strategy-builder/edit/[id]` | N/A | Edit existing strategy |
| `/edit/[id]` | Edit strategy | Redirect to `/strategy-builder/edit/[id]` |
| `/strategies` | Strategy library | No change |

### Component Decomposition

The 1,500-line `StrategyBuilder.tsx` is replaced by:

| Component | Responsibility | Approximate Size |
|-----------|---------------|-----------------|
| `StrategyBuilderPage.tsx` | Page wrapper, mode tabs (AI/Manual/Template), 60/40 layout shell | ~150 lines |
| `AIChat.tsx` | Left panel in AI mode: message history, input, Cerberus integration | ~400 lines |
| `StrategyPreview.tsx` | Right panel (shared across all modes): live preview of strategy, entry/exit/risk cards, action buttons | ~300 lines |
| `ManualBuilder.tsx` | Left panel in Manual mode: accordion form sections, condition group CRUD | ~400 lines |
| `TemplateGallery.tsx` | Left panel in Template mode: card grid with filters | ~200 lines |

**Deleted files:**
- `AIStrategyGeneratorDialog.tsx` — replaced entirely by `AIChat.tsx`. The floating Cerberus widget continues to use `useStrategyBuilderStore.pendingSpec` to handoff specs to the builder page.

Existing components reused without changes:
- `ConditionGroup.tsx` (110 lines)
- `ConditionRow.tsx` (260 lines)
- `DiagnosticPanel.tsx` (165 lines) — rendered inside StrategyPreview
- `ExplainerPanel.tsx` (122 lines) — rendered inside StrategyPreview below diagnostics
- `AccordionSection.tsx` (135 lines)

### State Management

**Builder state**: Lifted into a Zustand store (`useBuilderStore`) replacing the 30+ `useState` calls in the current monolith. `useStrategyBuilderStore` (the old store with just `pendingSpec`) is kept only for Cerberus widget → builder handoff. The builder page consumes `pendingSpec` on mount and writes to `useBuilderStore`.

**Full store shape:**

```typescript
interface BuilderState {
  // Identity
  name: string;
  description: string;
  action: "BUY" | "SELL";
  timeframe: string;
  strategyType: "manual" | "ai_generated" | "custom";
  sourcePrompt: string;

  // Universe
  symbols: string[];
  symbolInput: string; // transient UI state

  // Conditions
  conditionGroups: ConditionGroup[]; // entry conditions
  exitConditionGroups: ConditionGroup[]; // exit conditions (same shape as entry)

  // Risk
  stopLoss: number;
  takeProfit: number;
  positionSize: number;
  trailingStopEnabled: boolean;
  trailingStop: number;
  exitAfterBarsEnabled: boolean;
  exitAfterBars: number;
  exitLogic: "stop_target" | "indicator_reversal" | "time_stop" | "hybrid";
  cooldownBars: number;
  maxTradesPerDay: number;
  maxExposurePct: number;
  maxLossPct: number;

  // Execution
  orderType: string;
  backtestPeriod: string;
  commissionPct: number;
  slippagePct: number;

  // AI context
  aiContext: StrategyAiContext | null;
  aiBaselineFingerprint: string | null; // for detecting post-AI edits

  // Computed / derived (set by effects, not user)
  diagnostics: DiagnosticReport | null;
  explanation: StrategyExplanation | null;
  indicatorPreviews: Record<string, unknown>;

  // Actions
  setField: (field: string, value: unknown) => void;
  loadFromSpec: (spec: StrategySpec) => void;
  loadFromStrategy: (strategy: StrategyRecord) => void;
  reset: () => void;
}
```

**Draft persistence**: Store subscribes to changes and persists to `localStorage` under `"strategy_builder_draft"` (same key as current, via Zustand `persist` middleware).

---

## AI-Assisted Mode (Default)

### Layout

Fixed 60/40 horizontal split. Below `xl` breakpoint (1280px), stacks vertically: chat on top, preview below.

```
┌─────────────────────────────────┬──────────────────────┐
│  [AI-Assisted] [Manual] [Tmpl]  │                      │
│─────────────────────────────────│   Live Preview       │
│                                 │                      │
│  Chat History                   │   Strategy Name      │
│  ┌─────────────────────────┐    │   Action · TF · Syms │
│  │ You: Build me a...      │    │                      │
│  └─────────────────────────┘    │   ┌─ Entry ────────┐ │
│  ┌─────────────────────────┐    │   │ RSI < 30 AND   │ │
│  │ Cerberus: Here's my     │    │   │ MACD cross up  │ │
│  │ approach...              │    │   └────────────────┘ │
│  │                          │    │   ┌─ Exit ─────────┐ │
│  │ Should I add volume?     │    │   │ RSI > 70 OR    │ │
│  └─────────────────────────┘    │   │ MACD cross dn  │ │
│                                 │   └────────────────┘ │
│                                 │   ┌─ Risk ─────────┐ │
│                                 │   │ SL: 3% TP: 8%  │ │
│                                 │   └────────────────┘ │
│                                 │                      │
│                                 │   [Deploy Bot] [Save]│
│  ┌──────────────────────┐ [↑]   │                      │
│  │ Describe strategy... │       │                      │
│  └──────────────────────┘       │                      │
└─────────────────────────────────┴──────────────────────┘
```

### Chat Flow

1. User types a strategy idea in natural language
2. Message sent to `POST /api/ai/chat` with `mode: "strategy"` (`"strategy"` is already a valid `ConversationMode`)
3. Cerberus responds with clarifying questions OR a full strategy JSON in a fenced code block
4. If JSON is returned, `parseStrategySpec()` extracts it → `specToBuilderFields()` converts to store fields → store updates → preview reflects changes
5. User can iterate: "Change stop loss to 2%" → Cerberus returns updated JSON → preview updates

### Chat Component Details

- Messages rendered as cards: user messages right-aligned (dark), Cerberus left-aligned (blue border)
- Cerberus messages support markdown rendering (already have `react-markdown` + `remark-gfm`)
- Sticky input at bottom with send button
- Thread ID maintained across messages (existing `activeThreadId` pattern)
- Loading state: typing indicator while Cerberus responds

### Preview Component Details

- Reads from `useBuilderStore` (reactive)
- Sections with color-coded borders:
  - Strategy header (name, action, timeframe, symbols) — neutral
  - Entry conditions — blue (`#3b82f6`)
  - Exit conditions — red (`#ef4444`)
  - Risk controls — orange/amber (`#f59e0b`)
- Each condition rendered as readable rule text
- DiagnosticPanel rendered below risk controls (health score ring + issues)
- ExplainerPanel rendered below diagnostics (AI analysis summary)
- Preview is read-only — no inline editing. Users click "Edit in Manual" to modify fields directly.

### Action Buttons (bottom of preview)

- **"Deploy Bot"** (primary): Two-step operation:
  1. `POST /api/strategies/create` — saves strategy to DB, returns `strategy_id`
  2. `POST /api/ai/chat` with a tool-calling message that invokes `createBot` with the strategy config
- **"Save Draft"**: `POST /api/strategies/create` only — saves without deploying
- **"Edit in Manual"**: Switches mode tab to Manual, state preserved in store

---

## From Template Mode

### Layout

Same 60/40 split. Left panel shows template gallery. Right panel shows preview of selected template.

Mode tabs remain at the top of the left panel (same position as AI/Manual modes).

### Template Cards (3 per row in left panel)

Each card contains:
- Strategy name + type badge (color-coded: green=Momentum, purple=Mean Reversion, blue=Breakout, orange=Trend)
- 2-line description
- Indicator pills (small badges: RSI, MACD, BB, etc.)
- "Use Template" button

### Filter Bar

- Strategy Type dropdown: All, Momentum, Mean Reversion, Breakout, Trend Following
- Timeframe dropdown: All, Intraday (1m-1H), Swing (4H-1D), Position (1W)
- Search input (filters by name/description)

### Starter Templates (6 seeded)

| Name | Type | Indicators | Entry Logic |
|------|------|-----------|-------------|
| RSI Oversold Bounce | Momentum | RSI, Volume | RSI < 30 AND Vol > 20d avg |
| Bollinger Squeeze | Mean Reversion | BB, ATR | Price < Lower BB AND ATR expanding |
| MACD Crossover | Momentum | MACD, EMA | MACD crosses above signal AND price > EMA(200) |
| Volume Breakout | Breakout | Volume, SMA | Vol > 2x 20d avg AND price breaks SMA(50) |
| Golden Cross | Trend | SMA | SMA(50) crosses above SMA(200) |
| Stochastic Reversal | Mean Reversion | Stoch, RSI | Stoch K < 20 AND RSI < 35 |

Templates are stored as `StrategyTemplate` records with `is_system=True` (new column). Seeded via an idempotent startup function that runs in `api/main.py` after DB init.

### Backend: Template Endpoint

```
GET /api/strategies/templates?type=momentum&timeframe=1D
```

Returns system templates (`is_system=True`), filterable by `strategy_type` and `timeframe`. Added to existing `api/routes/strategies.py`.

### "Use Template" Flow

Click "Use Template" → template config loaded into `useBuilderStore` → mode switches to AI → preview shows the template strategy → user can chat with Cerberus to refine ("Make this more aggressive", "Add NVDA")

---

## Manual Mode

### Layout

Same 60/40 split. Left panel is the form, right panel is the shared `StrategyPreview`.

### Left Panel — Accordion Form

Uses existing `AccordionSection` component with these sections:

1. **Basics** (expanded) — Name, Description, Action (BUY/SELL), Timeframe, Symbols
2. **Entry Conditions** (expanded) — Condition groups with AND/OR visual joiners, "Add Group" button
3. **Exit Conditions** (expanded) — Same condition group UI for exits
4. **Risk Controls** (collapsed) — Stop Loss %, Take Profit %, Position Size %, Trailing Stop, Max Trades/Day
5. **Execution** (collapsed) — Order Type, Commission %, Slippage %, Backtest Period

### Improvements over current

- Side-by-side entry/exit visibility (both in left panel, preview shows both)
- Real-time preview updates as user fills form
- Condition group labels: "Entry Branch A" instead of "Group A"
- Color-coded AND (green) / OR (yellow) joiners between conditions

---

## Shared Components

### StrategyPreview (right panel)

Shared across all 3 modes. Reads from `useBuilderStore`. Contains:

1. **Header card**: Strategy name, action badge, timeframe, symbol pills
2. **Entry conditions card** (blue border): Visual condition list with AND/OR logic
3. **Exit conditions card** (red border): Same format
4. **Risk controls card** (amber border): 2x2 grid of SL/TP/Position/Trailing
5. **DiagnosticPanel**: Health score ring + issues (fetched from `POST /api/strategies/diagnose`, debounced 500ms)
6. **ExplainerPanel**: AI analysis summary (fetched from `POST /api/explain/strategy`)
7. **Action buttons**: "Deploy Bot" (primary), "Save Draft", "Edit in Manual" / "Edit with AI"

### Mode Tabs

Segmented control at top of left panel: `[AI-Assisted]  [Manual]  [From Template]`

- AI-Assisted is highlighted by default
- Switching modes preserves builder state (strategy carries over)
- Uses existing `.app-segmented` / `.app-segment` CSS classes

---

## Validation

Validation logic (currently in `StrategyBuilder.tsx` lines 878-893) moves to a utility function `validateStrategy(state: BuilderState)` in `frontend/src/lib/strategy-validation.ts`. Returns `{ canSave: boolean, issues: string[] }`. Called by both StrategyPreview (to disable Deploy/Save buttons) and DiagnosticPanel.

---

## Data Flow

```
User input (chat or form)
    ↓
useBuilderStore (single source of truth)
    ↓
StrategyPreview (reactive render)
    ↓
Deploy Bot:
  1. POST /api/strategies/create  →  strategy saved
  2. POST /api/ai/chat (createBot tool)  →  bot created & running

Save Draft:
  POST /api/strategies/create  →  strategy saved (no bot)
```

For AI mode specifically:
```
User message → POST /api/ai/chat (mode: "strategy")
    ↓
Cerberus LLM response (markdown + JSON in ```json block)
    ↓
parseStrategySpec() extracts JSON
    ↓
specToBuilderFields() converts to flat fields
    ↓
useBuilderStore.loadFromSpec() updates store → preview re-renders
```

---

## Error Handling

- **Chat failures**: Toast notification + retry button on the message
- **JSON parse failures**: Fallback to showing Cerberus's text response in chat, toast: "Strategy couldn't be parsed — try rephrasing"
- **Deploy failures**: Error message in preview panel with details
- **Template load failures**: Card shows error state, retry button
- **Validation failures**: Deploy/Save buttons disabled, issues shown in DiagnosticPanel

---

## Testing Strategy

- **Unit tests**: `useBuilderStore` — verify state transitions, `loadFromSpec`, draft persistence
- **Unit tests**: `validateStrategy()` — verify validation rules
- **Component tests**: StrategyPreview renders correctly from store state
- **Integration test**: AI chat → parse → preview → deploy flow
- **Existing tests**: All current strategy backend tests remain unchanged
