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
  useToast,
} from "@/components/admin/ui";
import {
  deleteSocialLink,
  getAdminSettings,
  listSocialLinks,
  saveSocialLink,
  updateAdminSettings,
} from "@/lib/admin";
import type { SiteSettings, SocialLink } from "@/lib/admin-types";
import { ApiError } from "@/lib/api";

const TEXT_FIELDS: { key: keyof SiteSettings; label: string; hint?: string }[] = [
  { key: "brand_name", label: "Brand name" },
  { key: "owner_name", label: "Owner" },
  { key: "tagline", label: "Tagline" },
  { key: "contact_email", label: "Contact email" },
  { key: "contact_phone", label: "Contact phone" },
  { key: "address", label: "Address" },
  { key: "currency", label: "Currency", hint: "Three-letter code, e.g. USD" },
  { key: "logo_url", label: "Logo URL" },
  { key: "favicon_url", label: "Favicon URL" },
  { key: "seo_title", label: "SEO title" },
];

const LONG_FIELDS: { key: keyof SiteSettings; label: string }[] = [
  { key: "seo_description", label: "SEO description" },
  { key: "shipping_information", label: "Shipping information" },
  { key: "return_policy", label: "Returns policy" },
  { key: "warranty_information", label: "Warranty information" },
];

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [links, setLinks] = useState<SocialLink[]>([]);
  const [newLink, setNewLink] = useState({ platform: "", label: "", url: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { toast, setToast } = useToast();

  const load = useCallback(() => {
    Promise.all([getAdminSettings(), listSocialLinks()])
      .then(([s, l]) => {
        setSettings(
          Object.fromEntries(Object.entries(s).map(([k, v]) => [k, v ?? ""])) as Record<
            string,
            string
          >,
        );
        setLinks(l);
        setError(null);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof ApiError ? cause.message : "Could not load settings."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const body = Object.fromEntries(
      [...TEXT_FIELDS, ...LONG_FIELDS].map(({ key }) => [
        key,
        settings[key as string] || null,
      ]),
    );
    updateAdminSettings(body)
      .then(() => {
        load();
        setToast({ kind: "success", text: "Settings saved." });
      })
      .catch((cause: unknown) =>
        setToast({
          kind: "error",
          text: cause instanceof ApiError ? cause.message : "Could not save.",
        }),
      )
      .finally(() => setBusy(false));
  }

  const bind = (key: string) => ({
    value: settings[key] ?? "",
    onChange: (
      event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
    ) => setSettings((current) => ({ ...current, [key]: event.target.value })),
    className: "field",
  });

  return (
    <>
      <PageHeader
        title="Settings"
        description="Brand and contact details the storefront reads. Payment keys are never stored here."
      />

      {error && <Banner kind="error">{error}</Banner>}

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <form onSubmit={save} className="space-y-6">
          <Panel title="Brand & contact">
            <div className="grid gap-4 px-4 py-4 sm:grid-cols-2">
              {TEXT_FIELDS.map(({ key, label, hint }) => (
                <Field key={key} label={label} hint={hint}>
                  <input {...bind(key as string)} />
                </Field>
              ))}
            </div>
          </Panel>

          <Panel title="Policies & SEO">
            <div className="grid gap-4 px-4 py-4">
              {LONG_FIELDS.map(({ key, label }) => (
                <Field key={key} label={label}>
                  <textarea rows={3} {...bind(key as string)} />
                </Field>
              ))}
            </div>
          </Panel>

          <button type="submit" disabled={busy} className="btn btn-primary">
            {busy ? "Saving…" : "Save settings"}
          </button>
        </form>

        <div className="space-y-6">
          <Panel title="Social links">
            {links.length === 0 ? (
              <EmptyRow>No links yet.</EmptyRow>
            ) : (
              <ul className="divide-y divide-line">
                {links.map((link) => (
                  <li
                    key={link.id}
                    className="flex items-center gap-3 px-4 py-3 text-sm"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block">{link.platform}</span>
                      <span className="block truncate text-xs text-ink-subtle">
                        {link.url}
                      </span>
                    </span>
                    <ConfirmButton
                      label="Remove"
                      question="Remove?"
                      onConfirm={() =>
                        deleteSocialLink(link.id).then(load).catch(() => undefined)
                      }
                    />
                  </li>
                ))}
              </ul>
            )}

            <form
              className="space-y-3 border-t border-line px-4 py-4"
              onSubmit={(event) => {
                event.preventDefault();
                saveSocialLink({
                  platform: newLink.platform,
                  label: newLink.label || null,
                  url: newLink.url,
                  active: true,
                  sort_order: links.length,
                })
                  .then(() => {
                    setNewLink({ platform: "", label: "", url: "" });
                    load();
                    setToast({ kind: "success", text: "Link saved." });
                  })
                  .catch(() =>
                    setToast({ kind: "error", text: "Could not save the link." }),
                  );
              }}
            >
              <Field label="Platform" hint="Saving an existing platform replaces it">
                <input
                  required
                  value={newLink.platform}
                  onChange={(event) =>
                    setNewLink((c) => ({ ...c, platform: event.target.value }))
                  }
                  placeholder="instagram"
                  className="field"
                />
              </Field>
              <Field label="Label">
                <input
                  value={newLink.label}
                  onChange={(event) =>
                    setNewLink((c) => ({ ...c, label: event.target.value }))
                  }
                  placeholder="@retrowhatches.jo"
                  className="field"
                />
              </Field>
              <Field label="URL">
                <input
                  required
                  type="url"
                  value={newLink.url}
                  onChange={(event) =>
                    setNewLink((c) => ({ ...c, url: event.target.value }))
                  }
                  className="field"
                />
              </Field>
              <button type="submit" className="btn btn-secondary w-full">
                Save link
              </button>
            </form>
          </Panel>

          <Panel title="Payments">
            <p className="px-4 py-4 text-sm text-ink-muted">
              Payment provider keys live in the server environment
              (<code className="text-xs">PAYMENT_PROVIDER</code>,{" "}
              <code className="text-xs">PAYMENT_SECRET_KEY</code>,{" "}
              <code className="text-xs">PAYMENT_WEBHOOK_SECRET</code>) and are
              deliberately not editable here.
            </p>
          </Panel>
        </div>
      </div>

      <Toast toast={toast} />
    </>
  );
}
