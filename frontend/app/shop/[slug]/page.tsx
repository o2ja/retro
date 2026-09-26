import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { WatchCard } from "@/components/collection";
import { RequestPanel } from "@/components/inquiry";
import { ProductGallery } from "@/components/product-gallery";
import { ApiError, formatMoney, getProduct, getSiteSettings, isSold, modelName, priceLabel } from "@/lib/api";
import type { ProductDetail, ProductSpecifications } from "@/lib/types";

const SPEC_LABELS: Record<keyof ProductSpecifications, string> = {
  reference_number: "Reference",
  sku: "Stock number",
  condition: "Condition",
  production_year: "Year",
  movement: "Movement",
  case_material: "Case",
  case_size: "Diameter",
  dial: "Dial",
  crystal: "Crystal",
  strap_material: "Strap",
  water_resistance: "Water resistance",
  included_items: "Supplied with",
  limited_edition: "Edition",
};

const CONDITION_LABELS: Record<string, string> = {
  NEW: "New",
  UNWORN: "Unworn",
  EXCELLENT: "Excellent",
  VERY_GOOD: "Very good",
  GOOD: "Good",
};

async function load(slug: string): Promise<ProductDetail | null> {
  try {
    return await getProduct(slug);
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 404) return null;
    throw cause;
  }
}

export async function generateMetadata(props: PageProps<"/shop/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const product = await load(slug);
  if (!product) return { title: "Watch not found" };

  const description = product.short_description ?? product.description?.slice(0, 160) ?? undefined;
  return {
    title: product.name,
    description,
    openGraph: {
      title: product.name,
      description,
      type: "website",
      images: product.primary_image ? [product.primary_image.url] : undefined,
    },
  };
}

export default async function ProductPage(props: PageProps<"/shop/[slug]">) {
  const { slug } = await props.params;
  const [product, settings] = await Promise.all([load(slug), getSiteSettings().catch(() => null)]);
  if (!product) notFound();

  const sold = isSold(product);

  // Only the rows this watch actually has; the stock number is for the store.
  const specs = (Object.keys(SPEC_LABELS) as (keyof ProductSpecifications)[])
    .filter((key) => key !== "sku")
    .map((key) => {
      const raw = product.specifications[key];
      if (raw === null || raw === undefined || raw === "") return null;
      const value = key === "condition" ? (CONDITION_LABELS[String(raw)] ?? String(raw)) : String(raw);
      return { label: SPEC_LABELS[key], value };
    })
    .filter((row): row is { label: string; value: string } => row !== null);

  return (
    <div className="pt-16 pb-24 sm:pt-20 lg:pb-0">
      <div className="lg:shell lg:grid lg:grid-cols-12 lg:gap-6 lg:pt-10">
        <div className="lg:col-span-7">
          <ProductGallery images={product.images} productName={product.name} seed={product.id} />
        </div>

        <div className="shell pt-10 lg:sticky lg:top-28 lg:col-span-4 lg:col-start-9 lg:self-start lg:px-0 lg:pt-6">
          <nav aria-label="Breadcrumb" className="fade-in text-xs text-ink-subtle">
            <Link href="/shop" className="link-line">
              Collection
            </Link>
            <span aria-hidden className="mx-2">
              /
            </span>
            <span>{product.brand?.name ?? product.name}</span>
          </nav>

          <p className="maker mt-10">{product.brand?.name}</p>
          <h1 className="mt-3 text-[clamp(2.6rem,1.9rem+2.6vw,4.25rem)] leading-[0.98] tracking-[-0.02em]">
            <span className="rise">
              <span style={{ "--delay": "100ms" } as React.CSSProperties}>{modelName(product)}</span>
            </span>
          </h1>

          <div className="fade-in mt-7 flex items-baseline justify-between gap-4 border-y border-line py-5" style={{ "--delay": "250ms" } as React.CSSProperties}>
            <p className="figures text-xl">{sold ? "Sold" : priceLabel(product)}</p>
            <p className="flex items-center gap-2 text-sm text-ink-muted">
              <span aria-hidden className={`size-1.5 rounded-full ${sold ? "bg-line-strong" : "bg-clay"}`} />
              {sold ? "No longer available" : product.stock_quantity <= 1 ? "One piece" : "Available"}
            </p>
          </div>

          {product.pricing.price_on_request && product.pricing.estimated_market_price && (
            <p className="mt-3 text-xs text-ink-subtle">
              Estimated market value{" "}
              {formatMoney(product.pricing.estimated_market_price, product.pricing.currency)}. The store will confirm
              the price.
            </p>
          )}

          {product.short_description && (
            <p className="mt-7 text-[1.05rem] leading-relaxed text-ink-muted">{product.short_description}</p>
          )}

          <div className="mt-9">
            <RequestPanel product={product} storePhone={settings?.contact_phone ?? null} />
          </div>

          {specs.length > 0 && (
            <section className="mt-14">
              <h2 className="eyebrow">Specification</h2>
              <dl className="mt-4 border-t border-line">
                {specs.map((row) => (
                  <div key={row.label} className="grid grid-cols-[8rem_1fr] gap-4 border-b border-line py-3.5 text-sm">
                    <dt className="text-ink-subtle">{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          {product.description && (
            <section className="mt-12">
              <h2 className="eyebrow">About this piece</h2>
              <p className="mt-4 leading-relaxed text-ink-muted">{product.description}</p>
            </section>
          )}

          {(product.warranty_information || product.shipping_information) && (
            <section className="mt-12 space-y-6 border-t border-line pt-8 text-sm">
              {product.warranty_information && (
                <div>
                  <h2 className="eyebrow">Warranty</h2>
                  <p className="mt-2 text-ink-muted">{product.warranty_information}</p>
                </div>
              )}
              {product.shipping_information && (
                <div>
                  <h2 className="eyebrow">Delivery</h2>
                  <p className="mt-2 text-ink-muted">{product.shipping_information}</p>
                </div>
              )}
            </section>
          )}
        </div>
      </div>

      {product.related.length > 0 && (
        <section className="shell mt-section border-t border-line pt-section-sm pb-section">
          <div className="mb-12 flex flex-wrap items-end justify-between gap-4">
            <h2 data-split className="text-[clamp(2rem,1.5rem+2vw,3.25rem)]">Also in the collection</h2>
            <Link href="/shop" className="link-under text-[0.9375rem] text-ink-muted hover:text-ink">
              See every piece
            </Link>
          </div>
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 lg:gap-6">
            {product.related.slice(0, 3).map((item) => (
              <li key={item.id}>
                <WatchCard product={item} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
