import type { SymbolSearchResult } from "@/types/trading";

export const SYMBOL_CATALOG: SymbolSearchResult[] = [
  { symbol: "SPY", name: "SPDR S&P 500 ETF Trust", exchange: "NYSE Arca", type: "etf" },
  { symbol: "QQQ", name: "Invesco QQQ Trust", exchange: "NASDAQ", type: "etf" },
  { symbol: "IWM", name: "iShares Russell 2000 ETF", exchange: "NYSE Arca", type: "etf" },
  { symbol: "DIA", name: "SPDR Dow Jones Industrial Average ETF", exchange: "NYSE Arca", type: "etf" },
  { symbol: "VTI", name: "Vanguard Total Stock Market ETF", exchange: "NYSE Arca", type: "etf" },
  { symbol: "ARKK", name: "ARK Innovation ETF", exchange: "NYSE Arca", type: "etf" },
  { symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "MSFT", name: "Microsoft Corporation", exchange: "NASDAQ", type: "stock" },
  { symbol: "NVDA", name: "NVIDIA Corporation", exchange: "NASDAQ", type: "stock" },
  { symbol: "AMZN", name: "Amazon.com, Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "GOOGL", name: "Alphabet Inc. Class A", exchange: "NASDAQ", type: "stock" },
  { symbol: "META", name: "Meta Platforms, Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "TSLA", name: "Tesla, Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "AMD", name: "Advanced Micro Devices, Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "NFLX", name: "Netflix, Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "AVGO", name: "Broadcom Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "PLTR", name: "Palantir Technologies Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "COIN", name: "Coinbase Global, Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "SOFI", name: "SoFi Technologies, Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "RIVN", name: "Rivian Automotive, Inc.", exchange: "NASDAQ", type: "stock" },
  { symbol: "JPM", name: "JPMorgan Chase & Co.", exchange: "NYSE", type: "stock" },
  { symbol: "BAC", name: "Bank of America Corporation", exchange: "NYSE", type: "stock" },
  { symbol: "V", name: "Visa Inc.", exchange: "NYSE", type: "stock" },
  { symbol: "MA", name: "Mastercard Incorporated", exchange: "NYSE", type: "stock" },
  { symbol: "WMT", name: "Walmart Inc.", exchange: "NYSE", type: "stock" },
  { symbol: "COST", name: "Costco Wholesale Corporation", exchange: "NASDAQ", type: "stock" },
  { symbol: "XOM", name: "Exxon Mobil Corporation", exchange: "NYSE", type: "stock" },
  { symbol: "CVX", name: "Chevron Corporation", exchange: "NYSE", type: "stock" },
  { symbol: "UNH", name: "UnitedHealth Group Incorporated", exchange: "NYSE", type: "stock" },
  { symbol: "LLY", name: "Eli Lilly and Company", exchange: "NYSE", type: "stock" },
  { symbol: "ABBV", name: "AbbVie Inc.", exchange: "NYSE", type: "stock" },
  { symbol: "PFE", name: "Pfizer Inc.", exchange: "NYSE", type: "stock" },
  { symbol: "XLF", name: "Financial Select Sector SPDR Fund", exchange: "NYSE Arca", type: "etf" },
  { symbol: "XLE", name: "Energy Select Sector SPDR Fund", exchange: "NYSE Arca", type: "etf" },
  { symbol: "SMH", name: "VanEck Semiconductor ETF", exchange: "NASDAQ", type: "etf" },
  { symbol: "TLT", name: "iShares 20+ Year Treasury Bond ETF", exchange: "NASDAQ", type: "etf" },
  { symbol: "GLD", name: "SPDR Gold Shares", exchange: "NYSE Arca", type: "etf" },
  { symbol: "SLV", name: "iShares Silver Trust", exchange: "NYSE Arca", type: "etf" },
];

function symbolScore(result: SymbolSearchResult, rawQuery: string): number {
  const query = rawQuery.trim().toLowerCase();
  if (!query) return 0;

  const symbol = result.symbol.toLowerCase();
  const name = result.name.toLowerCase();
  const exchange = result.exchange?.toLowerCase() ?? "";

  let score = 0;

  if (symbol === query) score += 200;
  if (name === query) score += 120;
  if (symbol.startsWith(query)) score += 110;
  if (name.startsWith(query)) score += 90;
  if (symbol.includes(query)) score += 70;
  if (name.includes(query)) score += 50;
  if (exchange.includes(query)) score += 20;

  if (result.type === "stock") score += 4;

  return score;
}

export function rankSymbols(query: string, limit = 8): SymbolSearchResult[] {
  const ranked = SYMBOL_CATALOG
    .map((entry) => ({ entry, score: symbolScore(entry, query) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return a.entry.symbol.localeCompare(b.entry.symbol);
    })
    .slice(0, limit)
    .map((item) => item.entry);

  return ranked;
}

export function getCatalogSymbol(symbol: string): SymbolSearchResult | undefined {
  return SYMBOL_CATALOG.find((entry) => entry.symbol === symbol.toUpperCase());
}
