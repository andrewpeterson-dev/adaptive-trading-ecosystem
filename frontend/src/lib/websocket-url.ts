function deriveOrigin(): string {
  if (typeof window === "undefined") {
    return "";
  }
  const envUrl = process.env.NEXT_PUBLIC_WS_URL;
  if (envUrl) {
    return envUrl
      .replace(/^http:/, "ws:")
      .replace(/^https:/, "wss:")
      .replace(/\/ws\/?$/, "")
      .replace(/\/$/, "");
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const hostname = window.location.hostname;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return `${protocol}://${hostname}:8000`;
  }
  return `${protocol}://${window.location.host}`;
}

export function getWebSocketOrigin(): string {
  return deriveOrigin();
}

export function getMarketWebSocketBase(): string {
  const origin = deriveOrigin();
  return origin ? `${origin}/ws` : "";
}
