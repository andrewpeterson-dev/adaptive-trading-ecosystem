"use client";

import { useEffect, useMemo, useState } from "react";
import { Layers3 } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCompactNumber } from "@/lib/trading/format";
import type { OptionContract } from "@/types/trading";

interface OptionsChainResponse {
  expirations: string[];
  contracts: OptionContract[];
  selected_expiration?: string;
  selectedExpiration?: string;
}

function numberCell(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function OptionsChainTab({ symbol }: { symbol: string }) {
  const [data, setData] = useState<OptionsChainResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [expiration, setExpiration] = useState("");
  const [side, setSide] = useState<"all" | "call" | "put">("all");
  const [strikeQuery, setStrikeQuery] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadChain() {
      setLoading(true);
      try {
        const query = new URLSearchParams({ symbol });
        if (expiration) query.set("expiration", expiration);

        const payload = await apiFetch<OptionsChainResponse>(
          `/api/trading/options-chain?${query.toString()}`,
        );
        if (cancelled) return;

        setData(payload);
        const nextExpiration =
          expiration ||
          payload.selected_expiration ||
          payload.selectedExpiration ||
          payload.expirations?.[0] ||
          "";
        setExpiration(nextExpiration);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadChain();
    return () => {
      cancelled = true;
    };
  }, [expiration, symbol]);

  const rows = useMemo(() => {
    const selectedExpiration = expiration || data?.selected_expiration || data?.selectedExpiration;
    return (data?.contracts || [])
      .filter((contract) => !selectedExpiration || contract.expiration === selectedExpiration)
      .filter((contract) => side === "all" || contract.type === side)
      .filter((contract) => {
        if (!strikeQuery.trim()) return true;
        return contract.strike.toString().includes(strikeQuery.trim());
      })
      .sort((a, b) => {
        if (a.strike !== b.strike) return a.strike - b.strike;
        return a.type.localeCompare(b.type);
      });
  }, [data, expiration, side, strikeQuery]);

  if (loading) {
    return (
      <div className="rounded-[20px] border border-border/70 bg-muted/20 px-4 py-4 text-sm text-muted-foreground">
        Loading options chain for {symbol}...
      </div>
    );
  }

  if (!data || !data.contracts?.length) {
    return (
      <EmptyState
        icon={<Layers3 className="h-5 w-5 text-muted-foreground" />}
        title="No options chain available"
        description={`Contracts are not available for ${symbol} from the active market-data source yet.`}
        className="border border-dashed border-border/70 bg-muted/15"
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto]">
        <select
          value={expiration}
          onChange={(event) => setExpiration(event.target.value)}
          className="app-input"
        >
          {(data.expirations || []).map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          value={side}
          onChange={(event) => setSide(event.target.value as "all" | "call" | "put")}
          className="app-input"
        >
          <option value="all">All contracts</option>
          <option value="call">Calls</option>
          <option value="put">Puts</option>
        </select>

        <input
          value={strikeQuery}
          onChange={(event) => setStrikeQuery(event.target.value)}
          placeholder="Strike"
          className="app-input lg:w-28"
        />
      </div>

      <div className="rounded-[20px] border border-border/70 bg-background/70 px-3 py-3 text-xs text-muted-foreground">
        {rows.length} contract rows · Greeks, IV, volume, and open interest update from the connected options feed.
      </div>

      <div className="app-table-shell overflow-x-auto">
        <table className="app-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Strike</th>
              <th>Bid</th>
              <th>Ask</th>
              <th>Last</th>
              <th>IV</th>
              <th>Delta</th>
              <th>Gamma</th>
              <th>Theta</th>
              <th>Vega</th>
              <th>Volume</th>
              <th>Open Int</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((contract) => (
              <tr key={contract.symbol}>
                <td>
                  <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                    contract.type === "call"
                      ? "bg-emerald-500/12 text-emerald-300"
                      : "bg-red-500/12 text-red-200"
                  }`}>
                    {contract.type}
                  </span>
                </td>
                <td className="font-mono text-sm">{numberCell(contract.strike)}</td>
                <td className="font-mono text-sm">{numberCell(contract.bid)}</td>
                <td className="font-mono text-sm">{numberCell(contract.ask)}</td>
                <td className="font-mono text-sm">{numberCell(contract.last)}</td>
                <td className="font-mono text-sm">
                  {contract.implied_volatility != null
                    ? `${(contract.implied_volatility * 100).toFixed(1)}%`
                    : "—"}
                </td>
                <td className="font-mono text-sm">{numberCell(contract.delta, 4)}</td>
                <td className="font-mono text-sm">{numberCell(contract.gamma, 4)}</td>
                <td className="font-mono text-sm">{numberCell(contract.theta, 4)}</td>
                <td className="font-mono text-sm">{numberCell(contract.vega, 4)}</td>
                <td className="font-mono text-sm">{formatCompactNumber(contract.volume ?? null)}</td>
                <td className="font-mono text-sm">{formatCompactNumber(contract.open_interest ?? null)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
