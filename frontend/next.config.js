/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone output for Docker; Vercel ignores this and uses its own builder
  ...(process.env.VERCEL ? {} : { output: "standalone" }),

  // Optimize CSS — removes unused rules from the final CSS bundle
  experimental: {
    optimizeCss: true,
  },

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
        // Long-cache immutable static assets (Next.js hashes filenames)
        source: "/_next/static/(.*)",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
    ];
  },

  async rewrites() {
    const apiUrl =
      process.env.API_URL ||
      (process.env.NODE_ENV === "production"
        ? "https://api-production-3b8df.up.railway.app"
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
