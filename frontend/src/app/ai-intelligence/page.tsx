"use client";

import { Brain } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { RiskGauge } from "@/components/intelligence/RiskGauge";
import { ActiveEvents } from "@/components/intelligence/ActiveEvents";

export default function AIIntelligencePage() {
  return (
    <div className="app-page">
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

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_1.5fr]">
        <RiskGauge />
        <ActiveEvents />
      </div>
    </div>
  );
}
