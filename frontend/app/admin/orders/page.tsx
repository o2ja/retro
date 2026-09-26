"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  Banner,
  EmptyRow,
  PageHeader,
  Pager,
  Panel,
  StatusBadge,
  formatDate,
  formatMoney,
} from "@/components/admin/ui";
import { listOrders } from "@/lib/admin";
import type { Order, Page } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

const ORDER_STATUSES = [
  "PENDING_PAYMENT",
  "PAYMENT_CONFIRMED",
  "PROCESSING",
  "SHIPPED",
  "DELIVERED",
  "CANCELLED",
  "REFUNDED",
];
const PAYMENT_STATUSES = [
  "PENDING",
  "AUTHORIZED",
  "PAID",
  "FAILED",
  "CANCELLED",
  "REFUNDED",
];

export default function AdminOrdersPage() {
  const [query, setQuery] = useState("");
  const [orderStatus, setOrderStatus] = useState("");
  const [paymentStatus, setPaymentStatus] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Order> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    listOrders({
      q: query || undefined,
      order_status: orderStatus || undefined,
      payment_status: paymentStatus || undefined,
      page,
      page_size: 20,
    })
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load orders."),
      );
  }, [query, orderStatus, paymentStatus, page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Sales"
        description="Every sale recorded from a request. Open one to record the payment or mark it delivered."
      />

      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Order number, name or email"
          value={query}
          onChange={(event) => {
            setPage(1);
            setQuery(event.target.value);
          }}
          className="field max-w-xs"
        />
        <select
          value={orderStatus}
          onChange={(event) => {
            setPage(1);
            setOrderStatus(event.target.value);
          }}
          className="field max-w-[12rem]"
        >
          <option value="">Any order status</option>
          {ORDER_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status.replaceAll("_", " ")}
            </option>
          ))}
        </select>
        <select
          value={paymentStatus}
          onChange={(event) => {
            setPage(1);
            setPaymentStatus(event.target.value);
          }}
          className="field max-w-[12rem]"
        >
          <option value="">Any payment status</option>
          {PAYMENT_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
      </div>

      {error && <Banner kind="error">{error}</Banner>}

      <Panel>
        {!data ? (
          <EmptyRow>Loading…</EmptyRow>
        ) : data.items.length === 0 ? (
          <EmptyRow>No orders match these filters.</EmptyRow>
        ) : (
          <>
            {/* A table on desktop, stacked cards on mobile - not a squeezed table. */}
            <ul className="divide-y divide-line">
              {data.items.map((order) => (
                <li key={order.id}>
                  <Link
                    href={`/admin/orders/${order.order_number}`}
                    className="grid gap-2 px-4 py-4 text-sm hover:bg-surface-muted sm:grid-cols-[10rem_1fr_auto_auto_auto] sm:items-center sm:gap-4"
                  >
                    <span className="font-mono text-xs">{order.order_number}</span>
                    <span className="min-w-0">
                      <span className="block truncate">{order.shipping_name}</span>
                      <span className="block truncate text-xs text-ink-subtle">
                        {order.shipping_email}
                      </span>
                    </span>
                    <span className="text-xs text-ink-subtle">
                      {formatDate(order.created_at)}
                    </span>
                    <span className="flex gap-2">
                      <StatusBadge status={order.payment_status} kind="payment" />
                      <StatusBadge status={order.order_status} kind="order" />
                    </span>
                    <span className="text-right tabular-nums">
                      {formatMoney(order.total, order.currency)}
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
