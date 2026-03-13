"use client";

import { Brain } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { RiskGauge } from "@/components/intelligence/RiskGauge";
import { ActiveEvents } from "@/components/intelligence/ActiveEvents";
import { NewsFeed } from "@/components/intelligence/NewsFeed";
import { SectorMomentum } from "@/components/intelligence/SectorMomentum";
import { SentimentTicker } from "@/components/intelligence/SentimentTicker";
import { EarningsCalendar } from "@/components/intelligence/EarningsCalendar";

export default function AIIntelligencePage() {
  return (
    <div className="app-page">
      <SubNav
        items={[
          { href: "/ai-intelligence", label: "Market Intel" },
          { href: "/models", label: "Models" },
          { href: "/quant", label: "Quant" },
        ]}
      />

      <PageHeader
        eyebrow="AI Reasoning Layer"
        title="Market Intelligence"
        description="Real-time market context, risk assessment, and active events powering bot decision-making."
        meta={
          <span className="app-pill font-mono tracking-normal">
            <Brain className="mr-1.5 inline h-3 w-3" />
            Live
          </span>
        }
      />

      {/* Row 1: Risk Score + Sentiment */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <RiskGauge />
        <SentimentTicker />
      </div>

      {/* Row 2: News + Sector Momentum */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.5fr_1fr]">
        <NewsFeed />
        <SectorMomentum />
      </div>

      {/* Row 3: Earnings + Active Events */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <EarningsCalendar />
        <ActiveEvents />
      </div>
    </div>
  );
}
