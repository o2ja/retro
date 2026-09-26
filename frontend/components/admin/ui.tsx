"use client";

/**
 * Admin UI kit.
 *
 * Operational, not editorial: denser than the storefront, same tokens. Grouped
 * in one file because each piece is small and they are always used together.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import type { OrderStatus, PaymentStatus } from "@/lib/admin-types";

export function formatMoney(amount: string | null | undefined, currency = "USD") {
  if (amount === null || amount === undefined) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(amount));
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/* -------------------------------------------------------------------------- */
/* Feedback                                                                   */
/* -------------------------------------------------------------------------- */

export function Banner({
  kind = "info",
  children,
}: {
  kind?: "info" | "error" | "success";
  children: React.ReactNode;
}) {
  const styles = {
    info: "border-line bg-surface-muted text-ink",
    error: "border-danger/40 bg-danger/5 text-danger",
    success: "border-success/40 bg-success/5 text-success",
  }[kind];
  return (
    <p
      role={kind === "error" ? "alert" : "status"}
      className={`mb-4 border px-4 py-3 text-sm ${styles}`}
    >
      {children}
    </p>
  );
}

export type ToastState = { kind: "success" | "error"; text: string } | null;

/** Auto-clearing toast for save confirmations. */
export function useToast() {
  const [toast, setToast] = useState<ToastState>(null);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);
  return { toast, setToast };
}

export function Toast({ toast }: { toast: ToastState }) {
  if (!toast) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-6 left-1/2 z-50 -translate-x-1/2 border px-5 py-3 text-sm shadow-lg ${
        toast.kind === "error"
          ? "border-danger/40 bg-surface text-danger"
          : "border-line bg-surface text-ink"
      }`}
    >
      {toast.text}
    </div>
  );
}

export function EmptyRow({ children }: { children: React.ReactNode }) {
  return <p className="px-4 py-12 text-center text-sm text-ink-subtle">{children}</p>;
}

export function ConfirmButton({
  onConfirm,
  label,
  question,
  className = "",
}: {
  onConfirm: () => void;
  label: string;
  question: string;
  className?: string;
}) {
  const [asking, setAsking] = useState(false);
  // Inline confirmation rather than window.confirm: no blocking dialog.
  if (!asking) {
    return (
      <button
        type="button"
        onClick={() => setAsking(true)}
        className={`text-xs text-danger underline underline-offset-4 ${className}`}
      >
        {label}
      </button>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 text-xs">
      <span>{question}</span>
      <button
        type="button"
        onClick={() => {
          setAsking(false);
          onConfirm();
        }}
        className="text-danger underline underline-offset-4"
      >
        Yes
      </button>
      <button type="button" onClick={() => setAsking(false)} className="text-ink-muted">
        No
      </button>
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Status                                                                     */
/* -------------------------------------------------------------------------- */

const ORDER_TONE: Record<OrderStatus, string> = {
  PENDING_PAYMENT: "border-clay text-bark",
  PAYMENT_CONFIRMED: "border-success/50 text-success",
  PROCESSING: "border-clay text-bark",
  SHIPPED: "border-clay text-bark",
  DELIVERED: "border-success/50 text-success",
  CANCELLED: "border-line-strong text-ink-subtle",
  REFUNDED: "border-danger/40 text-danger",
};

const PAYMENT_TONE: Record<PaymentStatus, string> = {
  PENDING: "border-clay text-bark",
  AUTHORIZED: "border-clay text-bark",
  PAID: "border-success/50 text-success",
  FAILED: "border-danger/40 text-danger",
  CANCELLED: "border-line-strong text-ink-subtle",
  REFUNDED: "border-danger/40 text-danger",
};

/** Status is a word inside a border, never colour alone. */
export function StatusBadge({
  status,
  kind,
}: {
  status: OrderStatus | PaymentStatus | string;
  kind: "order" | "payment";
}) {
  const tone =
    kind === "order"
      ? (ORDER_TONE[status as OrderStatus] ?? "border-line text-ink-muted")
      : (PAYMENT_TONE[status as PaymentStatus] ?? "border-line text-ink-muted");
  return (
    <span
      className={`inline-block border px-2 py-0.5 text-[0.625rem] tracking-[0.1em] whitespace-nowrap uppercase ${tone}`}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Layout pieces                                                              */
/* -------------------------------------------------------------------------- */

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-muted">{description}</p>}
      </div>
      {action}
    </header>
  );
}

export function Panel({
  title,
  action,
  children,
}: {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="border border-line bg-surface">
      {(title || action) && (
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          {title && <h2 className="text-sm tracking-[0.08em] uppercase">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-subtle">{hint}</span>}
    </label>
  );
}

export function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}

export function Pager({
  page,
  total,
  pageSize,
  onPage,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(Math.ceil(total / pageSize), 1);
  if (pages <= 1) return null;
  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-between border-t border-line px-4 py-3 text-sm"
    >
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
        className="text-ink-muted disabled:opacity-40"
      >
        Previous
      </button>
      <span className="text-ink-subtle">
        Page {page} of {pages} · {total} total
      </span>
      <button
        type="button"
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
        className="text-ink-muted disabled:opacity-40"
      >
        Next
      </button>
    </nav>
  );
}

export function LinkButton({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className="btn btn-secondary px-4 py-2 text-xs">
      {children}
    </Link>
  );
}
