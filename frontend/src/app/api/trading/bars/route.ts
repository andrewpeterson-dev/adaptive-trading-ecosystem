import { NextRequest, NextResponse } from "next/server";

/**
 * GET /api/trading/bars — proxies chart data to the FastAPI backend.
 * The chart has a proper empty/error state, so never synthesize bars here.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const symbol = searchParams.get("symbol") ?? "SPY";
  const timeframe = searchParams.get("timeframe") ?? "1D";
  const limit = searchParams.get("limit") ?? "300";

  const auth = request.headers.get("authorization") ?? "";
  const cookie = request.headers.get("cookie") ?? "";
  const backendUrl = process.env.API_URL || "http://localhost:8000";

  try {
    const res = await fetch(
      `${backendUrl}/api/trading/bars?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=${encodeURIComponent(limit)}`,
      {
        headers: {
          Authorization: auth,
          Cookie: cookie,
        },
        next: { revalidate: 60 },
      }
    );

    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: {
        "content-type": res.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "Chart data backend unavailable" },
      { status: 502 }
    );
  }
}
