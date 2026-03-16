"use client";

import { useEffect, useState } from "react";
import StrategyPreview from "./StrategyPreview";
import { useBuilderStore } from "@/stores/builder-store";
import { useStrategyBuilderStore } from "@/stores/strategy-builder-store";
import type { StrategyRecord } from "@/types/strategy";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StrategyBuilderPageProps {
  mode?: "create" | "edit";
  initialStrategy?: StrategyRecord;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StrategyBuilderPage({ mode, initialStrategy }: StrategyBuilderPageProps) {
  const [activeMode, setActiveMode] = useState<"ai" | "manual" | "template">("ai");

  // ---- On-mount effects: hydrate builder store from edit data or pending spec ----
  useEffect(() => {
    if (initialStrategy) {
      useBuilderStore.getState().loadFromStrategy(initialStrategy);
    }

    const pendingSpec = useStrategyBuilderStore.getState().consumePendingSpec();
    if (pendingSpec) {
      // Cerberus widget → builder handoff: map PendingStrategy to builder fields
      // TODO: align PendingStrategy shape with StrategySpec for type-safe handoff
      useBuilderStore.getState().loadFromSpec(pendingSpec as any);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="app-page flex flex-col h-full">
      {/* ---- Mode tabs ---- */}
      <div className="p-4">
        <div className="app-segmented">
          <button
            className={`app-segment ${activeMode === "ai" ? "app-toggle-active" : ""}`}
            onClick={() => setActiveMode("ai")}
          >
            AI-Assisted
          </button>
          <button
            className={`app-segment ${activeMode === "manual" ? "app-toggle-active" : ""}`}
            onClick={() => setActiveMode("manual")}
          >
            Manual
          </button>
          <button
            className={`app-segment ${activeMode === "template" ? "app-toggle-active" : ""}`}
            onClick={() => setActiveMode("template")}
          >
            From Template
          </button>
        </div>
      </div>

      {/* ---- 60/40 split layout ---- */}
      <div className="grid grid-cols-1 xl:grid-cols-[3fr_2fr] h-[calc(100vh-120px)]">
        {/* Left panel */}
        <div className="overflow-y-auto border-r border-border">
          {activeMode === "ai" && (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              AI Chat — coming soon
            </div>
          )}
          {activeMode === "manual" && (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Manual Builder — coming soon
            </div>
          )}
          {activeMode === "template" && (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Template Gallery — coming soon
            </div>
          )}
        </div>

        {/* Right panel */}
        <div className="overflow-y-auto">
          <StrategyPreview activeMode={activeMode} onModeSwitch={setActiveMode} />
        </div>
      </div>
    </div>
  );
}
