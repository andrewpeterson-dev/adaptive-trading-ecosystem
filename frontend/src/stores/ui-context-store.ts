import { create } from 'zustand';
import type { PageContext } from '@/types/cerberus';

interface UIContextState {
  pageContext: PageContext;

  // Actions
  updatePageContext: (context: Partial<PageContext>) => void;
  updateSelectedSymbol: (symbol: string | null) => void;
  updateSelectedAccount: (accountId: string | null) => void;
  updateRoute: (route: string, page: string) => void;
}

const DEFAULT_PAGE_CONTEXT: PageContext = {
  currentPage: '',
  route: '/',
  visibleComponents: [],
  focusedComponent: null,
  selectedSymbol: null,
  selectedAccountId: null,
  selectedBotId: null,
  componentState: {},
};

export const useUIContextStore = create<UIContextState>((set) => ({
  pageContext: DEFAULT_PAGE_CONTEXT,

  updatePageContext: (context) => set((state) => ({
    pageContext: { ...state.pageContext, ...context },
  })),

  updateSelectedSymbol: (symbol) => set((state) => ({
    pageContext: { ...state.pageContext, selectedSymbol: symbol },
  })),

  updateSelectedAccount: (accountId) => set((state) => ({
    pageContext: { ...state.pageContext, selectedAccountId: accountId },
  })),

  updateRoute: (route, page) => set((state) => ({
    pageContext: { ...state.pageContext, route, currentPage: page },
  })),
}));
