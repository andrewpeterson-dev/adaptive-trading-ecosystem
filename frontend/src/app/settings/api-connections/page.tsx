"use client";

import { Plug } from "lucide-react";
import { ApiConnectionsSection } from "@/components/settings/ApiConnectionsSection";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";

export default function ApiConnectionsPage() {
  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Connections"
        title="API Connections"
        description="Centralize broker, data, and research providers, then control which services are primary, fallback, or disconnected."
        badge={
          <Badge variant="info">
            <Plug className="h-3.5 w-3.5" />
            Providers
          </Badge>
        }
      />
      <ApiConnectionsSection />
    </div>
  );
}
