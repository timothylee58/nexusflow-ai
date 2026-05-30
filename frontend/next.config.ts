import type { NextConfig } from "next";

const apiBase =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/agent/:path*", destination: `${apiBase}/agent/:path*` },
      { source: "/api/audit/:path*", destination: `${apiBase}/audit/:path*` },
      { source: "/api/sse/:path*", destination: `${apiBase}/sse/:path*` },
      { source: "/api/status", destination: `${apiBase}/status` },
    ];
  },
};

export default nextConfig;
