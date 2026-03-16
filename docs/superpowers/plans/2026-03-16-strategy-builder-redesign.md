# Strategy Builder Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 1,500-line strategy builder monolith with a 60/40 split-panel UI where AI chat is the default mode, backed by a shared Zustand store.

**Architecture:** Break `StrategyBuilder.tsx` into 5 focused components (StrategyBuilderPage, AIChat, StrategyPreview, ManualBuilder, TemplateGallery) sharing state through a new `useBuilderStore` Zustand store. Move homepage to Dashboard. Add backend template seeding + endpoint.

**Tech Stack:** Next.js 14, React 18, Zustand, Tailwind CSS (custom `.app-*` design system), Radix UI, react-markdown, FastAPI (backend)

**Spec:** `docs/superpowers/specs/2026-03-16-strategy-builder-redesign-design.md`

---

## File Structure

### New Files (Frontend)

| File | Responsibility |
|------|---------------|
| `frontend/src/stores/builder-store.ts` | Zustand store: all builder state, actions (setField, loadFromSpec, loadFromStrategy, reset), localStorage persistence |
| `frontend/src/lib/strategy-validation.ts` | `validateStrategy(state)` → `{ canSave, issues[] }` |
| `frontend/src/app/strategy-builder/page.tsx` | Route `/strategy-builder` — renders `<StrategyBuilderPage />` |
| `frontend/src/app/strategy-builder/edit/[id]/page.tsx` | Route `/strategy-builder/edit/[id]` — fetches strategy, passes to builder |
| `frontend/src/components/strategy-builder/StrategyBuilderPage.tsx` | Layout shell: mode tabs + 60/40 split + renders left panel by mode + StrategyPreview |
| `frontend/src/components/strategy-builder/AIChat.tsx` | AI mode left panel: message list, input, sendChatMessage, JSON extraction, store updates |
| `frontend/src/components/strategy-builder/StrategyPreview.tsx` | Right panel: strategy cards (header, entry, exit, risk), DiagnosticPanel, ExplainerPanel, action buttons |
| `frontend/src/components/strategy-builder/ManualBuilder.tsx` | Manual mode left panel: accordion sections, condition group CRUD |
| `frontend/src/components/strategy-builder/TemplateGallery.tsx` | Template mode left panel: card grid, filters, "Use Template" |
| `scripts/seed_templates.py` | Idempotent seed script for 6 starter strategy templates |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/app/page.tsx` | Change from rendering `<StrategyBuilder />` to rendering Dashboard |
| `frontend/src/app/edit/[id]/page.tsx` | Redirect to `/strategy-builder/edit/[id]` |
| `db/models.py` | Add `is_system` column to `StrategyTemplate` |
| `api/routes/strategies.py` | Add `GET /api/strategies/templates` endpoint |
| `api/main.py` | Call `seed_templates()` after DB init |

### Deleted Files

| File | Reason |
|------|--------|
| `frontend/src/components/strategy-builder/AIStrategyGeneratorDialog.tsx` | Replaced by AIChat.tsx |

### Unchanged Files (reused as-is)

- `frontend/src/components/strategy-builder/ConditionGroup.tsx`
- `frontend/src/components/strategy-builder/ConditionRow.tsx`
- `frontend/src/components/strategy-builder/DiagnosticPanel.tsx`
- `frontend/src/components/strategy-builder/ExplainerPanel.tsx`
- `frontend/src/components/strategy-builder/AccordionSection.tsx`
- `frontend/src/stores/strategy-builder-store.ts` (kept for Cerberus widget handoff)
- `frontend/src/lib/strategy-spec.ts`
- `frontend/src/lib/cerberus-strategy.ts`
- `frontend/src/lib/cerberus-api.ts`
- `frontend/src/types/strategy.ts`

---

## Chunk 1: Foundation — Store, Validation, Routes

### Task 1: Create `useBuilderStore` Zustand store

**Files:**
- Create: `frontend/src/stores/builder-store.ts`

- [ ] **Step 1: Create the store with full state shape and actions**

The store replaces all 30+ `useState` calls from the monolith. It uses Zustand `persist` middleware for draft auto-save to localStorage.

Key implementation notes:
- Import `ConditionGroup`, `StrategyAiContext`, `DiagnosticReport`, `StrategyExplanation` from `@/types/strategy`
- Import `StrategySpec` from `@/lib/strategy-spec`
- `loadFromSpec(spec)` calls `specToBuilderFields(spec)` from `@/lib/strategy-spec` and spreads the result into state
- `loadFromStrategy(record)` maps a `StrategyRecord` (API response) to store fields — reference current `StrategyBuilder.tsx` lines ~200-260 for the mapping
- `setField(field, value)` is a generic setter using Zustand's `set((s) => ({ ...s, [field]: value }))`
- `reset()` clears to defaults and removes the localStorage draft
- Persist middleware config: `name: "strategy_builder_draft"`, `partialize` to exclude `diagnostics`, `explanation`, `indicatorPreviews` (computed/transient)

Default values — match current `StrategyBuilder.tsx` defaults:
- `name: ""`, `description: ""`, `action: "BUY"`, `timeframe: "1D"`, `strategyType: "manual"`
- `symbols: []`, `conditionGroups: [{ id: "A", conditions: [], joiner: "AND" }]`, `exitConditionGroups: []`
- `stopLoss: 2`, `takeProfit: 5`, `positionSize: 5`
- `trailingStopEnabled: false`, `trailingStop: 1`, `exitAfterBarsEnabled: false`, `exitAfterBars: 10`
- `exitLogic: "stop_target"`, `cooldownBars: 0`, `maxTradesPerDay: 10`, `maxExposurePct: 100`, `maxLossPct: 10`
- `orderType: "market"`, `backtestPeriod: "6M"`, `commissionPct: 0.1`, `slippagePct: 0.05`

- [ ] **Step 2: Verify store works**

Run: `npx tsc --noEmit` from `frontend/`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/builder-store.ts
git commit -m "feat: add useBuilderStore Zustand store for strategy builder state"
```

### Task 2: Create `validateStrategy` utility

**Files:**
- Create: `frontend/src/lib/strategy-validation.ts`

- [ ] **Step 1: Extract validation logic from StrategyBuilder.tsx**

Reference `StrategyBuilder.tsx` lines ~878-893 for current validation rules. The function signature:

```typescript
export function validateStrategy(state: BuilderState): { canSave: boolean; issues: string[] }
```

Rules to implement:
- Name is required (non-empty after trim)
- At least one symbol
- At least one entry condition with indicator + operator + value
- `stopLoss > 0` and `takeProfit > 0`
- `positionSize > 0` and `positionSize <= 100`

Returns `{ canSave: true, issues: [] }` if all pass, or `{ canSave: false, issues: ["Name is required", ...] }`.

- [ ] **Step 2: Verify no type errors**

Run: `npx tsc --noEmit` from `frontend/`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/strategy-validation.ts
git commit -m "feat: add validateStrategy utility extracted from monolith"
```

### Task 3: Set up new routes

**Files:**
- Create: `frontend/src/app/strategy-builder/page.tsx`
- Create: `frontend/src/app/strategy-builder/edit/[id]/page.tsx`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/edit/[id]/page.tsx`

- [ ] **Step 1: Create `/strategy-builder` page**

Simple page that renders `<StrategyBuilderPage />` (component created in Task 5). For now, render a placeholder `<div>Strategy Builder - Coming Soon</div>` since the component doesn't exist yet.

- [ ] **Step 2: Create `/strategy-builder/edit/[id]` page**

Copy logic from existing `frontend/src/app/edit/[id]/page.tsx` — fetches `GET /api/strategies/:id` and passes `initialStrategy` prop. Renders `<StrategyBuilderPage mode="edit" initialStrategy={data} />`. For now, placeholder.

- [ ] **Step 3: Update `/` to render Dashboard**

Change `frontend/src/app/page.tsx` to redirect to `/portfolio` (the existing dashboard page) or render the dashboard component directly. Check what component currently lives at `/portfolio` or `/dashboard` route and reuse it.

- [ ] **Step 4: Update `/edit/[id]` to redirect**

Change `frontend/src/app/edit/[id]/page.tsx` to `redirect("/strategy-builder/edit/" + params.id)` using Next.js `redirect()`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/strategy-builder/ frontend/src/app/page.tsx frontend/src/app/edit/
git commit -m "feat: add /strategy-builder routes, move homepage to dashboard"
```

---

## Chunk 2: StrategyPreview + StrategyBuilderPage Shell

### Task 4: Build `StrategyPreview` component

**Files:**
- Create: `frontend/src/components/strategy-builder/StrategyPreview.tsx`

- [ ] **Step 1: Build the preview component**

Reads from `useBuilderStore`. Renders:
1. **Header card** — strategy `name` (or "Untitled Strategy"), `action` as badge (BUY=green, SELL=red), `timeframe`, `symbols` as pills
2. **Entry conditions card** — blue left border (`border-l-4 border-blue-500`). Maps `conditionGroups` → readable condition text with AND/OR joiners. Use color: AND = `text-emerald-500`, OR = `text-amber-500`
3. **Exit conditions card** — red left border. Same rendering for `exitConditionGroups`. Also shows `stopLoss`, `takeProfit` as fallback if no exit conditions defined.
4. **Risk controls card** — amber left border. 2x2 grid: Stop Loss %, Take Profit %, Position Size %, Trailing Stop (if enabled)
5. **DiagnosticPanel** — import from existing `./DiagnosticPanel`, pass `diagnostics` from store
6. **ExplainerPanel** — import from existing `./ExplainerPanel`, pass `explanation` from store
7. **Action buttons** — "Deploy Bot" (primary, `.app-button-primary`), "Save Draft" (secondary), mode-switch button ("Edit in Manual" when in AI mode, "Edit with AI" when in Manual)

Call `validateStrategy()` from `@/lib/strategy-validation` to disable Deploy/Save when `canSave` is false.

Use existing CSS classes: `.app-panel`, `.app-card`, `.app-label`, `.app-pill`, `.app-button-primary`, `.app-button-secondary`.

- [ ] **Step 2: Verify no type errors**

Run: `npx tsc --noEmit` from `frontend/`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/strategy-builder/StrategyPreview.tsx
git commit -m "feat: add StrategyPreview component — live strategy preview panel"
```

### Task 5: Build `StrategyBuilderPage` shell

**Files:**
- Create: `frontend/src/components/strategy-builder/StrategyBuilderPage.tsx`
- Modify: `frontend/src/app/strategy-builder/page.tsx` (replace placeholder)

- [ ] **Step 1: Build the page shell**

Props: `{ mode?: "create" | "edit"; initialStrategy?: StrategyRecord }`

Renders:
1. Mode tabs at top using `.app-segmented` / `.app-segment` / `.app-toggle-active` classes. Three tabs: "AI-Assisted" (default), "Manual", "From Template". State: `activeMode` useState.
2. 60/40 split layout: `grid grid-cols-1 xl:grid-cols-[3fr_2fr] gap-0 h-[calc(100vh-60px)]`
3. Left panel: conditionally render by `activeMode`:
   - `"ai"` → `<AIChat />` (placeholder div for now)
   - `"manual"` → `<ManualBuilder />` (placeholder div for now)
   - `"template"` → `<TemplateGallery />` (placeholder div for now)
4. Right panel: `<StrategyPreview onModeSwitch={setActiveMode} />`
5. On mount: if `initialStrategy` provided, call `useBuilderStore.loadFromStrategy(initialStrategy)`. Also consume `pendingSpec` from `useStrategyBuilderStore` if present.

- [ ] **Step 2: Wire up the route page**

Update `frontend/src/app/strategy-builder/page.tsx` to import and render `<StrategyBuilderPage />`.

- [ ] **Step 3: Verify the page renders**

Run: `npm run dev` in frontend, navigate to `http://localhost:3000/strategy-builder`
Expected: Mode tabs visible, right panel shows StrategyPreview (empty state), left panel shows placeholder

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/strategy-builder/StrategyBuilderPage.tsx frontend/src/app/strategy-builder/page.tsx
git commit -m "feat: add StrategyBuilderPage shell with 60/40 layout and mode tabs"
```

---

## Chunk 3: AI Chat Panel

### Task 6: Build `AIChat` component

**Files:**
- Create: `frontend/src/components/strategy-builder/AIChat.tsx`

- [ ] **Step 1: Build the chat component**

State:
- `messages: Array<{ id: string; role: "user" | "assistant"; content: string; createdAt: string }>` — local state (chat history is UI-only, not persisted in builder store)
- `input: string` — current input text
- `isLoading: boolean` — waiting for Cerberus response
- `activeThreadId: string | null` — Cerberus thread ID
- `error: string | null`

Layout (full height of left panel, flex column):
1. **Messages area** (`flex-1 overflow-y-auto p-4`): Maps `messages` → message cards
   - User messages: right-aligned, `bg-slate-800 rounded-xl p-3`
   - Assistant messages: left-aligned, `bg-slate-900 border border-blue-900/50 rounded-xl p-3`, rendered with `<ReactMarkdown>` using `remark-gfm` and `rehype-highlight`
   - Auto-scroll to bottom on new message (`useRef` + `scrollIntoView`)
2. **Input area** (`border-t border-slate-700 p-3`): Text input + send button
   - `<textarea>` with `.app-input` styling, auto-resize, submit on Enter (not Shift+Enter)
   - Send button: `.app-button-primary` with arrow icon

On send:
1. Add user message to `messages`
2. Set `isLoading = true`
3. Call `sendChatMessage({ threadId: activeThreadId, mode: "strategy", message: input, pageContext: {} })` from `@/lib/cerberus-api`
4. On response: add assistant message, try `parseStrategySpec(markdown)`:
   - If `parsed.ok`: call `useBuilderStore.getState().loadFromSpec(parsed.spec)`, set `strategyType` to `"ai_generated"`
   - If `!parsed.ok`: just show the text response (no store update)
5. Set `isLoading = false`, clear input

Import `sendChatMessage` from `@/lib/cerberus-api`, `parseStrategySpec` from `@/lib/strategy-spec`, `useBuilderStore` from `@/stores/builder-store`.

- [ ] **Step 2: Verify no type errors**

Run: `npx tsc --noEmit` from `frontend/`

- [ ] **Step 3: Wire into StrategyBuilderPage**

In `StrategyBuilderPage.tsx`, replace the AI placeholder `<div>` with `<AIChat />`.

- [ ] **Step 4: Test the full flow**

Run: `npm run dev`, navigate to `/strategy-builder`
1. Type a strategy idea in the chat
2. Cerberus should respond
3. If JSON is returned, the right preview panel should update with the strategy

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/strategy-builder/AIChat.tsx frontend/src/components/strategy-builder/StrategyBuilderPage.tsx
git commit -m "feat: add AIChat component — conversational strategy builder with Cerberus"
```

---

## Chunk 4: Manual Builder + Template Gallery

### Task 7: Build `ManualBuilder` component

**Files:**
- Create: `frontend/src/components/strategy-builder/ManualBuilder.tsx`

- [ ] **Step 1: Build the manual form**

Extract the form sections from current `StrategyBuilder.tsx` (~lines 1050-1400) into this component. All state reads/writes go through `useBuilderStore` instead of local `useState`.

Layout: scrollable column using `AccordionSection` for each group:

1. **Basics** (default open, accent="blue"):
   - Name: `<input className="app-input">` → `store.setField("name", e.target.value)`
   - Description: `<textarea className="app-input">`
   - Action: segmented control BUY/SELL
   - Timeframe: `<select className="app-select">` with options 1m, 5m, 15m, 1H, 4H, 1D, 1W
   - Symbols: tag input (type + Enter to add, X to remove)

2. **Entry Conditions** (default open, accent="green"):
   - Map `store.conditionGroups` → `<ConditionGroup>` components
   - "Add Entry Branch" button
   - Label groups as "Entry Branch A", "Entry Branch B", etc.

3. **Exit Conditions** (default open, accent="red"):
   - Map `store.exitConditionGroups` → `<ConditionGroup>` components
   - "Add Exit Branch" button

4. **Risk Controls** (default collapsed, accent="orange"):
   - Stop Loss %, Take Profit %, Position Size %, Trailing Stop toggle + value, Max Trades/Day

5. **Execution** (default collapsed, accent="slate"):
   - Order Type select, Backtest Period, Commission %, Slippage %

All condition group CRUD operations (add group, remove group, add condition, remove condition, update condition) work through `store.setField("conditionGroups", updatedGroups)`.

- [ ] **Step 2: Wire into StrategyBuilderPage**

Replace the Manual placeholder `<div>` with `<ManualBuilder />`.

- [ ] **Step 3: Test manual mode**

Navigate to `/strategy-builder`, click "Manual" tab. Fill in a strategy. Verify preview updates live.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/strategy-builder/ManualBuilder.tsx frontend/src/components/strategy-builder/StrategyBuilderPage.tsx
git commit -m "feat: add ManualBuilder component — accordion form with live preview"
```

### Task 8: Build `TemplateGallery` component

**Files:**
- Create: `frontend/src/components/strategy-builder/TemplateGallery.tsx`

- [ ] **Step 1: Build the template gallery**

State:
- `templates: StrategyRecord[]` — loaded from API
- `typeFilter: string` — "all" | "momentum" | "mean_reversion" | "breakout" | "trend"
- `timeframeFilter: string` — "all" | "intraday" | "swing" | "position"
- `search: string`
- `isLoading: boolean`

On mount: fetch `GET /api/strategies/templates` (created in Task 10). Filter client-side by `typeFilter`, `timeframeFilter`, `search`.

Layout:
1. **Filter bar** — three controls in a row: Type dropdown, Timeframe dropdown, Search input
2. **Card grid** — `grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3`

Each card (`.app-card` with hover effect):
- Strategy name (bold)
- Type badge: colored pill (green=momentum, purple=mean_reversion, blue=breakout, orange=trend)
- Description (2 lines, `line-clamp-2`)
- Indicator pills at bottom (RSI, MACD, etc. — extracted from conditions)
- "Use Template" button (`.app-button-secondary`)

On "Use Template" click:
1. Call `useBuilderStore.getState().loadFromStrategy(template)`
2. Call `onModeSwitch("ai")` prop to switch to AI mode (user can refine with Cerberus)

- [ ] **Step 2: Wire into StrategyBuilderPage**

Replace the Template placeholder `<div>` with `<TemplateGallery onModeSwitch={setActiveMode} />`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/strategy-builder/TemplateGallery.tsx frontend/src/components/strategy-builder/StrategyBuilderPage.tsx
git commit -m "feat: add TemplateGallery component — visual template card grid"
```

---

## Chunk 5: Backend — Templates + Cleanup

### Task 9: Add `is_system` column to StrategyTemplate

**Files:**
- Modify: `db/models.py`

- [ ] **Step 1: Add the column**

Find the `StrategyTemplate` class in `db/models.py`. Add:
```python
is_system = Column(Boolean, default=False, server_default=text("false"))
```

This column distinguishes system-seeded templates from user-created ones.

- [ ] **Step 2: Verify the app starts**

Restart uvicorn — the `create_all` in `init_db` will add the column.

- [ ] **Step 3: Commit**

```bash
git add db/models.py
git commit -m "feat: add is_system column to StrategyTemplate for system templates"
```

### Task 10: Add template seed script + API endpoint

**Files:**
- Create: `scripts/seed_templates.py`
- Modify: `api/routes/strategies.py`
- Modify: `api/main.py`

- [ ] **Step 1: Create seed script**

Create `scripts/seed_templates.py` with an async `seed_templates()` function. It should be idempotent — check if templates with these names exist before inserting. Create 6 `StrategyTemplate` records with `is_system=True`:

1. RSI Oversold Bounce (momentum, 1D, RSI < 30 AND volume > SMA(20))
2. Bollinger Squeeze (mean_reversion, 1D, price < lower BB AND ATR expanding)
3. MACD Crossover (momentum, 1D, MACD crosses above signal AND price > EMA(200))
4. Volume Breakout (breakout, 1D, volume > 2x SMA(20) AND price breaks SMA(50))
5. Golden Cross (trend, 1D, SMA(50) crosses above SMA(200))
6. Stochastic Reversal (mean_reversion, 1D, Stoch K < 20 AND RSI < 35)

Each template's `config_json` should match the `StrategySpec` shape so `specToBuilderFields()` can parse it. Include `entryConditions`, `exitConditions`, `stopLossPct`, `takeProfitPct`, `positionPct`, `symbols`, `action`, `timeframe`, `name`, `description`, `strategyType: "system"`, `featureSignals`, `overview`.

- [ ] **Step 2: Add GET /api/strategies/templates endpoint**

In `api/routes/strategies.py`, add:
```python
@router.get("/templates")
async def list_templates(
    type: str = Query(None),
    timeframe: str = Query(None),
):
    """List system strategy templates."""
    async with get_session() as session:
        stmt = select(StrategyTemplate).where(StrategyTemplate.is_system == True)
        if type:
            stmt = stmt.where(StrategyTemplate.strategy_type == type)
        result = await session.execute(stmt)
        templates = result.scalars().all()
    return [_template_to_dict(t) for t in templates]
```

Add a `_template_to_dict()` helper that serializes the template to JSON (id, name, description, config_json, strategy_type, etc.).

- [ ] **Step 3: Call seed in api/main.py**

After `await _init_db_with_retry()` completes successfully, call:
```python
from scripts.seed_templates import seed_templates
await seed_templates()
```

- [ ] **Step 4: Test**

Restart backend. Hit `GET /api/strategies/templates` — should return 6 templates.

- [ ] **Step 5: Commit**

```bash
git add scripts/seed_templates.py api/routes/strategies.py api/main.py db/models.py
git commit -m "feat: add system template seeding and GET /api/strategies/templates endpoint"
```

### Task 11: Delete old monolith + wire deploy flow

**Files:**
- Delete: `frontend/src/components/strategy-builder/AIStrategyGeneratorDialog.tsx`
- Modify: `frontend/src/components/strategy-builder/StrategyPreview.tsx` (deploy logic)

- [ ] **Step 1: Delete AIStrategyGeneratorDialog.tsx**

Remove the file. Search for imports of `AIStrategyGeneratorDialog` in the codebase and remove them (should only be in the old `StrategyBuilder.tsx` which is no longer the entry point).

- [ ] **Step 2: Implement Deploy Bot flow in StrategyPreview**

In the "Deploy Bot" button handler:
1. Build the strategy payload from `useBuilderStore` state (same shape as current `saveStrategy()` in the monolith)
2. `POST /api/strategies/create` with auth header → get `strategy_id`
3. `POST /api/ai/chat` with message: `"Deploy the strategy '${name}' as a trading bot with the following config: ${JSON.stringify(config)}"` and `mode: "strategy"` — Cerberus will call `createBot` tool
4. Show success toast on completion, error toast on failure

"Save Draft" button: step 1+2 only (no bot deployment).

- [ ] **Step 3: Commit**

```bash
git rm frontend/src/components/strategy-builder/AIStrategyGeneratorDialog.tsx
git add frontend/src/components/strategy-builder/StrategyPreview.tsx
git commit -m "feat: implement deploy/save flow, delete AIStrategyGeneratorDialog"
```

### Task 12: Final integration + push to both environments

**Files:**
- Modify: `frontend/src/components/strategy-builder/StrategyBuilderPage.tsx` (final cleanup)

- [ ] **Step 1: Verify full flow end-to-end**

1. Navigate to `/strategy-builder`
2. AI mode: type a strategy idea → Cerberus responds → preview updates → Deploy Bot works
3. Manual mode: fill in form → preview updates → Save Draft works
4. Template mode: cards load → click "Use Template" → switches to AI with strategy pre-filled
5. `/` redirects to dashboard
6. `/strategies` page still works

- [ ] **Step 2: Run existing tests**

```bash
cd frontend && npx tsc --noEmit
python3 -m pytest tests/test_p0_bot_safety_and_access.py -x -q
```

- [ ] **Step 3: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: complete strategy builder redesign — AI chat, templates, manual mode"
```

- [ ] **Step 4: Push to both environments**

```bash
git push origin main
```

Vercel auto-deploys from push. Verify both:
- `http://localhost:3000/strategy-builder` (local)
- `https://adaptive-trading-ecosystem.vercel.app/strategy-builder` (production)
