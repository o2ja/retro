/**
 * The single place the storefront talks to the backend.
 *
 * Components never call `fetch` directly - they call these functions, so the
 * base URL, error shape and caching policy live in one file.
 */

import type {
  Brand,
  CatalogQuery,
  Category,
  Homepage,
  InquiryInput,
  Page,
  ProductDetail,
  ProductSummary,
  SiteSettings,
  SocialLink,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** The backend's error envelope: { error: { code, message, details? } }. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = {
  /** Seconds to cache. Omit for always-fresh (prices, stock, cart, checkout). */
  revalidate?: number;
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { revalidate, method = "GET", body, signal } = options;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    signal,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
    ...(revalidate === undefined
      ? { cache: "no-store" as const }
      : { next: { revalidate } }),
  });

  if (!response.ok) {
    let code = "http_error";
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      code = payload?.error?.code ?? code;
      message = payload?.error?.message ?? message;
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, code, message);
  }

  return (await response.json()) as T;
}

function toQueryString(query: Record<string, unknown>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const serialized = params.toString();
  return serialized ? `?${serialized}` : "";
}

/* -------------------------------------------------------------------------- */
/* Content: changes rarely, safe to cache briefly.                            */
/* -------------------------------------------------------------------------- */

export const getSiteSettings = () =>
  request<SiteSettings>("/api/public/settings", { revalidate: 300 });

export const getSocialLinks = () =>
  request<SocialLink[]>("/api/public/social-links", { revalidate: 300 });

export const getHomepage = () =>
  request<Homepage>("/api/public/homepage", { revalidate: 60 });

export const getBrands = () =>
  request<Brand[]>("/api/public/brands", { revalidate: 300 });

export const getCategories = () =>
  request<Category[]>("/api/public/categories", { revalidate: 300 });

/* -------------------------------------------------------------------------- */
/* Commerce: price and stock are never served stale.                          */
/* -------------------------------------------------------------------------- */

export const getProducts = (query: CatalogQuery = {}) =>
  request<Page<ProductSummary>>(
    `/api/public/products${toQueryString(query as Record<string, unknown>)}`,
  );

export const getProduct = (slug: string) =>
  request<ProductDetail>(`/api/public/products/${slug}`);

/** A request to buy. The owner follows up personally; nothing is charged online. */
export const sendInquiry = (body: InquiryInput) =>
  request<{ message: string }>("/api/public/inquiries", { method: "POST", body });

/* -------------------------------------------------------------------------- */
/* Display helpers                                                            */
/* -------------------------------------------------------------------------- */

export function formatMoney(amount: string | null, currency = "USD"): string {
  if (amount === null) return "";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(amount));
}

/** The model name without the maker repeated in front of it. */
export function modelName(product: Pick<ProductSummary, "name" | "brand">): string {
  const brand = product.brand?.name;
  if (brand && product.name.toLowerCase().startsWith(`${brand.toLowerCase()} `)) {
    return product.name.slice(brand.length + 1);
  }
  return product.name;
}

export function isSold(product: Pick<ProductSummary, "availability">): boolean {
  return product.availability === "SOLD" || product.availability === "OUT_OF_STOCK";
}

export function priceLabel(product: Pick<ProductSummary, "pricing">): string {
  const { pricing } = product;
  return pricing.price_on_request || pricing.final_price === null
    ? "Price on request"
    : formatMoney(pricing.final_price, pricing.currency);
}

/** A wa.me link from the store's phone number, or null when none is set. */
export function whatsappUrl(phone: string | null | undefined, text: string): string | null {
  const digits = phone?.replace(/\D/g, "");
  if (!digits || digits.length < 7) return null;
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
}

/**
 * The published collection plus, for each category, which pieces belong to it.
 * A category that holds every piece (or none) is left out: as a filter it does nothing.
 */
export async function getCollection() {
  const [all, categories] = await Promise.all([
    getProducts({ page_size: 60, sort: "featured" }),
    getCategories().catch(() => [] as Category[]),
  ]);
  const members = await Promise.all(
    categories.map((category) =>
      getProducts({ category: category.slug, page_size: 60 })
        .then((page) => page.items.map((item) => item.id))
        .catch(() => [] as number[]),
    ),
  );
  return {
    products: all.items,
    categories: categories
      .map((category, index) => ({ slug: category.slug, name: category.name, ids: members[index] }))
      .filter((category) => category.ids.length > 0 && category.ids.length < all.items.length),
  };
}
