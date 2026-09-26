"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Banner, EmptyRow, PageHeader, Pager, Panel, Toast, formatDate, useToast } from "@/components/admin/ui";
import { listInquiries, listProducts, recordSale, setInquiryStatus } from "@/lib/admin";
import {
  PAYMENT_LABELS,
  type AdminProduct,
  type Inquiry,
  type InquiryStatus,
  type Page,
  type PaymentMethod,
} from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

const TABS: { value: InquiryStatus | ""; label: string }[] = [
  { value: "NEW", label: "New" },
  { value: "CONTACTED", label: "Contacted" },
  { value: "SOLD", label: "Sold" },
  { value: "CLOSED", label: "Closed" },
  { value: "", label: "All" },
];

/** Statuses picked by hand. SOLD only comes from recording a sale. */
const MANUAL: { value: InquiryStatus; label: string }[] = [
  { value: "NEW", label: "New" },
  { value: "CONTACTED", label: "Contacted" },
  { value: "CLOSED", label: "Closed, no sale" },
];

const message = (cause: unknown, fallback: string) => (cause instanceof ApiError ? cause.message : fallback);

export default function AdminInquiriesPage() {
  const [status, setStatus] = useState<InquiryStatus | "">("NEW");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Inquiry> | null>(null);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [selling, setSelling] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { toast, setToast } = useToast();

  const load = useCallback(() => {
    listInquiries({ status: status || undefined, page, page_size: 20 })
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((cause: unknown) => setError(message(cause, "Could not load requests.")));
  }, [status, page]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    listProducts({ page_size: 100 })
      .then((result) => setProducts(result.items))
      .catch(() => setProducts([]));
  }, []);

  function mark(inquiry: Inquiry, next: InquiryStatus) {
    setInquiryStatus(inquiry.id, next)
      .then(load)
      .catch((cause: unknown) => setToast({ kind: "error", text: message(cause, "Could not update the request.") }));
  }

  return (
    <>
      <PageHeader
        title="Requests"
        description="Customers asking about a watch. Call them back, mark them contacted, then record the sale or close the request."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((option) => (
          <button
            key={option.value || "all"}
            type="button"
            onClick={() => {
              setPage(1);
              setSelling(null);
              setStatus(option.value);
            }}
            aria-pressed={status === option.value}
            className={`rounded-full border px-4 py-1.5 text-xs ${
              status === option.value ? "border-ink bg-ink text-ink-inverse" : "border-line hover:border-ink-subtle"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {error && <Banner kind="error">{error}</Banner>}

      <Panel>
        {!data ? (
          <EmptyRow>Loading…</EmptyRow>
        ) : data.items.length === 0 ? (
          <EmptyRow>No requests here.</EmptyRow>
        ) : (
          <>
            <ul className="divide-y divide-line">
              {data.items.map((inquiry) => (
                <li key={inquiry.id} className="px-4 py-4 text-sm">
                  <div className="grid gap-3 md:grid-cols-[1fr_1.4fr_auto]">
                    <div className="min-w-0">
                      <p className="text-base">{inquiry.full_name}</p>
                      <a href={`mailto:${inquiry.email}`} className="block truncate text-ink-muted hover:underline">
                        {inquiry.email}
                      </a>
                      <a
                        href={`tel:${inquiry.phone.replace(/[^\d+]/g, "")}`}
                        className="block text-ink-muted hover:underline"
                      >
                        {inquiry.phone}
                      </a>
                    </div>
                    <div className="min-w-0">
                      <p>{inquiry.product_name_snapshot ?? "General request"}</p>
                      {inquiry.message && <p className="mt-1 whitespace-pre-line text-ink-muted">{inquiry.message}</p>}
                      <p className="mt-1 text-xs text-ink-subtle">{formatDate(inquiry.created_at)}</p>
                    </div>
                    <div className="flex flex-wrap items-start gap-2 md:justify-end">
                      {inquiry.status === "SOLD" ? (
                        <Link
                          href={`/admin/orders/${inquiry.order_number}`}
                          className="rounded-full bg-success/10 px-3 py-1.5 text-xs text-success hover:underline"
                        >
                          Sold · {inquiry.order_number}
                        </Link>
                      ) : (
                        <>
                          <select
                            value={inquiry.status}
                            onChange={(event) => mark(inquiry, event.target.value as InquiryStatus)}
                            className="field h-fit w-40 !py-1.5 text-sm"
                            aria-label={`Status of ${inquiry.full_name}'s request`}
                          >
                            {MANUAL.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                          {inquiry.status !== "CLOSED" && (
                            <button
                              type="button"
                              onClick={() => setSelling(selling === inquiry.id ? null : inquiry.id)}
                              aria-expanded={selling === inquiry.id}
                              className="btn btn-primary !min-h-0 !px-4 !py-1.5 text-sm"
                            >
                              Record sale
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  {selling === inquiry.id && (
                    <SaleForm
                      inquiry={inquiry}
                      products={products}
                      onCancel={() => setSelling(null)}
                      onDone={(result) => {
                        setSelling(null);
                        setToast({ kind: "success", text: `Sale recorded as ${result.order_number}.` });
                        load();
                      }}
                      onError={(text) => setToast({ kind: "error", text })}
                    />
                  )}
                </li>
              ))}
            </ul>
            <Pager page={data.page} total={data.total} pageSize={data.page_size} onPage={setPage} />
          </>
        )}
      </Panel>

      <Toast toast={toast} />
    </>
  );
}

function SaleForm({
  inquiry,
  products,
  onCancel,
  onDone,
  onError,
}: {
  inquiry: Inquiry;
  products: AdminProduct[];
  onCancel: () => void;
  onDone: (result: Inquiry) => void;
  onError: (text: string) => void;
}) {
  const inStock = products.filter((product) => product.stock_quantity > 0 || product.id === inquiry.product_id);
  const [productId, setProductId] = useState<number | "">(inquiry.product_id ?? "");
  const product = products.find((item) => item.id === productId);
  const [price, setPrice] = useState(product?.price ?? "");
  const [payment, setPayment] = useState<PaymentMethod | "">("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!productId) return onError("Choose which watch was sold.");
    setBusy(true);
    recordSale(inquiry.id, {
      product_id: productId,
      price,
      payment: payment ? { method: payment } : null,
      note: note || null,
    })
      .then(onDone)
      .catch((cause: unknown) => onError(message(cause, "Could not record the sale.")))
      .finally(() => setBusy(false));
  }

  return (
    <form onSubmit={submit} className="mt-4 grid gap-4 rounded-md border border-line bg-surface-muted p-4 sm:grid-cols-2 lg:grid-cols-4">
      <label className="block">
        <span className="field-label">Watch sold</span>
        <select
          required
          value={productId}
          onChange={(event) => {
            const id = Number(event.target.value) || "";
            setProductId(id);
            setPrice(products.find((item) => item.id === id)?.price ?? "");
          }}
          className="field"
        >
          <option value="">Choose a watch</option>
          {inStock.map((item) => (
            <option key={item.id} value={item.id}>
              {item.brand ? `${item.brand.name} ` : ""}
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="field-label">Agreed price ({product?.currency ?? "USD"})</span>
        <input
          required
          inputMode="decimal"
          pattern="\d+(\.\d{1,2})?"
          value={price}
          onChange={(event) => setPrice(event.target.value)}
          className="field tabular-nums"
          placeholder="e.g. 18500"
        />
      </label>
      <label className="block">
        <span className="field-label">Payment</span>
        <select value={payment} onChange={(event) => setPayment(event.target.value as PaymentMethod | "")} className="field">
          <option value="">Not paid yet</option>
          {(Object.keys(PAYMENT_LABELS) as PaymentMethod[]).map((method) => (
            <option key={method} value={method}>
              Paid: {PAYMENT_LABELS[method]}
            </option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="field-label">Note (optional)</span>
        <input value={note} onChange={(event) => setNote(event.target.value)} className="field" placeholder="Delivery, strap change…" />
      </label>
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2 lg:col-span-4">
        <button type="submit" disabled={busy} className="btn btn-primary !min-h-0 !py-2 text-sm">
          {busy ? "Recording…" : "Record sale"}
        </button>
        <button type="button" onClick={onCancel} className="text-sm text-ink-muted hover:text-ink">
          Cancel
        </button>
        <p className="text-xs text-ink-subtle">
          Creates the order in Sales and marks the watch as sold on the website.
        </p>
      </div>
    </form>
  );
}
