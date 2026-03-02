import { NextRequest, NextResponse } from "next/server";

function generateMockBars(symbol: string, timeframe: string, count = 200) {
  const now = Date.now();
  const intervalMs: Record<string, number> = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1H": 60 * 60_000,
    "4H": 4 * 60 * 60_000,
    "1D": 24 * 60 * 60_000,
  };

  const interval = intervalMs[timeframe] ?? intervalMs["1D"];
  const basePrice = symbol === "SPY" ? 520 : symbol === "QQQ" ? 440 : 100 + Math.random() * 400;
  let price = basePrice;

  const bars = [];
  for (let i = count - 1; i >= 0; i--) {
    const timestamp = now - i * interval;
    const date = new Date(timestamp);

    const volatility = 0.008 + Math.random() * 0.007;
    const drift = (Math.random() - 0.48) * volatility;
    const open = price;
    const change1 = price * (drift + (Math.random() - 0.5) * volatility);
    const change2 = price * (drift + (Math.random() - 0.5) * volatility);
    const high = Math.max(open, open + change1, open + change2) + price * Math.random() * 0.003;
    const low = Math.min(open, open + change1, open + change2) - price * Math.random() * 0.003;
    const close = low + Math.random() * (high - low);
    price = close;

    const volume = Math.floor(500_000 + Math.random() * 2_000_000);

    const time =
      timeframe === "1D"
        ? `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
        : Math.floor(timestamp / 1000);

    bars.push({
      time,
      open: +open.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      close: +close.toFixed(2),
      volume,
    });
  }

  return bars;
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const symbol = searchParams.get("symbol") ?? "SPY";
  const timeframe = searchParams.get("timeframe") ?? "1D";

  const bars = generateMockBars(symbol, timeframe);

  return NextResponse.json({ bars });
}
