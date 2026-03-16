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

- Backend API changes (all existing endpoints are reused)
- Changing the strategy data model or types
- Mobile-first design (desktop is primary, responsive is nice-to-have)
- Backtest integration changes

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
| `AIChat.tsx` | Left panel in AI mode: message history, input, Cerberus integration, follow-up suggestions | ~400 lines |
| `StrategyPreview.tsx` | Right panel (shared across all modes): live preview of strategy, entry/exit/risk cards, Deploy/Edit buttons | ~350 lines |
| `ManualBuilder.tsx` | Left panel in Manual mode: accordion form sections, condition group CRUD | ~400 lines |
| `TemplateGallery.tsx` | Full-width template card grid with filters | ~200 lines |

Existing components reused without changes:
- `ConditionGroup.tsx` (110 lines)
- `ConditionRow.tsx` (260 lines)
- `DiagnosticPanel.tsx` (165 lines)
- `ExplainerPanel.tsx` (122 lines)
- `AccordionSection.tsx` (135 lines)

### State Management

- **Builder state**: Lifted into a Zustand store (`useBuilderStore`) replacing the 30+ `useState` calls in the current monolith. This allows AIChat, ManualBuilder, and StrategyPreview to share state without prop drilling.
- **Store shape**: `{ name, description, action, timeframe, symbols, conditionGroups, exitConditions, stopLoss, takeProfit, positionSize, riskControls, executionSettings, strategyType, sourcePrompt, aiContext, diagnostics }`
- **Draft persistence**: Store subscribes to changes and persists to `localStorage` (same behavior as current, just moved to store middleware).
- **Cross-component handoff** (Cerberus panel → builder): Existing `useStrategyBuilderStore` with `pendingSpec` is kept for the floating Cerberus widget. The new AIChat component writes directly to the builder store.

---

## AI-Assisted Mode (Default)

### Layout

Fixed 60/40 horizontal split. No layout shifts.

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
│  ┌─ Suggestions ────────────┐   │   ┌─ Risk ─────────┐ │
│  │ 💡 Add volume filter     │   │   │ SL: 3% TP: 8%  │ │
│  │ 💡 Tighten stop loss     │   │   └────────────────┘ │
│  └──────────────────────────┘   │                      │
│                                 │   [Deploy Bot] [Edit]│
│  ┌──────────────────────┐ [↑]   │                      │
│  │ Describe strategy... │       │                      │
│  └──────────────────────┘       │                      │
└─────────────────────────────────┴──────────────────────┘
```

### Chat Flow

1. User types a strategy idea in natural language
2. Message sent to `POST /api/ai/chat` with `mode: "strategy"`
3. Cerberus responds with clarifying questions OR a full strategy JSON
4. If JSON is returned, `parseStrategySpec()` extracts it → builder store updates → preview reflects changes
5. User can iterate: "Change stop loss to 2%" → Cerberus returns updated JSON → preview updates
6. Follow-up suggestion chips appear after each Cerberus response (contextual: "Add volume filter?", "Backtest this?", "Tighten exits?")

### Chat Component Details

- Messages rendered as cards: user messages right-aligned (dark), Cerberus left-aligned (blue border)
- Cerberus messages support markdown rendering (already have `react-markdown` + `remark-gfm`)
- Sticky input at bottom with send button
- Thread ID maintained across messages (existing `activeThreadId` pattern)
- Loading state: typing indicator while Cerberus responds

### Preview Component Details

- Reads from builder Zustand store (reactive)
- Sections with color-coded borders:
  - Strategy header (name, action, timeframe, symbols) — neutral
  - Entry conditions — blue (`#3b82f6`)
  - Exit conditions — red (`#ef4444`)
  - Risk controls — orange/amber (`#f59e0b`)
- Each condition rendered as readable rule (reuse `ConditionRow`'s readable format)
- "Deploy Bot" button: calls `POST /api/strategies/create` → then triggers `createBot` tool call
- "Edit in Manual" button: switches mode tab to Manual with state preserved
- Inline editing: click any value to modify directly in preview

---

## From Template Mode

### Layout

Full-width grid replacing the left panel. Preview panel stays on right showing the selected template.

### Template Cards (3 per row)

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

Templates are stored as `StrategyTemplate` records with `is_system=True`. Seeded via migration or startup script.

### "Use Template" Flow

Click "Use Template" → strategy loaded into builder store → mode switches to AI with template pre-filled in preview → user can chat with Cerberus to refine ("Make this more aggressive", "Add NVDA to the symbols")

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

Shared across all 3 modes. Reads from Zustand store. Contains:

1. **Header card**: Strategy name, action badge, timeframe, symbol pills
2. **Entry conditions card** (blue border): Visual condition list with AND/OR logic
3. **Exit conditions card** (red border): Same format
4. **Risk controls card** (amber border): 2x2 grid of SL/TP/Position/Trailing
5. **Diagnostics badge**: Health score ring (reuse DiagnosticPanel's ScoreRing)
6. **Action buttons**: "Deploy Bot" (primary), "Save Draft", "Edit in Manual" / "Edit with AI"

### Mode Tabs

Segmented control at top of left panel: `[AI-Assisted]  [Manual]  [From Template]`

- AI-Assisted is highlighted by default
- Switching modes preserves builder state (strategy carries over)
- Uses existing `.app-segmented` / `.app-segment` CSS classes

---

## Data Flow

```
User input (chat or form)
    ↓
Builder Zustand Store (single source of truth)
    ↓
StrategyPreview (reactive render)
    ↓
Deploy Bot → POST /api/strategies/create → createBot tool
```

For AI mode specifically:
```
User message → POST /api/ai/chat (mode: "strategy")
    ↓
Cerberus LLM response (markdown + JSON)
    ↓
parseStrategySpec() extracts JSON
    ↓
specToBuilderFields() converts to store shape
    ↓
Builder store updated → preview re-renders
```

---

## Error Handling

- **Chat failures**: Toast notification + retry button on the message
- **JSON parse failures**: Fallback to showing Cerberus's text response in chat, toast: "Strategy couldn't be parsed — try rephrasing"
- **Deploy failures**: Error message in preview panel with details
- **Template load failures**: Card shows error state, retry button

---

## Testing Strategy

- **Unit tests**: Builder store (Zustand) — verify state transitions, draft persistence
- **Component tests**: StrategyPreview renders correctly from store state
- **Integration test**: AI chat → parse → preview → deploy flow
- **Existing tests**: All current strategy tests remain (backend unchanged)
