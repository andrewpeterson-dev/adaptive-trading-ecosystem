import { BotControlPanel } from "@/components/cerberus/BotControlPanel";
import { PageHeader } from "@/components/layout/PageHeader";

export default function BotsPage() {
  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Autonomous"
        title="Bot Fleet"
        description="Monitor AI-generated and hybrid bots, inspect how each strategy is evolving, and jump into the learning detail view for parameter changes over time."
      />
      <div className="app-panel">
        <BotControlPanel />
      </div>
    </div>
  );
}
