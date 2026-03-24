const isProduction = process.env.NODE_ENV === "production";
const isVercel = Boolean(process.env.VERCEL);
const useStandaloneOutput =
  process.env.NEXT_OUTPUT_MODE === "standalone" ||
  process.env.NEXT_STANDALONE === "1";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone packaging is opt-in so local production builds stay stable.
  ...(isProduction && !isVercel && useStandaloneOutput ? { output: "standalone" } : {}),

  images: {
    dangerouslyAllowSVG: true,
    contentDispositionType: "attachment",
    contentSecurityPolicy: "default-src 'self'; script-src 'none'; sandbox;",
  },

  eslint: {
    ignoreDuringBuilds: true,
  },

  // Keep the dev server predictable; CSS optimization belongs in production builds.
  experimental: isProduction ? { optimizeCss: true } : {},

  // Strip console.log in production to avoid noisy dev logs leaking
  compiler: {
    removeConsole: process.env.NODE_ENV === "production" ? { exclude: ["error", "warn"] } : false,
  },

  // Security + performance headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
      {
        // Never long-cache dev assets; stale chunk caches cause route/module mismatches.
        source: "/_next/static/(.*)",
        headers: [
          {
            key: "Cache-Control",
            value: isProduction
              ? "public, max-age=31536000, immutable"
              : "no-store, must-revalidate",
          },
        ],
      },
    ];
  },

  async rewrites() {
    const apiUrl =
      process.env.API_URL ||
      (process.env.NODE_ENV === "production"
        ? "https://your-api.railway.app"
        : "http://localhost:8000");
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
