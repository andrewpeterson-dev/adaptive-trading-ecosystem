"use client";

import React, { useState } from "react";
import { Info } from "lucide-react";
import { getIndicatorMetadata } from "@/lib/indicatorRegistry";
import type { IndicatorId } from "@/types/indicators";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { InfoModal } from "@/components/ui/info-modal";

interface IndicatorInfoButtonProps {
  indicator: IndicatorId;
  size?: "sm" | "md";
}

export function IndicatorInfoButton({
  indicator,
  size = "sm",
}: IndicatorInfoButtonProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const metadata = getIndicatorMetadata(indicator);

  if (!metadata) return null;

  const iconSize = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";
  const btnSize = size === "sm" ? "h-5 w-5" : "h-6 w-6";

  return (
    <>
      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className={`inline-flex items-center justify-center rounded-full ${btnSize} text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors focus:outline-none focus:ring-2 focus:ring-ring/40`}
              aria-label={`Info about ${metadata.name}`}
            >
              <Info className={iconSize} />
            </button>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-xs">
            <p className="font-medium text-foreground">{metadata.name}</p>
            <p className="text-muted-foreground mt-0.5">
              {metadata.description_simple}
            </p>
            <p className="text-primary/80 mt-1 text-[10px] uppercase tracking-wider">
              Click for details
            </p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <InfoModal
        indicator={metadata}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </>
  );
}
