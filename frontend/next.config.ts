import type { NextConfig } from "next";
import path from "path";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://trustlayerapi.onrender.com";

const nextConfig: NextConfig = {
  // Prevent Next.js from inferring the wrong workspace root when multiple lockfiles exist
  outputFileTracingRoot: path.join(__dirname, ".."),

  // Disabled for Docker production builds (re-enable standalone for containers)
  // output: "standalone",

  // Work around Next.js 16 WASM serialization bug on Windows with @next/swc WASM bindings
  typescript: {
    // Types are checked in IDE - skip during build to avoid WASM bug
    ignoreBuildErrors: true,
  },

  // Proxy /api/v1/* to the FastAPI backend to avoid CORS issues in production
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiUrl}/api/v1/:path*`,
      },
    ];
  },

  // Expose environment variables to the browser
  env: {
    NEXT_PUBLIC_API_URL: apiUrl,
  },
};

export default nextConfig;

