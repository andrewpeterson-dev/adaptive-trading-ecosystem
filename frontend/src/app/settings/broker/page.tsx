"use client";

import { useState } from "react";
import { KeyRound, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { BrokerForm } from "@/components/settings/BrokerForm";

type BrokerType = "alpaca" | "webull";

const BROKERS: { id: BrokerType; name: string; description: string }[] = [
  {
    id: "alpaca",
    name: "Alpaca",
    description: "Commission-free stock & crypto trading API",
  },
  {
    id: "webull",
    name: "WebULL",
    description: "Advanced trading platform with extended hours",
  },
];

export default function BrokerSettingsPage() {
  const [selectedBroker, setSelectedBroker] = useState<BrokerType>("alpaca");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/settings"
          className="p-1.5 rounded-md border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex items-center gap-2">
          <KeyRound className="h-5 w-5 text-primary" />
          <h2 className="text-xl font-semibold">Broker Configuration</h2>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Broker selector sidebar */}
        <div className="flex flex-col gap-2 min-w-[180px]">
          {BROKERS.map((broker) => (
            <button
              key={broker.id}
              onClick={() => setSelectedBroker(broker.id)}
              className={`text-left px-3 py-2.5 rounded-md border transition-colors ${
                selectedBroker === broker.id
                  ? "bg-muted border-border/50 text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              <div className="text-sm font-medium">{broker.name}</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {broker.description}
              </div>
            </button>
          ))}
        </div>

        {/* Form */}
        <div className="flex-1 rounded-lg border border-border/50 bg-card p-6">
          <BrokerForm broker={selectedBroker} />
        </div>
      </div>
    </div>
  );
}
