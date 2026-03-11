"use client";

import Image from "next/image";
import Link from "next/link";

const HIGHLIGHTS = [
  {
    title: "Real data only",
    description:
      "Portfolio, risk, and order views stay grounded in actual broker and model data.",
  },
  {
    title: "Per-user broker security",
    description:
      "Credentials remain encrypted and isolated for each account across paper and live workflows.",
  },
  {
    title: "One calm workspace",
    description:
      "Strategy design, execution, analytics, and Cerberus guidance live in the same interface.",
  },
];

interface AuthShellProps {
  title: string;
  description: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export function AuthShell({
  title,
  description,
  children,
  footer,
}: AuthShellProps) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6 lg:px-8">
      <div className="grid w-full max-w-6xl gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
        <section className="hidden space-y-8 lg:block">
          <Link href="/" className="inline-flex items-center gap-3">
            <div className="app-card flex h-14 w-14 items-center justify-center rounded-[20px]">
              <Image
                src="/logo.svg"
                alt="Adaptive Trading"
                width={36}
                height={36}
                className="h-9 w-9 object-contain"
                priority
              />
            </div>
            <div>
              <p className="text-base font-semibold tracking-tight text-foreground">
                Adaptive Trading
              </p>
              <p className="text-sm text-muted-foreground">
                Strategy intelligence with execution discipline
              </p>
            </div>
          </Link>

          <div className="space-y-5">
            <p className="app-kicker">Trading Workspace</p>
            <h1 className="max-w-xl text-5xl font-semibold tracking-tight text-foreground">
              A calmer, sharper control room for systematic trading.
            </h1>
            <p className="max-w-xl text-base leading-8 text-muted-foreground">
              Build strategies, manage risk, and transition from paper to live
              execution inside a product that feels precise instead of noisy.
            </p>
          </div>

          <div className="grid gap-4">
            {HIGHLIGHTS.map((item) => (
              <div key={item.title} className="app-panel p-5">
                <p className="text-sm font-semibold text-foreground">
                  {item.title}
                </p>
                <p className="mt-1 text-sm leading-7 text-muted-foreground">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="app-panel overflow-hidden p-1">
          <div className="app-card rounded-[28px] p-6 sm:p-8">
            <div className="mb-8 space-y-4">
              <div className="inline-flex items-center gap-3 lg:hidden">
                <div className="app-card flex h-12 w-12 items-center justify-center rounded-[18px]">
                  <Image
                    src="/logo.svg"
                    alt="Adaptive Trading"
                    width={30}
                    height={30}
                    className="h-[30px] w-[30px] object-contain"
                    priority
                  />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">
                    Adaptive Trading
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Strategy intelligence workspace
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <p className="app-kicker">Account Access</p>
                <h2 className="text-3xl font-semibold tracking-tight text-foreground">
                  {title}
                </h2>
                <p className="text-sm leading-7 text-muted-foreground">
                  {description}
                </p>
              </div>
            </div>

            {children}

            {footer && (
              <div className="mt-6 border-t border-border/60 pt-5 text-sm text-muted-foreground">
                {footer}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
