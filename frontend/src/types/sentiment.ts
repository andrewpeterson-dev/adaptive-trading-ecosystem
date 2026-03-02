export interface TickerSentiment {
  ticker: string;
  score: number;
  relevance: number;
  summary: string;
}

export interface SentimentReport {
  market_mood: string;
  ticker_sentiments: Record<string, { score: number; relevance: number }>;
  article_count: number;
  report_time: string;
}
