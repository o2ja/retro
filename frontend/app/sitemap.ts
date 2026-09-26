import type { MetadataRoute } from "next";

import { getProducts } from "@/lib/api";

const BASE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/** Built from the live catalogue, so new watches appear on their own. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const products = await getProducts({ page_size: 60 }).catch(() => null);

  return [
    ...["", "/shop", "/about", "/contact"].map((path) => ({
      url: `${BASE}${path}`,
      changeFrequency: "weekly" as const,
    })),
    ...(products?.items ?? []).map((product) => ({
      url: `${BASE}/shop/${product.slug}`,
      changeFrequency: "daily" as const,
    })),
  ];
}
