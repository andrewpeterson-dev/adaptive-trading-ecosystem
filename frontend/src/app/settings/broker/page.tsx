"use client";

import { useState } from "react";
import { KeyRound, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { BrokerForm } from "@/components/settings/BrokerForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type BrokerType = "alpaca" | "webull";

const BROKERS: { id: BrokerType; name: string; description: string }[] = [
  {
    id: "alpaca",
    name: "Alpaca",
    description: "Commission-free equities and crypto execution with separate paper and live endpoints.",
  },
  {
    id: "webull",
    name: "Webull",
    description: "Broker connectivity for extended-hours trading and advanced retail routing.",
  },
];

export default function BrokerSettingsPage() {
  const [selectedBroker, setSelectedBroker] = useState<BrokerType>("alpaca");

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Connections"
        title="Broker Configuration"
        description="Manage the encrypted broker credentials that power trading, account sync, and paper-to-live transitions."
        badge={
          <Badge variant="info">
            <KeyRound className="h-3.5 w-3.5" />
            Broker Access
          </Badge>
        }
        actions={
          <Button asChild variant="ghost" size="sm">
            <Link href="/settings">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Settings
            </Link>
          </Button>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
        <div className="app-panel p-3">
          <div className="flex gap-2 overflow-x-auto xl:flex-col">
            {BROKERS.map((broker) => (
              <button
                key={broker.id}
                onClick={() => setSelectedBroker(broker.id)}
                className={`min-w-[220px] rounded-[22px] px-4 py-4 text-left transition-all xl:min-w-0 ${
                  selectedBroker === broker.id
                    ? "bg-foreground text-background shadow-[0_18px_30px_-24px_rgba(2,6,23,0.9)]"
                    : "text-muted-foreground hover:bg-white/[0.04] hover:text-foreground"
                }`}
              >
                <div className="text-sm font-semibold">{broker.name}</div>
                <div
                  className={`mt-1 text-xs leading-5 ${
                    selectedBroker === broker.id
                      ? "text-background/80"
                      : "text-muted-foreground"
                  }`}
                >
                  {broker.description}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="app-panel p-6 sm:p-7">
          <BrokerForm broker={selectedBroker} />
        </div>
      </div>
    </div>
  );
}
