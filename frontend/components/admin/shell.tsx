"use client";

/**
 * Admin shell and auth gate.
 *
 * The gate is convenience only — it decides what to *render*. Authorisation is
 * enforced by the API: every admin endpoint requires the signed session cookie,
 * so a forged client state gets 401s and nothing else.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { adminLogout, adminMe } from "@/lib/admin";

const NAV = [
  { href: "/admin", label: "Dashboard", exact: true },
  { href: "/admin/inquiries", label: "Requests" },
  { href: "/admin/orders", label: "Sales" },
  { href: "/admin/products", label: "Products" },
  { href: "/admin/catalog", label: "Brands & categories" },
  { href: "/admin/customers", label: "Customers" },
  { href: "/admin/homepage", label: "Homepage" },
  { href: "/admin/settings", label: "Settings" },
];

type Admin = { id: number; email: string; full_name: string | null };

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [state, setState] = useState<
    { status: "checking" } | { status: "in"; admin: Admin } | { status: "out" }
  >({ status: "checking" });
  const [menuOpen, setMenuOpen] = useState(false);

  const isLoginPage = pathname === "/admin/login";

  useEffect(() => {
    let cancelled = false;
    adminMe()
      .then((admin) => {
        if (!cancelled) setState({ status: "in", admin });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "out" });
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const signOut = useCallback(async () => {
    await adminLogout().catch(() => undefined);
    router.push("/admin/login");
  }, [router]);

  if (isLoginPage) return <>{children}</>;

  if (state.status === "checking") {
    return (
      <div className="grid min-h-[60vh] place-items-center text-sm text-ink-muted">
        Checking your session…
      </div>
    );
  }

  if (state.status === "out") {
    return (
      <div className="grid min-h-[60vh] place-items-center px-6 text-center">
        <div>
          <h1 className="text-2xl">Please sign in</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Your session has ended or you are not signed in.
          </p>
          <Link href="/admin/login" className="btn btn-primary mt-6">
            Go to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas lg:grid lg:grid-cols-[15rem_1fr]">
      <aside className="border-b border-line bg-surface lg:min-h-screen lg:border-r lg:border-b-0">
        <div className="flex items-center justify-between px-5 py-4 lg:block">
          <div>
            <p className="font-display text-lg tracking-[0.12em] uppercase">
              Retro Watches
            </p>
            <p className="eyebrow mt-0.5">Administration</p>
          </div>
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            className="p-2 text-sm text-ink-muted lg:hidden"
          >
            {menuOpen ? "Close" : "Menu"}
          </button>
        </div>

        <nav
          aria-label="Admin"
          className={`px-3 pb-4 lg:block ${menuOpen ? "block" : "hidden"}`}
        >
          <ul className="space-y-0.5">
            {NAV.map((item) => {
              const active = item.exact
                ? pathname === item.href
                : pathname.startsWith(item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={`block px-3 py-2 text-sm transition-colors ${
                      active
                        ? "bg-surface-muted text-ink"
                        : "text-ink-muted hover:text-ink"
                    }`}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>

          <div className="mt-6 border-t border-line px-3 pt-4 text-xs text-ink-subtle">
            <p className="truncate">{state.admin.email}</p>
            <div className="mt-2 flex gap-3">
              <button type="button" onClick={signOut} className="underline">
                Sign out
              </button>
              <Link href="/" className="underline">
                View store
              </Link>
            </div>
          </div>
        </nav>
      </aside>

      <main className="px-5 py-8 lg:px-8">{children}</main>
    </div>
  );
}
