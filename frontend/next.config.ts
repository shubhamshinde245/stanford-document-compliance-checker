import type { NextConfig } from "next";

const apiOrigin = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // High-effort requirement batches (especially 50–80 safeguard CSVs) take
  // minutes. Next rewrites otherwise kill the proxy after 30s with ECONNRESET.
  experimental: {
    proxyTimeout: 30 * 60 * 1000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
