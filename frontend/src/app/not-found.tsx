import Link from "next/link";
import { Compass, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="app-page">
      <section className="app-hero">
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 py-10 text-center">
          <div className="app-empty-icon h-14 w-14">
            <Compass className="h-6 w-6 text-muted-foreground" />
          </div>
          <div className="space-y-3">
            <p className="app-kicker">Navigation</p>
            <h1 className="text-4xl font-semibold tracking-tight text-foreground">
              That page does not exist
            </h1>
            <p className="text-sm leading-7 text-muted-foreground sm:text-base">
              The route may have moved, the link may be stale, or the workspace is
              pointing at a page that has not been built yet.
            </p>
          </div>
          <Button asChild variant="primary">
            <Link href="/dashboard">
              <ArrowLeft className="h-4 w-4" />
              Return to dashboard
            </Link>
          </Button>
        </div>
      </section>
    </div>
  );
}
