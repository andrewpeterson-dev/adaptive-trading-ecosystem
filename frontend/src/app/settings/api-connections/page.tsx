"use client";

import { Plug } from "lucide-react";
import { ApiConnectionsSection } from "@/components/settings/ApiConnectionsSection";

// Standalone page — accessible via direct URL.
// The same content is also rendered inline under Settings → Connections.
export default function ApiConnectionsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Plug className="h-5 w-5 text-primary" />
        <h2 className="text-xl font-semibold">API Connections</h2>
      </div>
      <ApiConnectionsSection />
    </div>
  );
}
