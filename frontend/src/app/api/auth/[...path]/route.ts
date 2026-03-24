import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_URL =
  process.env.API_URL ||
  (process.env.NODE_ENV === "production"
    ? "https://your-api.railway.app"
    : "http://localhost:8000");

function buildBackendUrl(request: NextRequest, path: string[]) {
  const upstream = new URL(`/api/auth/${path.join("/")}`, BACKEND_URL);
  request.nextUrl.searchParams.forEach((value, key) => {
    upstream.searchParams.append(key, value);
  });
  return upstream;
}

function copyResponseHeaders(source: Response, target: NextResponse) {
  source.headers.forEach((value, key) => {
    if (key.toLowerCase() === "set-cookie") {
      return;
    }
    target.headers.set(key, value);
  });

  const getSetCookie = (
    source.headers as Headers & { getSetCookie?: () => string[] }
  ).getSetCookie;
  const setCookies = typeof getSetCookie === "function"
    ? getSetCookie.call(source.headers)
    : source.headers.get("set-cookie")
      ? [source.headers.get("set-cookie") as string]
      : [];

  for (const cookie of setCookies) {
    target.headers.append("set-cookie", cookie);
  }
}

async function proxyAuth(request: NextRequest, path: string[]) {
  const auth = request.headers.get("authorization");
  const contentType = request.headers.get("content-type");
  const csrf = request.headers.get("x-csrf-token");
  const cookie = request.headers.get("cookie");

  const headers = new Headers();
  if (auth) headers.set("authorization", auth);
  if (contentType) headers.set("content-type", contentType);
  if (csrf) headers.set("x-csrf-token", csrf);
  if (cookie) headers.set("cookie", cookie);

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  try {
    const upstream = await fetch(buildBackendUrl(request, path), init);
    const body = await upstream.text();
    const response = new NextResponse(body, { status: upstream.status });
    copyResponseHeaders(upstream, response);
    if (!response.headers.has("content-type")) {
      response.headers.set("content-type", "application/json");
    }
    return response;
  } catch {
    return NextResponse.json(
      { detail: "Authentication backend unavailable" },
      { status: 502 }
    );
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxyAuth(request, params.path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxyAuth(request, params.path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxyAuth(request, params.path);
}

export async function OPTIONS(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  return proxyAuth(request, params.path);
}
