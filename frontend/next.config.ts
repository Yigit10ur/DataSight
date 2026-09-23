import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits .next/standalone, a self-contained server the Docker image runs.
  output: "standalone",
};

export default nextConfig;
