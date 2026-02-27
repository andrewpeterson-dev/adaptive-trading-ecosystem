export interface IndicatorParameter {
  type: "integer" | "float";
  default: number;
  min: number;
  max: number;
  description: string;
}

export interface IndicatorMetadata {
  id: string;
  name: string;
  category: "Momentum" | "Trend" | "Volatility" | "Volume";
  description_simple: string;
  description_detailed: string;
  formula: string;
  parameters: Record<string, IndicatorParameter>;
  output_type: "single_line" | "multi_line" | "histogram";
  outputs: string[];
  how_traders_use_it: string[];
  pros: string[];
  cons: string[];
  common_mistakes: string[];
  when_it_fails: string[];
  advanced_quant_note: string;
  related_indicators: string[];
  default_thresholds?: {
    overbought?: number;
    oversold?: number;
  };
}

export type IndicatorId =
  | "rsi"
  | "sma"
  | "ema"
  | "macd"
  | "bollinger_bands"
  | "atr"
  | "vwap"
  | "stochastic"
  | "obv";

export const CATEGORY_COLORS: Record<string, string> = {
  Momentum: "text-blue-400 bg-blue-400/10 border-blue-400/20",
  Trend: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  Volatility: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  Volume: "text-purple-400 bg-purple-400/10 border-purple-400/20",
};
