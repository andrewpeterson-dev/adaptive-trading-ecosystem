import { StrategyBuilder } from "@/components/strategy-builder/StrategyBuilder";
import { Layers, BookOpen, Cpu } from "lucide-react";
import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* Nav */}
      <header className="border-b bg-card/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Cpu className="h-5 w-5 text-primary" />
            <span className="font-semibold tracking-tight">
              Adaptive Trading Ecosystem
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 font-medium">
              Strategy Intelligence
            </span>
          </div>
          <nav className="flex items-center gap-1">
            <Link
              href="/"
              className="px-3 py-1.5 rounded-md text-sm font-medium text-foreground bg-muted"
            >
              Builder
            </Link>
            <Link
              href="/strategies"
              className="px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            >
              Strategies
            </Link>
          </nav>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <StrategyBuilder />
      </main>
    </div>
  );
}
