"use client";

import React from "react";
import type { IndicatorMetadata } from "@/types/indicators";
import { CATEGORY_COLORS } from "@/types/indicators";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  BookOpen,
  Code2,
  Brain,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Lightbulb,
  TrendingUp,
} from "lucide-react";

interface InfoModalProps {
  indicator: IndicatorMetadata;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function SectionList({
  items,
  icon: Icon,
  iconColor,
}: {
  items: string[];
  icon: React.ElementType;
  iconColor: string;
}) {
  return (
    <ul className="space-y-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2.5 text-sm leading-relaxed">
          <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${iconColor}`} />
          <span className="text-foreground/90">{item}</span>
        </li>
      ))}
    </ul>
  );
}

function ParameterTable({ params }: { params: IndicatorMetadata["parameters"] }) {
  const entries = Object.entries(params);
  if (entries.length === 0) return <p className="text-sm text-muted-foreground">No configurable parameters.</p>;

  return (
    <div className="rounded-md border overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Parameter</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Default</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Range</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Description</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, p]) => (
            <tr key={name} className="border-b last:border-0">
              <td className="px-3 py-2 font-mono text-primary">{name}</td>
              <td className="px-3 py-2 font-mono">{p.default}</td>
              <td className="px-3 py-2 font-mono text-muted-foreground">
                {p.min}&ndash;{p.max}
              </td>
              <td className="px-3 py-2 text-muted-foreground">{p.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function InfoModal({ indicator, open, onOpenChange }: InfoModalProps) {
  const catColor = CATEGORY_COLORS[indicator.category] ?? "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          <div className="flex items-center gap-3">
            <DialogTitle className="text-xl">{indicator.name}</DialogTitle>
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${catColor}`}>
              {indicator.category}
            </span>
          </div>
          <DialogDescription className="mt-1">{indicator.description_simple}</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          <Tabs defaultValue="simple" className="w-full">
            <div className="px-6 pt-4 sticky top-0 bg-card z-10">
              <TabsList className="w-full">
                <TabsTrigger value="simple" className="flex-1 gap-1.5">
                  <BookOpen className="h-3.5 w-3.5" />
                  Simple
                </TabsTrigger>
                <TabsTrigger value="technical" className="flex-1 gap-1.5">
                  <Code2 className="h-3.5 w-3.5" />
                  Technical
                </TabsTrigger>
                <TabsTrigger value="advanced" className="flex-1 gap-1.5">
                  <Brain className="h-3.5 w-3.5" />
                  Advanced
                </TabsTrigger>
              </TabsList>
            </div>

            {/* Tab 1: Simple Explanation */}
            <TabsContent value="simple" className="px-6 pb-6 space-y-5">
              <div>
                <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-line">
                  {indicator.description_detailed}
                </p>
              </div>

              {indicator.default_thresholds && (
                <div className="flex gap-3">
                  {indicator.default_thresholds.overbought !== undefined && (
                    <div className="flex-1 rounded-md border p-3 bg-red-500/5 border-red-500/20">
                      <div className="text-xs text-red-400 font-medium uppercase tracking-wide">
                        Overbought
                      </div>
                      <div className="text-2xl font-mono mt-1">
                        {indicator.default_thresholds.overbought}
                      </div>
                    </div>
                  )}
                  {indicator.default_thresholds.oversold !== undefined && (
                    <div className="flex-1 rounded-md border p-3 bg-emerald-500/5 border-emerald-500/20">
                      <div className="text-xs text-emerald-400 font-medium uppercase tracking-wide">
                        Oversold
                      </div>
                      <div className="text-2xl font-mono mt-1">
                        {indicator.default_thresholds.oversold}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div>
                <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-primary" />
                  How Traders Use It
                </h4>
                <SectionList
                  items={indicator.how_traders_use_it}
                  icon={CheckCircle2}
                  iconColor="text-emerald-400"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-emerald-400">Strengths</h4>
                  <SectionList items={indicator.pros} icon={CheckCircle2} iconColor="text-emerald-400/60" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold mb-2 text-red-400">Limitations</h4>
                  <SectionList items={indicator.cons} icon={XCircle} iconColor="text-red-400/60" />
                </div>
              </div>
            </TabsContent>

            {/* Tab 2: Technical Details */}
            <TabsContent value="technical" className="px-6 pb-6 space-y-5">
              <div>
                <h4 className="text-sm font-semibold mb-2">Formula</h4>
                <div className="rounded-md bg-muted/50 border p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
                  {indicator.formula}
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-2">Parameters</h4>
                <ParameterTable params={indicator.parameters} />
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-2">Output</h4>
                <div className="text-sm text-muted-foreground">
                  <span className="font-mono text-primary">{indicator.output_type}</span>
                  {indicator.outputs.length > 0 && (
                    <span>
                      {" "}&mdash;{" "}
                      {indicator.outputs.map((o, i) => (
                        <span key={o}>
                          <code className="text-foreground bg-muted px-1 rounded">{o}</code>
                          {i < indicator.outputs.length - 1 && ", "}
                        </span>
                      ))}
                    </span>
                  )}
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  Common Mistakes
                </h4>
                <SectionList
                  items={indicator.common_mistakes}
                  icon={AlertTriangle}
                  iconColor="text-amber-400"
                />
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <XCircle className="h-4 w-4 text-red-400" />
                  When It Fails
                </h4>
                <SectionList
                  items={indicator.when_it_fails}
                  icon={XCircle}
                  iconColor="text-red-400"
                />
              </div>

              {indicator.related_indicators.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Related Indicators</h4>
                  <div className="flex gap-2 flex-wrap">
                    {indicator.related_indicators.map((r) => (
                      <span
                        key={r}
                        className="text-xs px-2 py-1 rounded-md bg-muted border font-mono"
                      >
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </TabsContent>

            {/* Tab 3: Advanced Quant Insight */}
            <TabsContent value="advanced" className="px-6 pb-6 space-y-5">
              <div className="rounded-md border border-primary/20 bg-primary/5 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Lightbulb className="h-4 w-4 text-primary" />
                  <h4 className="text-sm font-semibold text-primary">Quantitative Insight</h4>
                </div>
                <p className="text-sm leading-relaxed text-foreground/90">
                  {indicator.advanced_quant_note}
                </p>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-2">Formula Breakdown</h4>
                <div className="rounded-md bg-muted/50 border p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
                  {indicator.formula}
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-3">Failure Modes &amp; Edge Cases</h4>
                <SectionList items={indicator.when_it_fails} icon={AlertTriangle} iconColor="text-amber-400" />
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-3">Practical Mistakes to Avoid</h4>
                <SectionList items={indicator.common_mistakes} icon={XCircle} iconColor="text-red-400" />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
}
