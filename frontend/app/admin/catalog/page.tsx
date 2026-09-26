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
  Toggle,
  useToast,
} from "@/components/admin/ui";
import {
  createBrand,
  createCategory,
  deleteBrand,
  deleteCategory,
  listBrands,
  listCategories,
  updateBrand,
  updateCategory,
} from "@/lib/admin";
import type { Brand, Category } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

/** Brands and categories share a shape and a screen; one page, two lists. */
export default function AdminCatalogPage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { toast, setToast } = useToast();

  const load = useCallback(() => {
    Promise.all([listBrands(), listCategories()])
      .then(([b, c]) => {
        setBrands(b);
        setCategories(c);
        setError(null);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const report = (cause: unknown, fallback: string) =>
    setToast({
      kind: "error",
      text: cause instanceof ApiError ? cause.message : fallback,
    });

  return (
    <>
      <PageHeader
        title="Brands & collections"
        description="What customers can filter the catalogue by."
      />

      {error && <Banner kind="error">{error}</Banner>}

      <div className="grid gap-6 lg:grid-cols-2">
        <TaxonomyPanel
          title="Makers"
          rows={brands}
          onCreate={(name) =>
            createBrand({ name })
              .then(() => {
                load();
                setToast({ kind: "success", text: "Maker added." });
              })
              .catch((cause) => report(cause, "Could not add the maker."))
          }
          onToggle={(row, active) =>
            updateBrand(row.id, { active }).then(load).catch((cause) => report(cause, "Failed."))
          }
          onDelete={(row) =>
            deleteBrand(row.id)
              .then(() => {
                load();
                setToast({ kind: "success", text: "Maker deleted." });
              })
              .catch((cause) => report(cause, "Could not delete."))
          }
        />

        <TaxonomyPanel
          title="Collections"
          rows={categories}
          onCreate={(name) =>
            createCategory({ name })
              .then(() => {
                load();
                setToast({ kind: "success", text: "Collection added." });
              })
              .catch((cause) => report(cause, "Could not add the collection."))
          }
          onToggle={(row, active) =>
            updateCategory(row.id, { active })
              .then(load)
              .catch((cause) => report(cause, "Failed."))
          }
          onDelete={(row) =>
            deleteCategory(row.id)
              .then(() => {
                load();
                setToast({ kind: "success", text: "Collection deleted." });
              })
              .catch((cause) => report(cause, "Could not delete."))
          }
        />
      </div>

      <Toast toast={toast} />
    </>
  );
}

type Row = { id: number; name: string; active: boolean; product_count: number };

function TaxonomyPanel<T extends Row>({
  title,
  rows,
  onCreate,
  onToggle,
  onDelete,
}: {
  title: string;
  rows: T[];
  onCreate: (name: string) => void;
  onToggle: (row: T, active: boolean) => void;
  onDelete: (row: T) => void;
}) {
  const [name, setName] = useState("");

  return (
    <Panel title={title}>
      <form
        className="flex gap-2 border-b border-line px-4 py-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (!name.trim()) return;
          onCreate(name.trim());
          setName("");
        }}
      >
        <Field label={`New ${title.toLowerCase().replace(/s$/, "")}`}>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="field"
            placeholder="Name"
          />
        </Field>
        <button type="submit" className="btn btn-secondary mt-5 shrink-0 px-4 py-2 text-xs">
          Add
        </button>
      </form>

      {rows.length === 0 ? (
        <EmptyRow>Nothing here yet.</EmptyRow>
      ) : (
        <ul className="divide-y divide-line">
          {rows.map((row) => (
            <li key={row.id} className="flex items-center gap-3 px-4 py-3 text-sm">
              <span className="min-w-0 flex-1 truncate">{row.name}</span>
              <span className="text-xs text-ink-subtle">
                {row.product_count} {row.product_count === 1 ? "watch" : "watches"}
              </span>
              <Toggle
                label="Visible"
                checked={row.active}
                onChange={(value) => onToggle(row, value)}
              />
              {row.product_count === 0 ? (
                <ConfirmButton
                  label="Delete"
                  question="Delete?"
                  onConfirm={() => onDelete(row)}
                />
              ) : (
                <span className="text-xs text-ink-subtle">In use</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
