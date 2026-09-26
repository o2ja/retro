"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PhotoPlaceholder } from "@/components/primitives";
import {
  Banner,
  EmptyRow,
  LinkButton,
  PageHeader,
  Pager,
  Panel,
  formatMoney,
} from "@/components/admin/ui";
import { listBrands, listCategories, listProducts } from "@/lib/admin";
import type { AdminProduct, Brand, Category, Page } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

export default function AdminProductsPage() {
  const [query, setQuery] = useState("");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [active, setActive] = useState("");
  const [lowStock, setLowStock] = useState(false);
  const [page, setPage] = useState(1);

  const [data, setData] = useState<Page<AdminProduct> | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listBrands().then(setBrands).catch(() => setBrands([]));
    listCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const load = useCallback(() => {
    listProducts({
      q: query || undefined,
      brand: brand || undefined,
      category: category || undefined,
      active: active === "" ? undefined : active,
      low_stock: lowStock || undefined,
      page,
      page_size: 20,
    })
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load products."),
      );
  }, [query, brand, category, active, lowStock, page]);

  useEffect(() => {
    load();
  }, [load]);

  const reset = () => setPage(1);

  return (
    <>
      <PageHeader
        title="Products"
        description="The catalogue the storefront reads from."
        action={<LinkButton href="/admin/products/new">Add a watch</LinkButton>}
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Name, SKU or reference"
          value={query}
          onChange={(event) => {
            reset();
            setQuery(event.target.value);
          }}
          className="field max-w-xs"
        />
        <select
          value={brand}
          onChange={(event) => {
            reset();
            setBrand(event.target.value);
          }}
          className="field max-w-[11rem]"
        >
          <option value="">All makers</option>
          {brands.map((b) => (
            <option key={b.id} value={b.slug}>
              {b.name}
            </option>
          ))}
        </select>
        <select
          value={category}
          onChange={(event) => {
            reset();
            setCategory(event.target.value);
          }}
          className="field max-w-[11rem]"
        >
          <option value="">All collections</option>
          {categories.map((c) => (
            <option key={c.id} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>
        <select
          value={active}
          onChange={(event) => {
            reset();
            setActive(event.target.value);
          }}
          className="field max-w-[10rem]"
        >
          <option value="">Any status</option>
          <option value="true">Published</option>
          <option value="false">Hidden</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={lowStock}
            onChange={(event) => {
              reset();
              setLowStock(event.target.checked);
            }}
          />
          Low stock only
        </label>
      </div>

      {error && <Banner kind="error">{error}</Banner>}

      <Panel>
        {!data ? (
          <EmptyRow>Loading…</EmptyRow>
        ) : data.items.length === 0 ? (
          <EmptyRow>No products match these filters.</EmptyRow>
        ) : (
          <>
            <ul className="divide-y divide-line">
              {data.items.map((product) => (
                <li key={product.id}>
                  <Link
                    href={`/admin/products/${product.id}`}
                    className="flex items-center gap-4 px-4 py-3 text-sm hover:bg-surface-muted"
                  >
                    <span className="relative size-12 shrink-0 bg-surface-muted">
                      {product.primary_image ? (
                        <Image
                          src={product.primary_image.url}
                          alt=""
                          fill
                          sizes="48px"
                          className="object-contain p-1"
                        />
                      ) : (
                        <PhotoPlaceholder
                          seed={product.id}
                          markClassName="w-3/5"
                        />
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{product.name}</span>
                      <span className="block truncate text-xs text-ink-subtle">
                        {product.brand?.name ?? "No maker"} · {product.sku}
                      </span>
                    </span>
                    <span className="hidden w-24 text-xs text-ink-muted sm:block">
                      {product.availability.replaceAll("_", " ").toLowerCase()}
                    </span>
                    <span className="w-16 text-right text-xs tabular-nums text-ink-muted">
                      {product.stock_quantity} in stock
                    </span>
                    <span className="w-24 text-right tabular-nums">
                      {formatMoney(product.price, product.currency)}
                    </span>
                    <span className="hidden w-16 text-right text-xs text-ink-subtle lg:block">
                      {product.active ? "Live" : "Hidden"}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <Pager
              page={data.page}
              total={data.total}
              pageSize={data.page_size}
              onPage={setPage}
            />
          </>
        )}
      </Panel>
    </>
  );
}
