"use client";

import { useEffect, useState } from "react";
import AIChat from "./AIChat";
import ManualBuilder from "./ManualBuilder";
import StrategyPreview from "./StrategyPreview";
import TemplateGallery from "./TemplateGallery";
import { useBuilderStore } from "@/stores/builder-store";
import { useStrategyBuilderStore } from "@/stores/strategy-builder-store";
import type { StrategyRecord } from "@/types/strategy";
import { Bot, Wrench, LayoutGrid } from "lucide-react";

interface StrategyBuilderPageProps {
  initialStrategy?: StrategyRecord;
}

export default function StrategyBuilderPage({ initialStrategy }: StrategyBuilderPageProps) {
  const [activeMode, setActiveMode] = useState<"ai" | "manual" | "template">("ai");

  useEffect(() => {
    if (initialStrategy) {
      useBuilderStore.getState().loadFromStrategy(initialStrategy);
      useStrategyBuilderStore.getState().consumePendingSpec();
      return;
    }
    const pendingSpec = useStrategyBuilderStore.getState().consumePendingSpec();
    if (pendingSpec) {
      useBuilderStore.getState().loadFromSpec(pendingSpec as any);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Header bar with mode tabs */}
      <div className="flex items-center justify-between border-b border-border px-6 py-3 bg-card/50">
        <div>
          <h1 className="text-lg font-bold text-foreground">Strategy Builder</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Design, test, and deploy trading strategies</p>
        </div>
        <div className="app-segmented">
          <button
            className={`app-segment flex items-center gap-2 ${activeMode === "ai" ? "app-toggle-active" : ""}`}
            onClick={() => setActiveMode("ai")}
          >
            <Bot className="h-3.5 w-3.5" />
            AI Builder
          </button>
          <button
            className={`app-segment flex items-center gap-2 ${activeMode === "manual" ? "app-toggle-active" : ""}`}
            onClick={() => setActiveMode("manual")}
          >
            <Wrench className="h-3.5 w-3.5" />
            Manual
          </button>
          <button
            className={`app-segment flex items-center gap-2 ${activeMode === "template" ? "app-toggle-active" : ""}`}
            onClick={() => setActiveMode("template")}
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            Templates
          </button>
        </div>
      </div>

      {/* Content area - full remaining height */}
      {activeMode === "template" ? (
        /* Template mode: full width gallery */
        <div className="flex-1 overflow-y-auto">
          <TemplateGallery onModeSwitch={setActiveMode} />
        </div>
      ) : (
        /* AI and Manual modes: split layout */
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_420px] flex-1 min-h-0">
          {/* Left panel - builder */}
          <div className="overflow-y-auto border-r border-border">
            {activeMode === "ai" && <AIChat />}
            {activeMode === "manual" && <ManualBuilder />}
          </div>
          {/* Right panel - live preview */}
          <div className="overflow-y-auto bg-card/30">
            <StrategyPreview activeMode={activeMode} onModeSwitch={setActiveMode} />
          </div>
        </div>
      )}
    </div>
  );
}
