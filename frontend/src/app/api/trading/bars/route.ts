import { NextRequest, NextResponse } from "next/server";

/**
 * GET /api/trading/bars — returns OHLCV candlestick data.
 * Tries the FastAPI backend first; falls back to generated data
 * so the chart always renders something.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const symbol = searchParams.get("symbol") ?? "SPY";
  const timeframe = searchParams.get("timeframe") ?? "1D";

  // Forward auth header to backend
  const auth = request.headers.get("authorization") ?? "";
  const cookie = request.headers.get("cookie") ?? "";

  // Try backend first
  try {
    const backendUrl = process.env.API_URL || "http://localhost:8000";
    const tfMap: Record<string, string> = {
      "1m": "m1",
      "5m": "m5",
      "15m": "m15",
      "1H": "h1",
      "4H": "h4",
      "1D": "d1",
    };
    const interval = tfMap[timeframe] ?? "d1";
    const res = await fetch(
      `${backendUrl}/api/trading/bars?symbol=${encodeURIComponent(symbol)}&timeframe=${interval}`,
      {
        headers: {
          Authorization: auth,
          Cookie: cookie,
        },
        next: { revalidate: 60 },
      }
    );
    if (res.ok) {
      const data = await res.json();
      if (data.bars && data.bars.length > 0) {
        return NextResponse.json(data);
      }
    }
  } catch {
    // Backend unavailable — fall through to generated data
  }

  // Fallback: generate realistic-looking price data
  const bars = generateBars(symbol, timeframe);
  return NextResponse.json({ bars });
}

function generateBars(symbol: string, timeframe: string, count = 200) {
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
  const basePrices: Record<string, number> = {
    SPY: 520,
    QQQ: 440,
    AAPL: 230,
    TSLA: 340,
    NVDA: 890,
    MSFT: 420,
  };
  let price = basePrices[symbol] ?? 100 + Math.random() * 400;

  const bars = [];
  for (let i = count - 1; i >= 0; i--) {
    const timestamp = now - i * interval;
    const date = new Date(timestamp);

    const volatility = 0.008 + Math.random() * 0.007;
    const drift = (Math.random() - 0.48) * volatility;
    const open = price;
    const change1 = price * (drift + (Math.random() - 0.5) * volatility);
    const change2 = price * (drift + (Math.random() - 0.5) * volatility);
    const high =
      Math.max(open, open + change1, open + change2) +
      price * Math.random() * 0.003;
    const low =
      Math.min(open, open + change1, open + change2) -
      price * Math.random() * 0.003;
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
