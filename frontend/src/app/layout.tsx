import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AppShell } from "@/components/layout/AppShell";
import { Providers } from "@/components/layout/Providers";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";

const initialThemeScript = `
(() => {
  try {
    const html = document.documentElement;
    const storedMode = window.localStorage.getItem("trading_mode");
    const storedTheme = window.localStorage.getItem("workspace_theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme =
      storedMode === "live"
        ? "dark"
        : storedMode === "paper"
          ? "light"
          : storedTheme === "light" || storedTheme === "dark"
            ? storedTheme
        : prefersDark
          ? "dark"
          : "light";
    html.classList.toggle("dark", theme === "dark");
  } catch (_) {}
})();
`;

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "Adaptive Trading",
  description:
    "Adaptive Trading combines strategy design, portfolio intelligence, and live execution in one polished workspace.",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon.svg", type: "image/svg+xml" },
    ],
    shortcut: "/favicon.ico",
    apple: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans">
        <script dangerouslySetInnerHTML={{ __html: initialThemeScript }} />
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
