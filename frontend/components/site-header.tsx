"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useState } from "react";

import type { SocialLink } from "@/lib/types";

const NAV = [
  { href: "/shop", label: "Collection" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function SiteHeader({
  brandName,
  instagram,
}: {
  brandName: string;
  instagram: SocialLink | null;
}) {
  const pathname = usePathname();
  const menuId = useId();

  // Tied to the route it was opened on, so navigating closes it without an effect.
  const [menu, setMenu] = useState({ open: false, route: pathname });
  const menuOpen = menu.open && menu.route === pathname;
  const setMenuOpen = (open: boolean) => setMenu({ open, route: pathname });

  const [scrolled, setScrolled] = useState(false);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let last = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      setScrolled(y > 24);
      // Step aside while reading down the page; return the moment they scroll up.
      setHidden(y > 240 && y > last);
      last = y;
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setMenuOpen(false);
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menuOpen]);

  if (pathname.startsWith("/admin")) return null;

  const clear = !scrolled && !menuOpen;
  // The About page opens on a dark photograph; the header reads light over it.
  const overDark = clear && pathname === "/about";

  return (
    <>
      <header
        className={`fixed inset-x-0 top-0 z-40 transition-[transform,background-color,color,border-color] duration-700 ease-[var(--ease-luxury)] ${
          hidden && !menuOpen ? "-translate-y-full" : ""
        } ${
          clear ? "border-b border-transparent" : "border-b border-line bg-canvas/85 backdrop-blur-lg"
        } ${overDark ? "on-dark" : ""} text-ink`}
      >
        <div className="shell grid h-16 grid-cols-[1fr_auto_1fr] items-center sm:h-20">
          <nav aria-label="Primary" className="hidden md:block">
            <ul className="flex items-center gap-10">
              {NAV.slice(0, 2).map((item) => (
                <NavItem key={item.href} {...item} pathname={pathname} />
              ))}
            </ul>
          </nav>

          <Link
            href="/"
            className="col-start-1 justify-self-start font-display text-[0.95rem] tracking-[0.26em] whitespace-nowrap uppercase sm:text-[1.2rem] sm:tracking-[0.34em] md:col-start-2 md:justify-self-center"
            aria-label={`${brandName}, home`}
          >
            {brandName}
          </Link>

          <div className="col-start-3 flex items-center justify-end gap-10">
            <nav aria-label="Secondary" className="hidden md:block">
              <ul className="flex items-center gap-10">
                {NAV.slice(2).map((item) => (
                  <NavItem key={item.href} {...item} pathname={pathname} />
                ))}
              </ul>
            </nav>
            {instagram && (
              <a
                href={instagram.url}
                target="_blank"
                rel="noreferrer noopener"
                className="hidden opacity-80 transition-opacity hover:opacity-100 md:block"
              >
                <span className="sr-only">Instagram {instagram.label}</span>
                <InstagramGlyph />
              </a>
            )}
            <button
              type="button"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-expanded={menuOpen}
              aria-controls={menuId}
              className="-mr-2 flex h-11 items-center gap-3 px-2 text-[0.9375rem] md:hidden"
            >
              <span>{menuOpen ? "Close" : "Menu"}</span>
              <span aria-hidden className="relative block h-2.5 w-6">
                <span
                  className={`absolute left-0 block h-px w-6 bg-current transition-transform duration-500 ${
                    menuOpen ? "top-1 rotate-45" : "top-0"
                  }`}
                />
                <span
                  className={`absolute left-0 block h-px bg-current transition-all duration-500 ${
                    menuOpen ? "top-1 w-6 -rotate-45" : "top-2.5 w-4"
                  }`}
                />
              </span>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile menu: a full page of its own, not a dropdown. */}
      <div
        id={menuId}
        aria-hidden={!menuOpen}
        inert={!menuOpen}
        className={`fixed inset-0 z-30 flex flex-col bg-canvas pt-16 transition-[opacity,visibility] duration-500 md:hidden ${
          menuOpen ? "visible opacity-100" : "invisible opacity-0"
        }`}
      >
        <nav aria-label="Menu" className="shell flex flex-1 flex-col justify-center">
          <ul className="space-y-2">
            {[{ href: "/", label: "Home" }, ...NAV].map((item, index) => (
              <li key={item.href} className="rise">
                <span
                  style={{ "--delay": `${120 + index * 70}ms` } as React.CSSProperties}
                  className={menuOpen ? "" : "!animate-none translate-y-full"}
                >
                  <Link
                    href={item.href}
                    aria-current={pathname === item.href ? "page" : undefined}
                    className="block py-2 font-display text-[2.75rem] leading-tight aria-[current=page]:text-clay"
                  >
                    {item.label}
                  </Link>
                </span>
              </li>
            ))}
          </ul>
        </nav>
        <div className="shell flex items-center justify-between border-t border-line py-6 text-sm text-ink-muted">
          <span>Authenticated pre-owned watches</span>
          {instagram && (
            <a href={instagram.url} target="_blank" rel="noreferrer noopener" className="link-under">
              {instagram.label ?? "Instagram"}
            </a>
          )}
        </div>
      </div>
    </>
  );
}

function NavItem({ href, label, pathname }: { href: string; label: string; pathname: string }) {
  const active = pathname.startsWith(href);
  return (
    <li>
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        className="link-line text-[0.9375rem] text-ink-muted transition-colors hover:text-ink aria-[current=page]:text-ink"
      >
        {label}
      </Link>
    </li>
  );
}

function InstagramGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden fill="none" stroke="currentColor" strokeWidth="1" className="size-[1.15rem]">
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.3" cy="6.7" r="0.6" fill="currentColor" stroke="none" />
    </svg>
  );
}
