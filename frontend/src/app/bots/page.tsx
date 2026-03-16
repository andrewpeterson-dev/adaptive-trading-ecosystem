import { BotControlPanel } from "@/components/cerberus/BotControlPanel";
import { PageHeader } from "@/components/layout/PageHeader";

export default function BotsPage() {
  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Trading Terminal"
        title="Bot Fleet"
        description="Monitor autonomous trading bots, track live P&L, and inspect AI decision-making in real time."
      />
      <div className="app-panel">
        <BotControlPanel />
      </div>
    </div>
  );
}
