import type { Metadata } from "next";
import "./globals.css";
import { NavHeader } from "@/components/layout/NavHeader";

export const metadata: Metadata = {
  title: "Strategy Intelligence | Adaptive Trading Ecosystem",
  description: "Build, analyze, and optimize trading strategies with AI-powered diagnostics",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>
        <NavHeader />
        <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
