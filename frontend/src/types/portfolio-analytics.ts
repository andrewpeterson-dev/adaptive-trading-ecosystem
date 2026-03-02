export interface PortfolioAnalytics {
  volatility: number;
  var_95: number;
  var_99: number;
  expected_shortfall: number;
  beta: number;
  concentration_hhi: number;
  risk_rating: string;
  positions_analyzed: number;
}
