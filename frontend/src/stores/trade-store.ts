import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { apiFetch } from '@/lib/api/client';
import type {
  Account,
  AssetMode,
  NewsArticle,
  Order,
  Position,
  Quote,
  SymbolSnapshot,
  Trade,
  TradingConnectionStatus,
} from '@/types/trading';

const DEFAULT_WATCHLIST = ['SPY', 'QQQ', 'AAPL', 'NVDA', 'MSFT'];

interface TradeState {
  symbol: string;
  assetMode: AssetMode;
  quote: Quote | null;
  snapshot: SymbolSnapshot | null;
  news: NewsArticle[];
  status: TradingConnectionStatus | null;
  account: Account | null;
  positions: Position[];
  orders: Order[];
  trades: Trade[];
  watchlist: string[];
  loading: boolean;
  quoteLoading: boolean;
  symbolDetailsLoading: boolean;
  newsLoading: boolean;
  statusLoading: boolean;
  error: boolean;
  errorMessage: string | null;
  highlightedTradeId: string | null;
  showAllExecutions: boolean;
  leftDrawerOpen: boolean;
  rightDrawerOpen: boolean;

  setSymbol: (symbol: string) => void;
  setAssetMode: (mode: AssetMode) => void;
  setHighlightedTradeId: (id: string | null) => void;
  setShowAllExecutions: (show: boolean) => void;
  setLeftDrawerOpen: (open: boolean) => void;
  setRightDrawerOpen: (open: boolean) => void;
  toggleLeftDrawer: () => void;
  toggleRightDrawer: () => void;
  addToWatchlist: (symbol: string) => void;
  removeFromWatchlist: (symbol: string) => void;
  fetchQuote: (symbol?: string) => Promise<void>;
  fetchSymbolWorkspace: (symbol?: string) => Promise<void>;
  fetchAll: (mode: string) => Promise<void>;
}

export const useTradeStore = create<TradeState>()(
  persist(
    (set, get) => ({
      symbol: 'SPY',
      assetMode: 'stocks',
      quote: null,
      snapshot: null,
      news: [],
      status: null,
      account: null,
      positions: [],
      orders: [],
      trades: [],
      watchlist: DEFAULT_WATCHLIST,
      loading: true,
      quoteLoading: false,
      symbolDetailsLoading: false,
      newsLoading: false,
      statusLoading: false,
      error: false,
      errorMessage: null,
      highlightedTradeId: null,
      showAllExecutions: true,
      leftDrawerOpen: true,
      rightDrawerOpen: true,

      setSymbol: (symbol: string) => {
        const upper = symbol.trim().toUpperCase();
        if (!upper || upper === get().symbol) return;
        set({ symbol: upper, highlightedTradeId: null, errorMessage: null });
        void get().fetchSymbolWorkspace(upper);
      },

      setAssetMode: (mode: AssetMode) => set({ assetMode: mode }),

      setHighlightedTradeId: (id: string | null) => set({ highlightedTradeId: id }),

      setShowAllExecutions: (show: boolean) => set({ showAllExecutions: show }),

      setLeftDrawerOpen: (open: boolean) => set({ leftDrawerOpen: open }),
      setRightDrawerOpen: (open: boolean) => set({ rightDrawerOpen: open }),
      toggleLeftDrawer: () => set((state) => ({ leftDrawerOpen: !state.leftDrawerOpen })),
      toggleRightDrawer: () => set((state) => ({ rightDrawerOpen: !state.rightDrawerOpen })),

      addToWatchlist: (symbol: string) => {
        const upper = symbol.trim().toUpperCase();
        if (!upper) return;
        set((state) => ({
          watchlist: state.watchlist.includes(upper)
            ? state.watchlist
            : [upper, ...state.watchlist].slice(0, 24),
        }));
      },

      removeFromWatchlist: (symbol: string) => {
        const upper = symbol.trim().toUpperCase();
        set((state) => ({
          watchlist: state.watchlist.filter((item) => item !== upper),
        }));
      },

      fetchQuote: async (symbol?: string) => {
        const sym = symbol || get().symbol;
        if (!sym) return;
        set({ quoteLoading: true });
        try {
          const quote = await apiFetch<Quote>(`/api/trading/quote?symbol=${encodeURIComponent(sym)}`);
          set({ quote, quoteLoading: false });
        } catch (error) {
          set({
            quoteLoading: false,
            errorMessage: error instanceof Error ? error.message : null,
          });
        }
      },

      fetchSymbolWorkspace: async (symbol?: string) => {
        const sym = symbol || get().symbol;
        if (!sym) return;

        set({
          quoteLoading: true,
          symbolDetailsLoading: true,
          newsLoading: true,
          statusLoading: true,
        });

        const [quoteRes, snapshotRes, newsRes, statusRes] = await Promise.allSettled([
          apiFetch<Quote>(`/api/trading/quote?symbol=${encodeURIComponent(sym)}`),
          apiFetch<SymbolSnapshot>(`/api/trading/snapshot?symbol=${encodeURIComponent(sym)}`),
          apiFetch<{ articles: NewsArticle[] }>(
            `/api/trading/news?symbol=${encodeURIComponent(sym)}&limit=6`,
          ),
          apiFetch<TradingConnectionStatus>(
            `/api/trading/status?symbol=${encodeURIComponent(sym)}`,
          ),
        ]);

        const nextState: Partial<TradeState> = {
          quoteLoading: false,
          symbolDetailsLoading: false,
          newsLoading: false,
          statusLoading: false,
        };

        if (quoteRes.status === 'fulfilled') {
          nextState.quote = quoteRes.value;
        }

        if (snapshotRes.status === 'fulfilled') {
          nextState.snapshot = snapshotRes.value;
        } else if (quoteRes.status === 'fulfilled') {
          nextState.snapshot = {
            ...quoteRes.value,
            exchange: undefined,
            market_cap: null,
            pe_ratio: null,
            fifty_two_week_low: null,
            fifty_two_week_high: null,
            dividend_yield: null,
            avg_volume: null,
            market_state: null,
            currency: 'USD',
            source: null,
            sector: quoteRes.value.sector ?? null,
            industry: quoteRes.value.industry ?? null,
            description: quoteRes.value.company_summary ?? null,
          };
        }

        if (newsRes.status === 'fulfilled') {
          nextState.news = newsRes.value.articles || [];
        } else {
          nextState.news = [];
        }

        if (statusRes.status === 'fulfilled') {
          nextState.status = statusRes.value;
        }

        const firstFailure = [quoteRes, snapshotRes, newsRes, statusRes].find(
          (result) => result.status === 'rejected',
        );

        nextState.errorMessage =
          firstFailure && firstFailure.status === 'rejected'
            ? firstFailure.reason instanceof Error
              ? firstFailure.reason.message
              : 'Could not refresh symbol workspace'
            : null;

        set(nextState as Partial<TradeState>);
      },

      fetchAll: async (mode: string) => {
        set({ loading: true });
        try {
          const q = `?mode=${mode}`;
          const [accRes, posRes, orderRes, tradeRes] = await Promise.allSettled([
            apiFetch<Account>(`/api/trading/account${q}`),
            apiFetch<{ positions: Position[] }>(`/api/trading/positions${q}`),
            apiFetch<{ orders: Order[] }>(`/api/trading/orders${q}`),
            apiFetch<{ trades: Trade[] } | Trade[]>(`/api/trading/trade-log?limit=100&mode=${mode}`),
          ]);

          // Batch all state updates into a single set() call to avoid intermediate re-renders
          let hasData = false;
          const nextState: Partial<TradeState> = {};

          if (accRes.status === 'fulfilled') {
            nextState.account = accRes.value;
            hasData = true;
          }

          if (posRes.status === 'fulfilled') {
            nextState.positions = posRes.value.positions || [];
            hasData = true;
          }

          if (orderRes.status === 'fulfilled') {
            nextState.orders = orderRes.value.orders || [];
            hasData = true;
          } else {
            nextState.orders = [];
          }

          if (tradeRes.status === 'fulfilled') {
            const data = tradeRes.value;
            nextState.trades = Array.isArray(data) ? data : data.trades || [];
            hasData = true;
          }

          const accountError =
            accRes.status === 'rejected' && accRes.reason instanceof Error
              ? accRes.reason.message
              : null;

          nextState.error = !hasData;
          nextState.errorMessage = accountError;
          nextState.loading = false;

          set(nextState as Partial<TradeState>);

          // Fetch symbol workspace after main data is set
          await get().fetchSymbolWorkspace(get().symbol);
        } catch (error) {
          set({
            error: true,
            loading: false,
            errorMessage: error instanceof Error ? error.message : 'Failed to load trading workspace',
          });
        }
      },
    }),
    {
      name: 'trade-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        symbol: state.symbol,
        assetMode: state.assetMode,
        watchlist: state.watchlist,
        showAllExecutions: state.showAllExecutions,
        leftDrawerOpen: state.leftDrawerOpen,
        rightDrawerOpen: state.rightDrawerOpen,
      }),
    },
  ),
);
