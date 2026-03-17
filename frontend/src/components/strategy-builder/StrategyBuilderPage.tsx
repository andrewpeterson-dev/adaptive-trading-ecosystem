"use client";

import { useEffect, useState } from "react";
import AIChat from "./AIChat";
import ManualBuilder from "./ManualBuilder";
import StrategyPreview from "./StrategyPreview";
import TemplateGallery from "./TemplateGallery";
import { useBuilderStore } from "@/stores/builder-store";
import { useStrategyBuilderStore } from "@/stores/strategy-builder-store";
import type { StrategyRecord } from "@/types/strategy";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StrategyBuilderPageProps {
  initialStrategy?: StrategyRecord;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StrategyBuilderPage({ initialStrategy }: StrategyBuilderPageProps) {
  const [activeMode, setActiveMode] = useState<"ai" | "manual" | "template">("ai");

  // ---- On-mount effects: hydrate builder store from edit data or pending spec ----
  // Intentionally mount-only: initialStrategy is the server-fetched record and must not
  // re-trigger hydration if the object reference changes between renders.
  useEffect(() => {
    if (initialStrategy) {
      // Edit mode: load the existing strategy — takes priority over any stale pending spec
      useBuilderStore.getState().loadFromStrategy(initialStrategy);
      // Consume and discard any stale pending spec to prevent it from overwriting on future navigation
      useStrategyBuilderStore.getState().consumePendingSpec();
      return;
    }

    // Create mode: check for Cerberus widget → builder handoff
    const pendingSpec = useStrategyBuilderStore.getState().consumePendingSpec();
    if (pendingSpec) {
      useBuilderStore.getState().loadFromSpec(pendingSpec as any);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      <div className="grid grid-cols-1 xl:grid-cols-[3fr_2fr] flex-1 min-h-0">
        {/* Left panel */}
        <div className="overflow-y-auto border-r border-border">
          {activeMode === "ai" && <AIChat />}
          {activeMode === "manual" && <ManualBuilder />}
          {activeMode === "template" && <TemplateGallery onModeSwitch={setActiveMode} />}
        </div>

        {/* Right panel */}
        <div className="overflow-y-auto">
          <StrategyPreview activeMode={activeMode} onModeSwitch={setActiveMode} />
        </div>
      </div>
    </div>
  );
}
