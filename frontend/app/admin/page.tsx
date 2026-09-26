"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { BarList, StatTile, TrendChart } from "@/components/admin/charts";
import {
  Banner,
  EmptyRow,
  PageHeader,
  Panel,
  StatusBadge,
  formatDate,
  formatMoney,
} from "@/components/admin/ui";
import { getDashboard } from "@/lib/admin";
import type { Dashboard } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

const RANGES = [
  { value: "today", label: "Today" },
  { value: "week", label: "This week" },
  { value: "month", label: "This month" },
  { value: "year", label: "This year" },
  { value: "custom", label: "Custom" },
] as const;

export default function DashboardPage() {
  const [range, setRange] = useState<string>("month");
  const [custom, setCustom] = useState({ start: "", end: "" });
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const params: Record<string, unknown> = { range };
    if (range === "custom") {
      if (!custom.start || !custom.end) return;
      params.start = `${custom.start}T00:00:00Z`;
      params.end = `${custom.end}T23:59:59Z`;
    }
    getDashboard(params)
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((cause: unknown) => {
        setError(
          cause instanceof ApiError ? cause.message : "Could not load the dashboard.",
        );
      });
  }, [range, custom]);

  useEffect(() => {
    load();
  }, [load]);

  const currency = "USD";

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Every figure below is counted from real orders. Nothing is estimated."
      />

      {/* Filters sit in one row above the charts. */}
      <div className="mb-6 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="field-label">Period</span>
          <select
            value={range}
            onChange={(event) => setRange(event.target.value)}
            className="field"
          >
            {RANGES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {range === "custom" && (
          <>
            <label className="text-sm">
              <span className="field-label">From</span>
              <input
                type="date"
                value={custom.start}
                onChange={(event) =>
                  setCustom((c) => ({ ...c, start: event.target.value }))
                }
                className="field"
              />
            </label>
            <label className="text-sm">
              <span className="field-label">To</span>
              <input
                type="date"
                value={custom.end}
                onChange={(event) =>
                  setCustom((c) => ({ ...c, end: event.target.value }))
                }
                className="field"
              />
            </label>
          </>
        )}
      </div>

      {error && <Banner kind="error">{error}</Banner>}

      {!data ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              label="Revenue"
              value={formatMoney(data.kpis.revenue, currency)}
              note="Paid sales only"
              emphasis
            />
            <StatTile label="Sales" value={data.kpis.orders} note="In this period" />
            <StatTile
              label="Average sale"
              value={formatMoney(data.kpis.average_order_value, currency)}
            />
            <StatTile
              label="New customers"
              value={data.kpis.new_customers}
              note={`${data.kpis.customers} in total`}
            />
          </div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Published products" value={data.kpis.products} />
            <StatTile
              label="Out of stock"
              value={data.kpis.out_of_stock}
              note={`${data.kpis.low_stock} low`}
            />
            <StatTile label="Awaiting payment" value={data.kpis.pending_payments} />
            <StatTile label="To deliver" value={data.kpis.pending_orders} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Revenue over time">
              <TrendChart points={data.revenue_series} money currency={currency} />
            </Panel>
            <Panel title="Sales over time">
              <TrendChart points={data.orders_series} />
            </Panel>
            <Panel title="Sales by category">
              <BarList rows={data.sales_by_category} currency={currency} />
            </Panel>
            <Panel title="Sales by brand">
              <BarList rows={data.sales_by_brand} currency={currency} />
            </Panel>
            <Panel title="Best selling products">
              <BarList rows={data.best_selling_products} unit="units" />
            </Panel>
            <Panel title="Customer growth">
              <TrendChart points={data.customer_series} />
            </Panel>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel
              title="Recent orders"
              action={
                <Link href="/admin/orders" className="text-xs text-ink-muted underline">
                  All orders
                </Link>
              }
            >
              {data.recent_orders.length === 0 ? (
                <EmptyRow>No orders yet.</EmptyRow>
              ) : (
                <ul className="divide-y divide-line">
                  {data.recent_orders.map((order) => (
                    <li key={order.id}>
                      <Link
                        href={`/admin/orders/${order.order_number}`}
                        className="flex items-center justify-between gap-3 px-4 py-3 text-sm hover:bg-surface-muted"
                      >
                        <span className="min-w-0">
                          <span className="block truncate">{order.shipping_name}</span>
                          <span className="text-xs text-ink-subtle">
                            {order.order_number} · {formatDate(order.created_at)}
                          </span>
                        </span>
                        <span className="flex shrink-0 items-center gap-2">
                          <StatusBadge status={order.payment_status} kind="payment" />
                          <span className="tabular-nums">
                            {formatMoney(order.total, order.currency)}
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Low stock">
              {data.low_stock_products.length === 0 ? (
                <EmptyRow>
                  Nothing is running low. One-of-a-kind pieces are not counted.
                </EmptyRow>
              ) : (
                <ul className="divide-y divide-line">
                  {data.low_stock_products.map((product) => (
                    <li
                      key={product.id}
                      className="flex items-center justify-between px-4 py-3 text-sm"
                    >
                      <Link
                        href={`/admin/products/${product.id}`}
                        className="min-w-0 truncate hover:underline"
                      >
                        {product.name}
                      </Link>
                      <span className="tabular-nums text-ink-muted">
                        {product.stock_quantity} left
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}
