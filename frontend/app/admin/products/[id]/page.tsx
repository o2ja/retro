"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";

import {
  Banner,
  ConfirmButton,
  Field,
  PageHeader,
  Panel,
  Toast,
  Toggle,
  useToast,
} from "@/components/admin/ui";
import {
  addProductImage,
  createProduct,
  deleteProduct,
  getProduct,
  listBrands,
  listCategories,
  setInventory,
  updateProduct,
} from "@/lib/admin";
import type { Brand, Category } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

const CONDITIONS = ["", "NEW", "UNWORN", "EXCELLENT", "VERY_GOOD", "GOOD"];

type Form = Record<string, string | number | boolean | null | number[]>;

const BLANK: Form = {
  name: "",
  sku: "",
  brand_id: "",
  category_ids: [],
  short_description: "",
  description: "",
  price: "",
  compare_at_price: "",
  estimated_market_price: "",
  currency: "USD",
  reference_number: "",
  condition: "",
  production_year: "",
  movement: "",
  case_material: "",
  case_size: "",
  dial: "",
  crystal: "",
  strap_material: "",
  water_resistance: "",
  included_items: "",
  limited_edition: "",
  warranty_information: "",
  shipping_information: "",
  cutout_url: "",
  is_unique: true,
  active: true,
  featured: false,
  new_arrival: false,
  stock_quantity: 0,
  low_stock_threshold: 1,
};

/** Empty strings become null; empty money stays null rather than becoming 0. */
function clean(form: Form, keys: string[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const key of keys) {
    const value = form[key];
    if (value === "" || value === null) {
      out[key] = null;
    } else {
      out[key] = value;
    }
  }
  return out;
}

const CORE = [
  "name",
  "sku",
  "brand_id",
  "category_ids",
  "short_description",
  "description",
  "price",
  "compare_at_price",
  "estimated_market_price",
  "currency",
  "reference_number",
  "condition",
  "production_year",
  "movement",
  "case_material",
  "case_size",
  "dial",
  "crystal",
  "strap_material",
  "water_resistance",
  "included_items",
  "limited_edition",
  "warranty_information",
  "shipping_information",
  "cutout_url",
  "is_unique",
  "active",
  "featured",
  "new_arrival",
];

export default function AdminProductFormPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const isNew = id === "new";

  const [form, setForm] = useState<Form>(BLANK);
  const [imageUrl, setImageUrl] = useState("");
  const [brands, setBrands] = useState<Brand[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { toast, setToast } = useToast();

  useEffect(() => {
    listBrands().then(setBrands).catch(() => setBrands([]));
    listCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    if (isNew) return;
    getProduct(Number(id))
      .then((product) => {
        setForm({
          ...BLANK,
          ...Object.fromEntries(
            Object.entries(product).map(([key, value]) => [key, value ?? ""]),
          ),
          brand_id: product.brand?.id ?? "",
          category_ids: product.categories.map((c) => c.id),
          stock_quantity: product.stock_quantity,
          low_stock_threshold: product.low_stock_threshold,
        });
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load the product."),
      );
  }, [id, isNew]);

  const set = (key: string, value: unknown) =>
    setForm((current) => ({ ...current, [key]: value as never }));

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload = clean(form, CORE);
      if (payload.brand_id === "") payload.brand_id = null;
      if (payload.brand_id) payload.brand_id = Number(payload.brand_id);
      if (payload.production_year) payload.production_year = Number(payload.production_year);

      if (isNew) {
        const created = await createProduct({
          ...payload,
          stock_quantity: Number(form.stock_quantity) || 0,
          low_stock_threshold: Number(form.low_stock_threshold) || 0,
        });
        if (imageUrl) {
          await addProductImage(created.id, {
            url: imageUrl,
            alt_text: String(form.name),
            is_primary: true,
          });
        }
        router.push(`/admin/products/${created.id}`);
        return;
      }

      await updateProduct(Number(id), payload);
      await setInventory(Number(id), {
        quantity: Number(form.stock_quantity) || 0,
        low_stock_threshold: Number(form.low_stock_threshold) || 0,
      });
      if (imageUrl) {
        await addProductImage(Number(id), {
          url: imageUrl,
          alt_text: String(form.name),
          is_primary: true,
        });
        setImageUrl("");
      }
      setToast({ kind: "success", text: "Saved. The storefront now shows this." });
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  function remove() {
    deleteProduct(Number(id))
      .then((result) => {
        setToast({ kind: "success", text: result.message });
        router.push("/admin/products");
      })
      .catch((cause: unknown) =>
        setToast({
          kind: "error",
          text: cause instanceof ApiError ? cause.message : "Could not delete.",
        }),
      );
  }

  const text = (key: string) => ({
    value: String(form[key] ?? ""),
    onChange: (
      event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
    ) => set(key, event.target.value),
    className: "field",
  });

  return (
    <>
      <Link href="/admin/products" className="text-sm text-ink-muted hover:text-ink">
        ← Products
      </Link>

      <PageHeader
        title={isNew ? "Add a watch" : String(form.name || "Edit watch")}
        description={
          isNew
            ? "Only a name and stock number are required. Leave a price empty for price on request."
            : undefined
        }
        action={
          !isNew && (
            <Link
              href={`/shop/${form.slug}`}
              className="text-xs underline"
              target="_blank"
            >
              View on the storefront
            </Link>
          )
        }
      />

      {error && <Banner kind="error">{error}</Banner>}

      <form onSubmit={save} className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <Panel title="Basics">
            <div className="grid gap-4 px-4 py-4 sm:grid-cols-2">
              <Field label="Name *">
                <input required {...text("name")} />
              </Field>
              <Field label="Stock number (SKU) *">
                <input required {...text("sku")} />
              </Field>
              <Field label="Maker">
                <select {...text("brand_id")}>
                  <option value="">No maker</option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Reference number">
                <input {...text("reference_number")} />
              </Field>
              <div className="sm:col-span-2">
                <Field label="Collections">
                  <div className="flex flex-wrap gap-3 pt-1">
                    {categories.map((c) => {
                      const selected = (form.category_ids as number[]).includes(c.id);
                      return (
                        <label key={c.id} className="flex items-center gap-1.5 text-sm">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={(event) =>
                              set(
                                "category_ids",
                                event.target.checked
                                  ? [...(form.category_ids as number[]), c.id]
                                  : (form.category_ids as number[]).filter(
                                      (value) => value !== c.id,
                                    ),
                              )
                            }
                          />
                          {c.name}
                        </label>
                      );
                    })}
                  </div>
                </Field>
              </div>
              <div className="sm:col-span-2">
                <Field label="Short description">
                  <input {...text("short_description")} />
                </Field>
              </div>
              <div className="sm:col-span-2">
                <Field label="Description">
                  <textarea rows={5} {...text("description")} />
                </Field>
              </div>
            </div>
          </Panel>

          <Panel title="Pricing">
            <div className="grid gap-4 px-4 py-4 sm:grid-cols-3">
              <Field label="Selling price" hint="Leave empty for price on request">
                <input type="number" step="0.01" min="0" {...text("price")} />
              </Field>
              <Field label="Compare-at price" hint="Shown struck through">
                <input type="number" step="0.01" min="0" {...text("compare_at_price")} />
              </Field>
              <Field label="Estimated market value" hint="Reference only, never sold at">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  {...text("estimated_market_price")}
                />
              </Field>
            </div>
          </Panel>

          <Panel title="Specification">
            <div className="grid gap-4 px-4 py-4 sm:grid-cols-3">
              <Field label="Condition">
                <select {...text("condition")}>
                  {CONDITIONS.map((value) => (
                    <option key={value} value={value}>
                      {value ? value.replaceAll("_", " ") : "Not stated"}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Year">
                <input type="number" min="1900" max="2100" {...text("production_year")} />
              </Field>
              <Field label="Movement">
                <input {...text("movement")} />
              </Field>
              <Field label="Case material">
                <input {...text("case_material")} />
              </Field>
              <Field label="Case size">
                <input {...text("case_size")} />
              </Field>
              <Field label="Dial">
                <input {...text("dial")} />
              </Field>
              <Field label="Crystal">
                <input {...text("crystal")} />
              </Field>
              <Field label="Strap / bracelet">
                <input {...text("strap_material")} />
              </Field>
              <Field label="Water resistance">
                <input {...text("water_resistance")} />
              </Field>
              <Field label="Supplied with">
                <input {...text("included_items")} />
              </Field>
              <Field label="Edition">
                <input {...text("limited_edition")} />
              </Field>
            </div>
            <div className="grid gap-4 border-t border-line px-4 py-4 sm:grid-cols-2">
              <Field label="Warranty information">
                <textarea rows={3} {...text("warranty_information")} />
              </Field>
              <Field label="Shipping information">
                <textarea rows={3} {...text("shipping_information")} />
              </Field>
            </div>
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Visibility">
            <div className="space-y-3 px-4 py-4">
              <Toggle
                label="Published on the storefront"
                checked={Boolean(form.active)}
                onChange={(value) => set("active", value)}
              />
              <Toggle
                label="Featured"
                checked={Boolean(form.featured)}
                onChange={(value) => set("featured", value)}
              />
              <Toggle
                label="New arrival"
                checked={Boolean(form.new_arrival)}
                onChange={(value) => set("new_arrival", value)}
              />
              <Toggle
                label="One-of-a-kind piece"
                checked={Boolean(form.is_unique)}
                onChange={(value) => set("is_unique", value)}
              />
              <p className="text-xs text-ink-subtle">
                A one-of-a-kind piece reads as “Sold” at zero stock and is never
                reported as low stock.
              </p>
            </div>
          </Panel>

          <Panel title="Stock">
            <div className="grid gap-4 px-4 py-4">
              <Field label="Quantity">
                <input type="number" min="0" {...text("stock_quantity")} />
              </Field>
              <Field label="Low-stock threshold">
                <input type="number" min="0" {...text("low_stock_threshold")} />
              </Field>
              <p className="text-xs text-ink-subtle">
                Changes are recorded in the inventory history with the reason
                “manual adjustment”.
              </p>
            </div>
          </Panel>

          <Panel title="Photograph">
            <div className="space-y-3 px-4 py-4">
              <Field
                label="Image URL"
                hint="Files in frontend/public are served from /products/…"
              >
                <input
                  value={imageUrl}
                  onChange={(event) => setImageUrl(event.target.value)}
                  placeholder="/products/rolex-submariner.png"
                  className="field"
                />
              </Field>
              <Field
                label="Wrist cutout"
                hint="Straight-on PNG with no background. Leave empty to keep this watch off the homepage wrist."
              >
                <input {...text("cutout_url")} placeholder="/cutouts/rolex-datejust-silver-dial.png" />
              </Field>
            </div>
          </Panel>

          <div className="space-y-3">
            <button type="submit" disabled={busy} className="btn btn-primary w-full">
              {busy ? "Saving…" : isNew ? "Create watch" : "Save changes"}
            </button>
            {!isNew && (
              <ConfirmButton
                label="Delete this watch"
                question="Delete it? Watches that appear in orders are archived instead."
                onConfirm={remove}
              />
            )}
          </div>
        </div>
      </form>

      <Toast toast={toast} />
    </>
  );
}
