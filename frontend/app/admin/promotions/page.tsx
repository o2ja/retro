"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Banner,
  ConfirmButton,
  EmptyRow,
  Field,
  PageHeader,
  Panel,
  Toast,
  formatDate,
  useToast,
} from "@/components/admin/ui";
import {
  createPromotion,
  deactivatePromotion,
  listCategories,
  listPromotions,
  updatePromotion,
} from "@/lib/admin";
import type { Category, Promotion } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

const BLANK = {
  name: "",
  code: "",
  description: "",
  discount_type: "PERCENTAGE",
  discount_value: "",
  starts_at: "",
  ends_at: "",
  minimum_order_value: "",
  usage_limit: "",
  category_ids: [] as number[],
};

export default function AdminPromotionsPage() {
  const [rows, setRows] = useState<Promotion[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({ ...BLANK });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { toast, setToast } = useToast();

  const load = useCallback(() => {
    listPromotions()
      .then((result) => {
        setRows(result);
        setError(null);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load promotions."),
      );
  }, []);

  useEffect(() => {
    load();
    listCategories().then(setCategories).catch(() => setCategories([]));
  }, [load]);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    createPromotion({
      name: form.name,
      code: form.code.trim() || null,
      description: form.description || null,
      discount_type: form.discount_type,
      discount_value: form.discount_value,
      starts_at: form.starts_at ? `${form.starts_at}T00:00:00Z` : null,
      ends_at: form.ends_at ? `${form.ends_at}T23:59:59Z` : null,
      minimum_order_value: form.minimum_order_value || null,
      usage_limit: form.usage_limit ? Number(form.usage_limit) : null,
      category_ids: form.category_ids,
      product_ids: [],
    })
      .then(() => {
        setForm({ ...BLANK });
        load();
        setToast({ kind: "success", text: "Promotion created." });
      })
      .catch((cause: unknown) =>
        setToast({
          kind: "error",
          text: cause instanceof ApiError ? cause.message : "Could not create it.",
        }),
      )
      .finally(() => setBusy(false));
  }

  const set = (key: string, value: unknown) =>
    setForm((current) => ({ ...current, [key]: value as never }));

  return (
    <>
      <PageHeader
        title="Promotions"
        description="A code is entered at checkout. A promotion with no code applies automatically to the storefront."
      />

      {error && <Banner kind="error">{error}</Banner>}

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Panel title="Current promotions">
          {rows.length === 0 ? (
            <EmptyRow>No promotions yet.</EmptyRow>
          ) : (
            <ul className="divide-y divide-line">
              {rows.map((promotion) => (
                <li key={promotion.id} className="px-4 py-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{promotion.name}</span>
                    {promotion.code ? (
                      <code className="border border-line px-1.5 py-0.5 text-xs">
                        {promotion.code}
                      </code>
                    ) : (
                      <span className="text-xs text-ink-subtle">Automatic</span>
                    )}
                    <span className="text-xs text-ink-muted">
                      {promotion.discount_type === "PERCENTAGE"
                        ? `${Number(promotion.discount_value)}% off`
                        : `${Number(promotion.discount_value)} off`}
                    </span>
                    <span
                      className={`ml-auto text-xs ${promotion.active ? "text-success" : "text-ink-subtle"}`}
                    >
                      {promotion.active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-ink-subtle">
                    {promotion.starts_at ? `From ${formatDate(promotion.starts_at)}` : "No start"}
                    {" · "}
                    {promotion.ends_at ? `until ${formatDate(promotion.ends_at)}` : "no end"}
                    {" · "}
                    used {promotion.usage_count}
                    {promotion.usage_limit ? ` of ${promotion.usage_limit}` : " times"}
                  </p>
                  <div className="mt-2 flex gap-3">
                    <button
                      type="button"
                      onClick={() =>
                        updatePromotion(promotion.id, { active: !promotion.active })
                          .then(load)
                          .catch(() =>
                            setToast({ kind: "error", text: "Could not change it." }),
                          )
                      }
                      className="text-xs underline underline-offset-4"
                    >
                      {promotion.active ? "Deactivate" : "Activate"}
                    </button>
                    {promotion.active && (
                      <ConfirmButton
                        label="Archive"
                        question="Deactivate permanently?"
                        onConfirm={() =>
                          deactivatePromotion(promotion.id).then(load).catch(() => undefined)
                        }
                      />
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <p className="border-t border-line px-4 py-3 text-xs text-ink-subtle">
            Promotions are never deleted — past orders reference them.
          </p>
        </Panel>

        <Panel title="New promotion">
          <form onSubmit={submit} className="space-y-4 px-4 py-4">
            <Field label="Name *">
              <input
                required
                value={form.name}
                onChange={(event) => set("name", event.target.value)}
                className="field"
              />
            </Field>
            <Field label="Code" hint="Leave empty to apply automatically">
              <input
                value={form.code}
                onChange={(event) => set("code", event.target.value)}
                className="field"
              />
            </Field>
            <Field label="Type">
              <select
                value={form.discount_type}
                onChange={(event) => set("discount_type", event.target.value)}
                className="field"
              >
                <option value="PERCENTAGE">Percentage</option>
                <option value="FIXED_AMOUNT">Fixed amount</option>
              </select>
            </Field>
            <Field label="Value *">
              <input
                required
                type="number"
                step="0.01"
                min="0.01"
                value={form.discount_value}
                onChange={(event) => set("discount_value", event.target.value)}
                className="field"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Starts">
                <input
                  type="date"
                  value={form.starts_at}
                  onChange={(event) => set("starts_at", event.target.value)}
                  className="field"
                />
              </Field>
              <Field label="Ends">
                <input
                  type="date"
                  value={form.ends_at}
                  onChange={(event) => set("ends_at", event.target.value)}
                  className="field"
                />
              </Field>
            </div>
            <Field label="Minimum order value">
              <input
                type="number"
                step="0.01"
                min="0"
                value={form.minimum_order_value}
                onChange={(event) => set("minimum_order_value", event.target.value)}
                className="field"
              />
            </Field>
            <Field label="Usage limit">
              <input
                type="number"
                min="1"
                value={form.usage_limit}
                onChange={(event) => set("usage_limit", event.target.value)}
                className="field"
              />
            </Field>
            <Field label="Limit to collections" hint="None selected = whole catalogue">
              <div className="flex flex-wrap gap-2 pt-1">
                {categories.map((category) => (
                  <label key={category.id} className="flex items-center gap-1.5 text-sm">
                    <input
                      type="checkbox"
                      checked={form.category_ids.includes(category.id)}
                      onChange={(event) =>
                        set(
                          "category_ids",
                          event.target.checked
                            ? [...form.category_ids, category.id]
                            : form.category_ids.filter((id) => id !== category.id),
                        )
                      }
                    />
                    {category.name}
                  </label>
                ))}
              </div>
            </Field>
            <button type="submit" disabled={busy} className="btn btn-primary w-full">
              {busy ? "Creating…" : "Create promotion"}
            </button>
          </form>
        </Panel>
      </div>

      <Toast toast={toast} />
    </>
  );
}
