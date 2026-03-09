"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { ConnectApiModal, ApiProvider } from "./ConnectApiModal";

interface AvailableProviderCardProps {
  provider: ApiProvider;
  onConnect: (
    provider: ApiProvider,
    credentials: Record<string, string>,
    is_paper: boolean,
    nickname?: string
  ) => Promise<void>;
}

const API_TYPE_LABELS: Record<string, string> = {
  brokerage: "Brokerage",
  market_data: "Market Data",
  options_data: "Options Data",
  news: "News",
  fundamentals: "Fundamentals",
  macro: "Macro",
  crypto_broker: "Crypto",
};

export function AvailableProviderCard({
  provider,
  onConnect,
}: AvailableProviderCardProps) {
  const [showModal, setShowModal] = useState(false);

  const handleConnect = async (
    credentials: Record<string, string>,
    is_paper: boolean,
    nickname?: string
  ) => {
    await onConnect(provider, credentials, is_paper, nickname);
  };

  return (
    <>
      <div className="flex items-center justify-between rounded-xl border border-border/50 bg-card/50 px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="text-sm font-medium text-muted-foreground">
            {provider.name}
          </span>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest border text-muted-foreground bg-muted border-border/50">
            {API_TYPE_LABELS[provider.api_type] ?? provider.api_type}
          </span>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border/50 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        >
          <Plus className="h-3 w-3" />
          Connect
        </button>
      </div>

      {showModal && (
        <ConnectApiModal
          provider={provider}
          onConnect={handleConnect}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}
