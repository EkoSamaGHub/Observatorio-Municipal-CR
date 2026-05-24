import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// Proxy /api/* (server-side) to the Railway FastAPI. The admin control plane
// uses a session cookie set by the Discord OAuth callback; routing through
// the Vercel origin makes that cookie first-party so modern browsers (Safari
// ITP, Chrome 3p cookie phaseout, Brave) actually send it on subsequent
// fetches.
const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/admin/:path*", destination: `${API_ORIGIN}/admin/:path*` },
    ];
  },
};

export default withNextIntl(nextConfig);
