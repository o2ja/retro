"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import {
  Banner,
  ConfirmButton,
  PageHeader,
  Panel,
  StatusBadge,
  Toast,
  formatDate,
  formatMoney,
  useToast,
} from "@/components/admin/ui";
import { getOrder, recordPayment, refundOrder, setOrderStatus } from "@/lib/admin";
import {
  ORDER_TRANSITIONS,
  PAYMENT_LABELS,
  type OrderDetail,
  type OrderStatus,
  type PaymentMethod,
} from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

const ACTION_LABELS: Partial<Record<OrderStatus, string>> = {
  PROCESSING: "Preparing for delivery",
  SHIPPED: "Mark shipped",
  DELIVERED: "Mark delivered / handed over",
};

const isOffline = (provider: string) => provider in PAYMENT_LABELS;

export default function AdminOrderPage({
  params,
}: {
  params: Promise<{ orderNumber: string }>;
}) {
  const { orderNumber } = use(params);
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const { toast, setToast } = useToast();

  const load = useCallback(() => {
    getOrder(orderNumber)
      .then((result) => {
        setOrder(result);
        setError(null);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load the order."),
      );
  }, [orderNumber]);

  useEffect(() => {
    load();
  }, [load]);

  function move(status: OrderStatus) {
    setBusy(true);
    setOrderStatus(orderNumber, status, note)
      .then((result) => {
        setOrder(result);
        setNote("");
        setToast({ kind: "success", text: `Order moved to ${status.replaceAll("_", " ")}.` });
      })
      .catch((cause: unknown) =>
        setToast({
          kind: "error",
          text: cause instanceof ApiError ? cause.message : "Could not change the status.",
        }),
      )
      .finally(() => setBusy(false));
  }

  function pay() {
    setBusy(true);
    recordPayment(orderNumber, method, note)
      .then((result) => {
        setOrder(result);
        setNote("");
        setToast({ kind: "success", text: "Payment recorded. The sale now counts in revenue." });
      })
      .catch((cause: unknown) =>
        setToast({
          kind: "error",
          text: cause instanceof ApiError ? cause.message : "Could not record the payment.",
        }),
      )
      .finally(() => setBusy(false));
  }

  function refund() {
    setBusy(true);
    refundOrder(orderNumber, note)
      .then((result) => {
        setOrder(result);
        setToast({ kind: "success", text: "Refund issued through the payment provider." });
      })
      .catch((cause: unknown) =>
        setToast({
          kind: "error",
          text: cause instanceof ApiError ? cause.message : "Refund failed.",
        }),
      )
      .finally(() => setBusy(false));
  }

  if (error) return <Banner kind="error">{error}</Banner>;
  if (!order) return <p className="text-sm text-ink-muted">Loading…</p>;

  // Only transitions the server would accept are offered.
  const nextStatuses = ORDER_TRANSITIONS[order.order_status] ?? [];

  return (
    <>
      <Link href="/admin/orders" className="text-sm text-ink-muted hover:text-ink">
        ← Sales
      </Link>

      <PageHeader
        title={order.order_number}
        description={`Placed ${formatDate(order.created_at)}`}
        action={
          <span className="flex gap-2">
            <StatusBadge status={order.payment_status} kind="payment" />
            <StatusBadge status={order.order_status} kind="order" />
          </span>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <Panel title="Items">
            <ul className="divide-y divide-line">
              {order.items.map((item) => (
                <li key={item.id} className="flex justify-between gap-4 px-4 py-3 text-sm">
                  <span className="min-w-0">
                    <span className="block truncate">{item.product_name_snapshot}</span>
                    <span className="text-xs text-ink-subtle">
                      {item.brand_name_snapshot ? `${item.brand_name_snapshot} · ` : ""}
                      {item.sku_snapshot} · ×{item.quantity}
                    </span>
                  </span>
                  <span className="shrink-0 tabular-nums">
                    {formatMoney(item.line_total, order.currency)}
                  </span>
                </li>
              ))}
            </ul>
            <dl className="space-y-1.5 border-t border-line px-4 py-4 text-sm">
              <Row label="Subtotal" value={formatMoney(order.subtotal, order.currency)} />
              {Number(order.discount_total) > 0 && (
                <Row
                  label={`Discount${order.promotion_code_snapshot ? ` (${order.promotion_code_snapshot})` : ""}`}
                  value={`−${formatMoney(order.discount_total, order.currency)}`}
                />
              )}
              <Row label="Shipping" value={formatMoney(order.shipping_total, order.currency)} />
              <div className="flex justify-between border-t border-line pt-2 text-base">
                <dt>Total</dt>
                <dd className="font-display tabular-nums">
                  {formatMoney(order.total, order.currency)}
                </dd>
              </div>
            </dl>
          </Panel>

          <Panel title="Timeline">
            {order.status_history.length === 0 ? (
              <p className="px-4 py-6 text-sm text-ink-subtle">
                No status changes yet.
              </p>
            ) : (
              <ol className="divide-y divide-line">
                {order.status_history.map((entry, index) => (
                  <li key={index} className="px-4 py-3 text-sm">
                    <span className="flex items-center gap-2">
                      {entry.from_status && (
                        <>
                          <span className="text-ink-subtle">
                            {entry.from_status.replaceAll("_", " ")}
                          </span>
                          <span aria-hidden>→</span>
                        </>
                      )}
                      <StatusBadge status={entry.to_status} kind="order" />
                      <span className="ml-auto text-xs text-ink-subtle">
                        {formatDate(entry.created_at)}
                      </span>
                    </span>
                    {entry.note && (
                      <p className="mt-1 text-xs text-ink-muted">{entry.note}</p>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </Panel>

          <Panel title="Payments">
            {order.payments.length === 0 ? (
              <p className="px-4 py-6 text-sm text-ink-subtle">
                No payment has been started.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {order.payments.map((payment) => (
                  <li
                    key={payment.id}
                    className="flex items-center justify-between px-4 py-3 text-sm"
                  >
                    <span>
                      <span className="block">
                        {PAYMENT_LABELS[payment.provider as PaymentMethod] ?? payment.provider}
                      </span>
                      {payment.failure_reason && (
                        <span className="text-xs text-danger">
                          {payment.failure_reason}
                        </span>
                      )}
                    </span>
                    <span className="flex items-center gap-3">
                      <StatusBadge status={payment.status} kind="payment" />
                      <span className="tabular-nums">
                        {formatMoney(payment.amount, payment.currency)}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Customer">
            <div className="space-y-1 px-4 py-4 text-sm">
              <p>{order.shipping_name}</p>
              <p className="text-ink-muted">{order.shipping_email}</p>
              {order.shipping_phone && (
                <p className="text-ink-muted">{order.shipping_phone}</p>
              )}
              {order.customer_id && (
                <Link
                  href={`/admin/customers?id=${order.customer_id}`}
                  className="inline-block pt-2 text-xs underline"
                >
                  Customer record
                </Link>
              )}
            </div>
          </Panel>

          {(order.shipping_address || order.customer_note) && (
            <Panel title={order.shipping_address ? "Shipping" : "Note"}>
              {order.shipping_address && (
                <address className="space-y-0.5 px-4 py-4 text-sm not-italic text-ink-muted">
                  <p>{order.shipping_address}</p>
                  <p>
                    {order.shipping_city}
                    {order.shipping_postal_code ? `, ${order.shipping_postal_code}` : ""}
                  </p>
                  <p>{order.shipping_country}</p>
                </address>
              )}
              {order.customer_note && (
                <p className={`px-4 py-3 text-sm ${order.shipping_address ? "border-t border-line" : ""}`}>
                  {order.customer_note}
                </p>
              )}
            </Panel>
          )}

          <Panel title="Actions">
            <div className="space-y-3 px-4 py-4">
              <label className="block">
                <span className="field-label">Note (optional)</span>
                <input
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  className="field"
                  placeholder="Recorded in the timeline"
                />
              </label>

              {order.order_status === "PENDING_PAYMENT" && (
                <div className="space-y-2 rounded-md border border-line p-3">
                  <p className="text-sm">Awaiting payment of {formatMoney(order.total, order.currency)}</p>
                  <div className="flex gap-2">
                    <select
                      value={method}
                      onChange={(event) => setMethod(event.target.value as PaymentMethod)}
                      className="field !py-1.5 text-sm"
                      aria-label="Payment method"
                    >
                      {(Object.keys(PAYMENT_LABELS) as PaymentMethod[]).map((key) => (
                        <option key={key} value={key}>
                          {PAYMENT_LABELS[key]}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={pay}
                      className="btn btn-primary !min-h-0 shrink-0 !px-4 !py-1.5 text-sm"
                    >
                      Record payment
                    </button>
                  </div>
                </div>
              )}

              {nextStatuses.length === 0 ? (
                <p className="text-xs text-ink-subtle">
                  This order is final; no further status changes are possible.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {nextStatuses.map((status) =>
                    status === "CANCELLED" || status === "REFUNDED" ? (
                      <ConfirmButton
                        key={status}
                        label={status === "CANCELLED" ? "Cancel order" : "Mark refunded"}
                        question={`${status === "CANCELLED" ? "Cancel" : "Refund"} and return stock?`}
                        onConfirm={() => move(status)}
                      />
                    ) : (
                      <button
                        key={status}
                        type="button"
                        disabled={busy}
                        onClick={() => move(status)}
                        className="btn btn-secondary px-3 py-1.5 text-xs"
                      >
                        {ACTION_LABELS[status] ?? status.replaceAll("_", " ")}
                      </button>
                    ),
                  )}
                </div>
              )}

              {order.payment_status === "PAID" && !order.payments.some((p) => isOffline(p.provider)) && (
                <div className="border-t border-line pt-3">
                  <ConfirmButton
                    label="Refund through the payment provider"
                    question="Refund the full amount?"
                    onConfirm={refund}
                  />
                  <p className="mt-1 text-xs text-ink-subtle">
                    The order is only marked refunded once the provider confirms it.
                  </p>
                </div>
              )}
            </div>
          </Panel>
        </div>
      </div>

      <Toast toast={toast} />
    </>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}
