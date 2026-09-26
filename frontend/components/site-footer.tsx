import Link from "next/link";

import type { SiteSettings, SocialLink } from "@/lib/types";

const LINKS = [
  { href: "/shop", label: "Collection" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function SiteFooter({
  settings,
  socialLinks,
}: {
  settings: SiteSettings | null;
  socialLinks: SocialLink[];
}) {
  const brand = settings?.brand_name ?? "Retro Watches";

  return (
    <footer className="on-dark bg-surface-deep">
      <div className="shell grid gap-14 pt-20 pb-10 md:grid-cols-12 md:pt-28">
        <div className="md:col-span-6">
          <p className="max-w-md font-display text-[clamp(1.75rem,1.2rem+2vw,2.75rem)] leading-[1.1]">
            Every piece described as it is, and sold by a person you can call.
          </p>
          <Link href="/contact" className="btn btn-primary mt-10">
            Make an inquiry
          </Link>
        </div>

        <nav aria-label="Footer" className="md:col-span-2 md:col-start-8">
          <p className="eyebrow">Visit</p>
          <ul className="mt-5 space-y-3">
            {LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="link-line text-[0.95rem]">
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="md:col-span-3">
          <p className="eyebrow">Speak to us</p>
          <ul className="mt-5 space-y-3 text-[0.95rem]">
            {settings?.contact_email && (
              <li>
                <a href={`mailto:${settings.contact_email}`} className="link-line">
                  {settings.contact_email}
                </a>
              </li>
            )}
            {settings?.contact_phone && (
              <li>
                <a href={`tel:${settings.contact_phone.replace(/[^\d+]/g, "")}`} className="link-line">
                  {settings.contact_phone}
                </a>
              </li>
            )}
            {socialLinks.map((link) => (
              <li key={link.platform}>
                <a href={link.url} target="_blank" rel="noreferrer noopener" className="link-line">
                  {link.label ?? link.platform}
                </a>
              </li>
            ))}
            {settings?.address && <li className="text-ink-muted">{settings.address}</li>}
          </ul>
        </div>
      </div>

      <div className="shell">
        {/* The wordmark stretched edge to edge: the footer's horizon. */}
        <svg viewBox="0 0 1000 118" aria-hidden data-reveal className="block w-full text-clay/20 select-none">
          <text
            x="0"
            y="108"
            textLength="1000"
            lengthAdjust="spacing"
            fill="currentColor"
            style={{ fontFamily: "var(--font-display)", fontSize: 124 }}
          >
            {brand.toUpperCase()}
          </text>
        </svg>
        <div className="flex flex-col gap-2 border-t border-line-strong/60 py-6 text-xs text-ink-subtle sm:flex-row sm:justify-between">
          <p>
            © {new Date().getFullYear()} {brand}
            {settings?.owner_name ? `, ${settings.owner_name}` : ""}
          </p>
          <p>Condition stated, never implied.</p>
        </div>
      </div>
    </footer>
  );
}
