import { create } from 'zustand';
import { apiFetch } from '@/lib/api/client';
import type { Account, Position, AssetMode, Quote, Trade } from '@/types/trading';

interface TradeState {
  // State
  symbol: string;
  assetMode: AssetMode;
  quote: Quote | null;
  account: Account | null;
  positions: Position[];
  trades: Trade[];
  loading: boolean;
  quoteLoading: boolean;
  error: boolean;
  highlightedTradeId: string | null;
  showAllExecutions: boolean;

  // Actions
  setSymbol: (symbol: string) => void;
  setAssetMode: (mode: AssetMode) => void;
  setHighlightedTradeId: (id: string | null) => void;
  setShowAllExecutions: (show: boolean) => void;
  fetchQuote: (symbol?: string) => Promise<void>;
  fetchAll: (mode: string) => Promise<void>;
}

export const useTradeStore = create<TradeState>()((set, get) => ({
  // Initial state
  symbol: 'SPY',
  assetMode: 'stocks',
  quote: null,
  account: null,
  positions: [],
  trades: [],
  loading: true,
  quoteLoading: false,
  error: false,
  highlightedTradeId: null,
  showAllExecutions: true,

  setSymbol: (symbol: string) => {
    const upper = symbol.trim().toUpperCase();
    if (!upper || upper === get().symbol) return;
    set({ symbol: upper, highlightedTradeId: null });
    get().fetchQuote(upper);
  },

  setAssetMode: (mode: AssetMode) => set({ assetMode: mode }),

  setHighlightedTradeId: (id: string | null) => set({ highlightedTradeId: id }),

  setShowAllExecutions: (show: boolean) => set({ showAllExecutions: show }),

  fetchQuote: async (symbol?: string) => {
    const sym = symbol || get().symbol;
    if (!sym) return;
    set({ quoteLoading: true });
    try {
      const quote = await apiFetch<Quote>(`/api/trading/quote?symbol=${encodeURIComponent(sym)}`);
      set({ quote, quoteLoading: false });
    } catch {
      set({ quoteLoading: false });
    }
  },

  fetchAll: async (mode: string) => {
    set({ loading: true });
    try {
      const q = `?mode=${mode}`;
      const [accRes, posRes, tradeRes] = await Promise.allSettled([
        apiFetch<Account>(`/api/trading/account${q}`),
        apiFetch<{ positions: Position[] }>(`/api/trading/positions${q}`),
        apiFetch<{ trades: Trade[] } | Trade[]>(`/api/trading/trade-log?limit=100&mode=${mode}`),
      ]);

      let hasData = false;

      if (accRes.status === 'fulfilled') {
        set({ account: accRes.value });
        hasData = true;
      }

      if (posRes.status === 'fulfilled') {
        const data = posRes.value;
        set({ positions: data.positions || [] });
        hasData = true;
      }

      if (tradeRes.status === 'fulfilled') {
        const data = tradeRes.value;
        const trades = Array.isArray(data) ? data : (data as { trades: Trade[] }).trades || [];
        set({ trades });
        hasData = true;
      }

      // Also fetch quote for current symbol
      const sym = get().symbol;
      if (sym) {
        get().fetchQuote(sym);
      }

      set({ error: !hasData, loading: false });
    } catch {
      set({ error: true, loading: false });
    }
  },
}));
