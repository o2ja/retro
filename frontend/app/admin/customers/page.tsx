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
import { getCustomer, listCustomers } from "@/lib/admin";
import type { Customer, CustomerDetail, Page } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

export default function AdminCustomersPage() {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Customer> | null>(null);
  const [selected, setSelected] = useState<CustomerDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    listCustomers({ q: query || undefined, page, page_size: 20 })
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load customers."),
      );
  }, [query, page]);

  useEffect(() => {
    load();
  }, [load]);

  function open(id: number) {
    getCustomer(id)
      .then(setSelected)
      .catch(() => setSelected(null));
  }

  return (
    <>
      <PageHeader
        title="Customers"
        description="Created by checkout. Payment details are never stored."
      />

      <input
        type="search"
        placeholder="Name, email or phone"
        value={query}
        onChange={(event) => {
          setPage(1);
          setQuery(event.target.value);
        }}
        className="field mb-4 max-w-xs"
      />

      {error && <Banner kind="error">{error}</Banner>}

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Panel>
          {!data ? (
            <EmptyRow>Loading…</EmptyRow>
          ) : data.items.length === 0 ? (
            <EmptyRow>
              No customers yet. One is created the first time somebody checks out.
            </EmptyRow>
          ) : (
            <>
              <ul className="divide-y divide-line">
                {data.items.map((customer) => (
                  <li key={customer.id}>
                    <button
                      type="button"
                      onClick={() => open(customer.id)}
                      className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm hover:bg-surface-muted"
                    >
                      <span className="min-w-0">
                        <span className="block truncate">
                          {customer.full_name ?? "Unnamed"}
                        </span>
                        <span className="block truncate text-xs text-ink-subtle">
                          {customer.email}
                        </span>
                      </span>
                      <span className="shrink-0 text-xs text-ink-subtle">
                        {customer.last_order_at
                          ? `Last order ${formatDate(customer.last_order_at)}`
                          : "No orders"}
                      </span>
                    </button>
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

        <Panel title="Customer">
          {!selected ? (
            <EmptyRow>Select a customer to see their orders.</EmptyRow>
          ) : (
            <div className="px-4 py-4 text-sm">
              <p className="text-base">{selected.full_name ?? "Unnamed"}</p>
              <p className="text-ink-muted">{selected.email}</p>
              {selected.phone && <p className="text-ink-muted">{selected.phone}</p>}

              <dl className="mt-4 grid grid-cols-2 gap-3 border-y border-line py-3">
                <div>
                  <dt className="eyebrow">Orders</dt>
                  <dd className="tabular-nums">{selected.order_count}</dd>
                </div>
                <div>
                  <dt className="eyebrow">Total spent</dt>
                  <dd className="tabular-nums">{formatMoney(selected.total_spent)}</dd>
                </div>
              </dl>
              <p className="mt-1 text-xs text-ink-subtle">
                Spend counts verified-paid orders only.
              </p>

              <ul className="mt-4 space-y-2">
                {selected.orders.map((order) => (
                  <li key={order.id}>
                    <Link
                      href={`/admin/orders/${order.order_number}`}
                      className="flex items-center justify-between gap-2 hover:underline"
                    >
                      <span className="font-mono text-xs">{order.order_number}</span>
                      <StatusBadge status={order.payment_status} kind="payment" />
                      <span className="tabular-nums">
                        {formatMoney(order.total, order.currency)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
