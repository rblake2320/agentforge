/** @type {import('next').NextConfig} */
const nextConfig = {
  // Disable Next.js's automatic 308 trailing-slash redirect.
  // Without this, /api/v1/agents/ gets 308'd to /api/v1/agents, which then
  // causes FastAPI to 307-redirect back to localhost:8400 directly — a
  // cross-origin redirect that strips the Authorization header, causing 401s.
  skipTrailingSlashRedirect: true,

  async rewrites() {
    return [
      // Match both /api/v1/foo/ (trailing slash) and /api/v1/foo (no trailing slash)
      // Because skipTrailingSlashRedirect=true means Next.js no longer normalizes them
      {
        source: "/api/:path*/",
        destination: "http://localhost:8400/api/:path*/",
      },
      {
        source: "/api/:path*",
        destination: "http://localhost:8400/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
