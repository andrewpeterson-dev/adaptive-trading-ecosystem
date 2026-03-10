import { create } from 'zustand';
import { apiFetch } from '@/lib/api/client';
import type { Account, Position, AssetMode, Quote } from '@/types/trading';

interface TradeState {
  // State
  symbol: string;
  assetMode: AssetMode;
  quote: Quote | null;
  account: Account | null;
  positions: Position[];
  trades: any[];
  loading: boolean;
  quoteLoading: boolean;
  error: boolean;

  // Actions
  setSymbol: (symbol: string) => void;
  setAssetMode: (mode: AssetMode) => void;
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

  setSymbol: (symbol: string) => {
    set({ symbol });
    get().fetchQuote(symbol);
  },

  setAssetMode: (mode: AssetMode) => set({ assetMode: mode }),

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
        apiFetch<any>(`/api/trading/trade-log?limit=100&mode=${mode}`),
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
        set({ trades: data.trades || data || [] });
        hasData = true;
      }

      set({ error: !hasData, loading: false });
    } catch {
      set({ error: true, loading: false });
    }
  },
}));
