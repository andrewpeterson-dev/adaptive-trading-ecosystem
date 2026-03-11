import type { SymbolSearchResult } from '@/types/trading';

export const SYMBOL_CATALOG: SymbolSearchResult[] = [
  { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'MSFT', name: 'Microsoft Corporation', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'NVDA', name: 'NVIDIA Corporation', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'AMZN', name: 'Amazon.com, Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'GOOGL', name: 'Alphabet Inc. Class A', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'META', name: 'Meta Platforms, Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'TSLA', name: 'Tesla, Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'AMD', name: 'Advanced Micro Devices, Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'NFLX', name: 'Netflix, Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'AVGO', name: 'Broadcom Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'ORCL', name: 'Oracle Corporation', exchange: 'NYSE', type: 'stock' },
  { symbol: 'CRM', name: 'Salesforce, Inc.', exchange: 'NYSE', type: 'stock' },
  { symbol: 'INTC', name: 'Intel Corporation', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'ADBE', name: 'Adobe Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'QCOM', name: 'QUALCOMM Incorporated', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'PLTR', name: 'Palantir Technologies Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'COIN', name: 'Coinbase Global, Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'SOFI', name: 'SoFi Technologies, Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'RIVN', name: 'Rivian Automotive, Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'JPM', name: 'JPMorgan Chase & Co.', exchange: 'NYSE', type: 'stock' },
  { symbol: 'BAC', name: 'Bank of America Corporation', exchange: 'NYSE', type: 'stock' },
  { symbol: 'V', name: 'Visa Inc.', exchange: 'NYSE', type: 'stock' },
  { symbol: 'MA', name: 'Mastercard Incorporated', exchange: 'NYSE', type: 'stock' },
  { symbol: 'WMT', name: 'Walmart Inc.', exchange: 'NYSE', type: 'stock' },
  { symbol: 'COST', name: 'Costco Wholesale Corporation', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'DIS', name: 'The Walt Disney Company', exchange: 'NYSE', type: 'stock' },
  { symbol: 'LLY', name: 'Eli Lilly and Company', exchange: 'NYSE', type: 'stock' },
  { symbol: 'UNH', name: 'UnitedHealth Group Incorporated', exchange: 'NYSE', type: 'stock' },
  { symbol: 'PFE', name: 'Pfizer Inc.', exchange: 'NYSE', type: 'stock' },
  { symbol: 'MRK', name: 'Merck & Co., Inc.', exchange: 'NYSE', type: 'stock' },
  { symbol: 'ABBV', name: 'AbbVie Inc.', exchange: 'NYSE', type: 'stock' },
  { symbol: 'JNJ', name: 'Johnson & Johnson', exchange: 'NYSE', type: 'stock' },
  { symbol: 'KO', name: 'The Coca-Cola Company', exchange: 'NYSE', type: 'stock' },
  { symbol: 'PEP', name: 'PepsiCo, Inc.', exchange: 'NASDAQ', type: 'stock' },
  { symbol: 'HD', name: 'The Home Depot, Inc.', exchange: 'NYSE', type: 'stock' },
  { symbol: 'SPY', name: 'SPDR S&P 500 ETF Trust', exchange: 'NYSE Arca', type: 'etf' },
  { symbol: 'QQQ', name: 'Invesco QQQ Trust', exchange: 'NASDAQ', type: 'etf' },
  { symbol: 'IWM', name: 'iShares Russell 2000 ETF', exchange: 'NYSE Arca', type: 'etf' },
  { symbol: 'DIA', name: 'SPDR Dow Jones Industrial Average ETF', exchange: 'NYSE Arca', type: 'etf' },
  { symbol: 'VTI', name: 'Vanguard Total Stock Market ETF', exchange: 'NYSE Arca', type: 'etf' },
  { symbol: 'ARKK', name: 'ARK Innovation ETF', exchange: 'NYSE Arca', type: 'etf' },
  { symbol: 'XLF', name: 'Financial Select Sector SPDR Fund', exchange: 'NYSE Arca', type: 'etf' },
  { symbol: 'XLE', name: 'Energy Select Sector SPDR Fund', exchange: 'NYSE Arca', type: 'etf' },
  { symbol: 'XLK', name: 'Technology Select Sector SPDR Fund', exchange: 'NYSE Arca', type: 'etf' },
  { symbol: 'SMH', name: 'VanEck Semiconductor ETF', exchange: 'NASDAQ', type: 'etf' },
  { symbol: 'GLD', name: 'SPDR Gold Shares', exchange: 'NYSE Arca', type: 'etf' },
  { symbol: 'TLT', name: 'iShares 20+ Year Treasury Bond ETF', exchange: 'NASDAQ', type: 'etf' },
  { symbol: 'IBIT', name: 'iShares Bitcoin Trust ETF', exchange: 'NASDAQ', type: 'etf' },
  { symbol: 'ETHA', name: 'iShares Ethereum Trust ETF', exchange: 'NASDAQ', type: 'etf' },
  { symbol: 'BTC-USD', name: 'Bitcoin USD', exchange: 'CRYPTO', type: 'crypto' },
  { symbol: 'ETH-USD', name: 'Ethereum USD', exchange: 'CRYPTO', type: 'crypto' },
];

function scoreMatch(query: string, candidate: SymbolSearchResult): number {
  const upperQuery = query.toUpperCase();
  const symbol = candidate.symbol.toUpperCase();
  const name = candidate.name.toUpperCase();

  if (symbol === upperQuery) return 1000;
  if (symbol.startsWith(upperQuery)) return 850 - symbol.length;
  if (name.startsWith(upperQuery)) return 780 - name.length;
  if (name.split(/\s+/).some((part) => part.startsWith(upperQuery))) return 700;
  if (symbol.includes(upperQuery)) return 620 - symbol.indexOf(upperQuery);
  if (name.includes(upperQuery)) return 500 - name.indexOf(upperQuery);
  return 0;
}

export function rankSymbolMatches(query: string, limit = 8): SymbolSearchResult[] {
  const trimmed = query.trim();
  if (!trimmed) return [];

  return SYMBOL_CATALOG
    .map((candidate) => ({ candidate, score: scoreMatch(trimmed, candidate) }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      return left.candidate.symbol.localeCompare(right.candidate.symbol);
    })
    .slice(0, limit)
    .map((entry) => entry.candidate);
}

export function lookupSymbolDetails(symbol: string): SymbolSearchResult | undefined {
  const upper = symbol.trim().toUpperCase();
  return SYMBOL_CATALOG.find((item) => item.symbol === upper);
}
