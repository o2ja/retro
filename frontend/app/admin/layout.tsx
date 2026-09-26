import type { Metadata } from "next";

import { AdminShell } from "@/components/admin/shell";

/** The dashboard is private; it must never be indexed. */
export const metadata: Metadata = {
  title: { default: "Dashboard", template: "%s · Retro Watches admin" },
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <div className="admin-area min-h-screen">
      <AdminShell>{children}</AdminShell>
    </div>
  );
}
