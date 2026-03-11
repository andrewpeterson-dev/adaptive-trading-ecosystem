"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { ConnectApiModal, ApiProvider } from "./ConnectApiModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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
  BROKERAGE: "Brokerage",
  MARKET_DATA: "Market Data",
  OPTIONS_DATA: "Options Data",
  NEWS: "News",
  FUNDAMENTALS: "Fundamentals",
  MACRO: "Macro",
  CRYPTO_BROKER: "Crypto",
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
      <div className="app-inset flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="text-sm font-medium text-foreground">
            {provider.name}
          </span>
          <Badge variant="neutral">
            {API_TYPE_LABELS[provider.api_type] ?? provider.api_type}
          </Badge>
        </div>
        <Button
          onClick={() => setShowModal(true)}
          variant="secondary"
          size="sm"
          className="h-9 rounded-full px-3"
        >
          <Plus className="h-3 w-3" />
          Connect
        </Button>
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
