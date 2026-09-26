"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PhotoPlaceholder } from "@/components/primitives";
import { isSold, modelName, priceLabel } from "@/lib/api";
import type { ProductSummary } from "@/lib/types";

export type CollectionCategory = { slug: string; name: string; ids: number[] };

const OUT_MS = 300;

/**
 * Filter pills, then two clearly separate lists: what can be requested now,
 * and a compact archive of what has already sold. Filtering happens in the
 * browser from a membership map the server built, so it is instant.
 *
 * ponytail: holds the whole published catalogue client-side (API caps at 60).
 * Move to server-side paging once the collection outgrows that.
 */
export function Collection({
  products,
  categories,
  initialCategory = "",
  syncUrl = false,
}: {
  products: ProductSummary[];
  categories: CollectionCategory[];
  initialCategory?: string;
  syncUrl?: boolean;
}) {
  const known = categories.some((c) => c.slug === initialCategory) ? initialCategory : "";
  const [selected, setSelected] = useState(known);
  const [shown, setShown] = useState(known);
  const [leaving, setLeaving] = useState(false);

  const inCategory = (slug: string) =>
    slug ? products.filter((p) => categories.find((c) => c.slug === slug)?.ids.includes(p.id)) : products;
  const visible = inCategory(shown);
  const available = visible.filter((p) => !isSold(p));
  const sold = visible.filter(isSold);

  function choose(slug: string) {
    if (slug === selected) return;
    setSelected(slug);
    setLeaving(true);
    if (syncUrl) {
      const url = new URL(window.location.href);
      if (slug) url.searchParams.set("category", slug);
      else url.searchParams.delete("category");
      window.history.replaceState(null, "", url);
    }
  }

  // Let the current set fade out before the next one fades in.
  useEffect(() => {
    if (!leaving) return;
    const timer = setTimeout(() => {
      setShown(selected);
      setLeaving(false);
    }, OUT_MS);
    return () => clearTimeout(timer);
  }, [leaving, selected]);

  const pills = [{ slug: "", name: "All", count: products.length }].concat(
    categories.map((c) => ({ slug: c.slug, name: c.name, count: c.ids.length })),
  );

  return (
    <div>
      <div role="tablist" aria-label="Filter by category" className="no-scrollbar -mx-[var(--spacing-gutter)] flex gap-2 overflow-x-auto px-[var(--spacing-gutter)] sm:mx-0 sm:flex-wrap sm:px-0">
        {pills.map((pill) => {
          const active = pill.slug === selected;
          return (
            <button
              key={pill.slug || "all"}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => choose(pill.slug)}
              className={`flex shrink-0 items-center gap-2 rounded-full border px-4 py-2 text-sm transition-colors duration-300 ${
                active
                  ? "border-ink bg-ink text-ink-inverse"
                  : "border-line-strong text-ink-muted hover:border-ink hover:text-ink"
              }`}
            >
              {pill.name}
              <span className={`figures text-xs ${active ? "text-ink-inverse/70" : "text-ink-subtle"}`}>{pill.count}</span>
            </button>
          );
        })}
      </div>

      <div
        className={`transition-opacity ease-[var(--ease-luxury)] ${leaving ? "opacity-0 duration-300" : "opacity-100 duration-500"}`}
      >
        <div className="mt-10 mb-5 flex items-baseline justify-between border-b border-line pb-3">
          <h2 className="font-sans text-sm text-ink-muted">Available now</h2>
          <p className="figures text-sm text-ink-subtle">
            {available.length} {available.length === 1 ? "piece" : "pieces"}
          </p>
        </div>
        {available.length === 0 ? (
          <p className="py-16 text-center text-ink-muted">
            Nothing available in this category right now.{" "}
            <Link href="/contact" className="link-under text-ink">
              Ask us to find one
            </Link>
            .
          </p>
        ) : (
          <ul key={shown} className="grid grid-cols-2 gap-x-3 gap-y-10 md:grid-cols-3 md:gap-x-5 xl:grid-cols-4">
            {available.map((product, index) => (
              <li
                key={product.id}
                className="fade-in"
                style={{ "--delay": `${Math.min(index, 8) * 60}ms` } as React.CSSProperties}
              >
                <WatchCard product={product} priority={index < 4} />
              </li>
            ))}
          </ul>
        )}

        {sold.length > 0 && (
          <section className="mt-section-sm">
            <div className="mb-5 flex items-baseline justify-between border-b border-line pb-3">
              <h2 className="font-sans text-sm text-ink-muted">Previously sold</h2>
              <p className="text-sm text-ink-subtle">We can look for one like these</p>
            </div>
            <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
              {sold.map((product) => (
                <li key={product.id}>
                  <SoldCard product={product} />
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

/** The watch alone on a light panel when a cutout exists; its photograph otherwise. */
function WatchPlate({ product, priority }: { product: ProductSummary; priority: boolean }) {
  if (product.cutout_url) {
    return (
      <Image
        src={product.cutout_url}
        alt={`${product.brand?.name ?? ""} ${modelName(product)}`}
        fill
        sizes="(max-width: 768px) 50vw, (max-width: 1280px) 33vw, 25vw"
        quality={90}
        preload={priority}
        className="object-contain p-[8%] transition-transform duration-[900ms] ease-[var(--ease-luxury)] [filter:drop-shadow(0_0.9rem_0.9rem_rgb(0_0_0/0.18))] group-hover:-translate-y-[2%] group-hover:scale-[1.04]"
      />
    );
  }
  const image = product.primary_image;
  return image ? (
    <Image
      src={image.url}
      alt={image.alt_text ?? product.name}
      fill
      sizes="(max-width: 768px) 50vw, (max-width: 1280px) 33vw, 25vw"
      quality={85}
      preload={priority}
      className="object-cover transition-transform duration-[900ms] ease-[var(--ease-luxury)] group-hover:scale-[1.04]"
    />
  ) : (
    <PhotoPlaceholder seed={product.id} label="Photograph to follow" />
  );
}

export function WatchCard({ product, priority = false }: { product: ProductSummary; priority?: boolean }) {
  const sold = isSold(product);
  return (
    <Link href={`/shop/${product.slug}`} className="group block">
      <div
        data-reveal="image"
        className="relative aspect-[4/5] overflow-hidden rounded-lg bg-[radial-gradient(75%_60%_at_50%_45%,#ffffff_0%,var(--color-surface-muted)_100%)] transition-[box-shadow] duration-700 group-hover:shadow-[0_1.25rem_2.5rem_-1.25rem_rgb(0_0_0/0.25)]"
      >
        <WatchPlate product={product} priority={priority} />
      </div>
      <div className="mt-4 px-0.5">
        <p className="maker !text-[0.95rem]">{product.brand?.name}</p>
        <h3 className="mt-0.5 line-clamp-2 text-[1.2rem] leading-snug sm:text-[1.35rem]">{modelName(product)}</h3>
        <p className="figures mt-2 flex items-center gap-2 text-sm text-ink-muted">
          <span aria-hidden className={`size-1.5 rounded-full ${sold ? "bg-line-strong" : "bg-success"}`} />
          {sold ? "Sold" : priceLabel(product)}
        </p>
      </div>
    </Link>
  );
}

function SoldCard({ product }: { product: ProductSummary }) {
  return (
    <Link href={`/shop/${product.slug}`} className="group block">
      <div className="relative aspect-square overflow-hidden rounded-md bg-surface-muted grayscale transition-[filter] duration-700 group-hover:grayscale-0">
        <WatchPlate product={product} priority={false} />
      </div>
      <p className="mt-2 truncate text-xs text-ink-muted group-hover:text-ink">
        {product.brand?.name} {modelName(product)}
      </p>
    </Link>
  );
}
