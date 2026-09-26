import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Next 16 requires an explicit allowlist of qualities.
    qualities: [75, 85, 90],
  },
  // Retired storefront features. Old links (and search results) land somewhere useful.
  async redirects() {
    return [
      { source: "/cart", destination: "/shop", permanent: true },
      { source: "/checkout", destination: "/shop", permanent: true },
      { source: "/order/:path*", destination: "/contact", permanent: true },
      { source: "/offers", destination: "/shop", permanent: true },
      { source: "/journal/:path*", destination: "/about", permanent: true },
      { source: "/journal", destination: "/about", permanent: true },
      { source: "/collections", destination: "/shop", permanent: true },
    ];
  },
};

export default nextConfig;
