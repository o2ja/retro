"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Banner,
  Field,
  PageHeader,
  Panel,
  Toast,
  Toggle,
  useToast,
} from "@/components/admin/ui";
import { listHomepageSections, saveHomepageSection } from "@/lib/admin";
import type { HomepageSection } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

/** The sections the storefront knows how to render. */
const SECTION_TYPES = [
  { value: "HERO", label: "Hero" },
  { value: "FEATURED_PRODUCTS", label: "Featured products" },
  { value: "NEW_ARRIVALS", label: "New arrivals" },
  { value: "CATEGORIES", label: "Collections" },
  { value: "BRAND_STORY", label: "Brand story" },
  { value: "JOURNAL", label: "Journal" },
  { value: "OFFERS", label: "Offers" },
];

type Draft = {
  section_type: string;
  title: string;
  subtitle: string;
  body: string;
  image_url: string;
  cta_label: string;
  cta_url: string;
  visible: boolean;
  sort_order: number;
};

const blank = (type: string): Draft => ({
  section_type: type,
  title: "",
  subtitle: "",
  body: "",
  image_url: "",
  cta_label: "",
  cta_url: "",
  visible: true,
  sort_order: 0,
});

export default function AdminHomepagePage() {
  const [sections, setSections] = useState<HomepageSection[]>([]);
  const [active, setActive] = useState("HERO");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { toast, setToast } = useToast();

  const load = useCallback(() => {
    listHomepageSections()
      .then((result) => {
        setSections(result);
        setError(null);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load the homepage."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // The editor content is derived from the selected tab plus whatever the
  // server returned, with local edits layered on top. No effect, no sync.
  const [edits, setEdits] = useState<Partial<Draft>>({});
  const stored = sections.find((s) => s.section_type === active);
  const draft: Draft = {
    ...(stored
      ? {
          section_type: stored.section_type,
          title: stored.title ?? "",
          subtitle: stored.subtitle ?? "",
          body: stored.body ?? "",
          image_url: stored.image_url ?? "",
          cta_label: stored.cta_label ?? "",
          cta_url: stored.cta_url ?? "",
          visible: stored.visible,
          sort_order: stored.sort_order,
        }
      : blank(active)),
    ...edits,
    section_type: active,
  };

  const set = (key: keyof Draft, value: unknown) =>
    setEdits((current) => ({ ...current, [key]: value as never }));

  function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    saveHomepageSection({
      section_type: draft.section_type,
      title: draft.title || null,
      subtitle: draft.subtitle || null,
      body: draft.body || null,
      image_url: draft.image_url || null,
      cta_label: draft.cta_label || null,
      cta_url: draft.cta_url || null,
      visible: draft.visible,
      sort_order: Number(draft.sort_order) || 0,
    })
      .then(() => {
        setEdits({});
        load();
        setToast({ kind: "success", text: "Saved. The homepage updates within a minute." });
      })
      .catch((cause: unknown) =>
        setToast({
          kind: "error",
          text: cause instanceof ApiError ? cause.message : "Could not save.",
        }),
      )
      .finally(() => setBusy(false));
  }

  return (
    <>
      <PageHeader
        title="Homepage"
        description="What the storefront shows, and in what order. No code changes needed."
      />

      {error && <Banner kind="error">{error}</Banner>}

      <nav className="mb-4 flex flex-wrap gap-2" aria-label="Homepage sections">
        {SECTION_TYPES.map((type) => {
          const configured = sections.some((s) => s.section_type === type.value);
          return (
            <button
              key={type.value}
              type="button"
              onClick={() => {
                setActive(type.value);
                setEdits({});
              }}
              aria-current={active === type.value ? "true" : undefined}
              className={`border px-3 py-1.5 text-xs transition-colors ${
                active === type.value
                  ? "border-ink bg-surface text-ink"
                  : "border-line text-ink-muted hover:border-clay"
              }`}
            >
              {type.label}
              {!configured && <span className="ml-1 text-ink-subtle">·</span>}
            </button>
          );
        })}
      </nav>

      <Panel title={SECTION_TYPES.find((t) => t.value === active)?.label ?? active}>
        <form onSubmit={save} className="grid gap-4 px-4 py-4 sm:grid-cols-2">
          <Field label="Title">
            <input
              value={draft.title}
              onChange={(event) => set("title", event.target.value)}
              className="field"
            />
          </Field>
          <Field label="Eyebrow / subtitle">
            <input
              value={draft.subtitle}
              onChange={(event) => set("subtitle", event.target.value)}
              className="field"
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Body">
              <textarea
                rows={4}
                value={draft.body}
                onChange={(event) => set("body", event.target.value)}
                className="field"
              />
            </Field>
          </div>
          <Field label="Image URL">
            <input
              value={draft.image_url}
              onChange={(event) => set("image_url", event.target.value)}
              placeholder="/products/rolex-submariner-date-kermit.png"
              className="field"
            />
          </Field>
          <Field label="Sort order">
            <input
              type="number"
              value={draft.sort_order}
              onChange={(event) => set("sort_order", event.target.value)}
              className="field"
            />
          </Field>
          <Field label="Button label">
            <input
              value={draft.cta_label}
              onChange={(event) => set("cta_label", event.target.value)}
              className="field"
            />
          </Field>
          <Field label="Button link">
            <input
              value={draft.cta_url}
              onChange={(event) => set("cta_url", event.target.value)}
              placeholder="/shop"
              className="field"
            />
          </Field>
          <div className="sm:col-span-2 flex items-center justify-between border-t border-line pt-4">
            <Toggle
              label="Visible on the homepage"
              checked={draft.visible}
              onChange={(value) => set("visible", value)}
            />
            <button type="submit" disabled={busy} className="btn btn-primary">
              {busy ? "Saving…" : "Save section"}
            </button>
          </div>
        </form>
      </Panel>

      <Toast toast={toast} />
    </>
  );
}
