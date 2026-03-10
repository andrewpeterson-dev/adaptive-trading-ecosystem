import { apiFetch } from "./client";

export type TradingMode = "paper" | "live";

interface ModeResponse {
  mode: TradingMode;
  previous?: TradingMode;
}

export async function getServerMode(): Promise<TradingMode> {
  const res = await apiFetch<ModeResponse>("/api/user/mode");
  return res.mode;
}

export async function setServerMode(mode: TradingMode): Promise<ModeResponse> {
  return apiFetch<ModeResponse>("/api/user/set-mode", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}
