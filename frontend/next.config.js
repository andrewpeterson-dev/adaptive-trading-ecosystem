/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone output for Docker; Vercel ignores this and uses its own builder
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
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
