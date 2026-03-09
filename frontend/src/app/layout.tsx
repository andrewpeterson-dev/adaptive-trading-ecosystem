import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { NavHeader } from "@/components/layout/NavHeader";
import { Providers } from "@/components/layout/Providers";
import { AIWidget } from "@/components/cerberus/AIWidget";
import { ConfirmationModal } from "@/components/cerberus/ConfirmationModal";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export const metadata: Metadata = {
  title: "AI Trading",
  description:
    "Build, analyze, and optimize trading strategies with AI-powered diagnostics",
  icons: {
    icon: "/logo.png",
    apple: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          <NavHeader />
          <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">{children}</main>
          <AIWidget />
          <ConfirmationModal />
        </Providers>
      </body>
    </html>
  );
}
