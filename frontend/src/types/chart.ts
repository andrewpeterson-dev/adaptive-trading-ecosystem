export interface CandleData {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface TradeMarker {
  time: string | number;
  price: number;
  side: "buy" | "sell";
}

export type TimeFrame = "1m" | "5m" | "15m" | "1H" | "4H" | "1D";
