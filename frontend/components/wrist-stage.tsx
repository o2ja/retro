"use client";

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Arrow } from "@/components/primitives";
import { isSold, modelName, priceLabel } from "@/lib/api";
import type { ProductSummary } from "@/lib/types";

gsap.registerPlugin(ScrollTrigger);

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const SWIPE = 70;

const WRIST =
  "M0 6 C 420 16, 640 48, 800 48 C 960 48, 1220 28, 1600 0 " +
  "L1600 400 C 1220 372, 960 352, 800 352 C 640 352, 420 384, 0 394 Z";

/**
 * One wrist, every watch. Cutouts share a canvas and a case width, so each
 * watch lands in exactly the same place on the band. Drag, arrows or the rail
 * slide the current watch off along the wrist and the next one on.
 */
export function WristStage({ products }: { products: ProductSummary[] }) {
  const count = products.length;
  const [index, setIndex] = useState(0);
  const current = useRef(0);
  const busy = useRef(false);
  const sectionRef = useRef<HTMLElement>(null);
  const bandRef = useRef<SVGSVGElement>(null);
  const sheenRef = useRef<SVGRadialGradientElement>(null);
  const watchesRef = useRef<HTMLDivElement>(null);
  const watchRefs = useRef<(HTMLDivElement | null)[]>([]);
  const drag = useRef<{ x: number; dx: number } | null>(null);

  // The wrist extends and the first watch settles onto it as the section arrives.
  useEffect(() => {
    if (reducedMotion()) return;
    const ctx = gsap.context(() => {
      gsap
        .timeline({
          scrollTrigger: { trigger: sectionRef.current, start: "top 85%", end: "top 15%", scrub: 0.8 },
        })
        .from(bandRef.current, { scaleX: 0.15, autoAlpha: 0, ease: "power2.out" })
        .from(
          watchesRef.current,
          { yPercent: -45, rotate: 16, scale: 1.25, autoAlpha: 0, ease: "power3.out" },
          0.15,
        );
    }, sectionRef);
    return () => ctx.revert();
  }, []);

  function go(target: number, dir: 1 | -1) {
    const next = (target + count) % count;
    const from = current.current;
    if (next === from || busy.current) return;
    const outgoing = watchRefs.current[from];
    const incoming = watchRefs.current[next];
    current.current = next;
    setIndex(next);

    if (reducedMotion()) {
      gsap.set(outgoing, { autoAlpha: 0 });
      gsap.set(incoming, { autoAlpha: 1, x: 0, xPercent: 0, rotate: 0 });
      return;
    }
    busy.current = true;
    gsap.to(outgoing, {
      xPercent: -120 * dir,
      rotate: -10 * dir,
      scale: 0.9,
      autoAlpha: 0,
      duration: 0.8,
      ease: "power3.in",
    });
    gsap.fromTo(
      incoming,
      { x: 0, xPercent: 120 * dir, rotate: 10 * dir, scale: 0.9, autoAlpha: 0 },
      {
        xPercent: 0,
        rotate: 0,
        scale: 1,
        autoAlpha: 1,
        duration: 1.1,
        delay: 0.35,
        ease: "expo.out",
        onComplete: () => {
          busy.current = false;
        },
      },
    );
    // The light on the wrist shifts with the watch, as if the arm turned.
    gsap.to(sheenRef.current, { attr: { cx: 0.3 + ((next * 0.37) % 0.4) }, duration: 1.4, ease: "power2.inOut" });
  }

  if (count === 0) return null;
  const active = products[index];

  return (
    <section
      id="wrist"
      ref={sectionRef}
      aria-roledescription="carousel"
      aria-label="Watches from the collection, shown on the wrist"
      className="relative scroll-mt-16 overflow-hidden bg-surface-muted py-section-sm"
      onKeyDown={(event) => {
        if (event.key === "ArrowRight") go(current.current + 1, 1);
        if (event.key === "ArrowLeft") go(current.current - 1, -1);
      }}
    >
      <div className="shell flex flex-wrap items-end justify-between gap-6">
        <h2 data-split className="max-w-xl text-[clamp(2.4rem,1.5rem+3.4vw,4.75rem)] leading-[0.98] tracking-[-0.02em]">
          On the wrist
        </h2>
        <p className="max-w-sm text-ink-muted">
          Drag the watch along the wrist, or use the arrows, to try on each piece in the collection.
        </p>
      </div>

      {/* The stage: wrist band across, watch on top. */}
      <div
        className="relative mt-8 h-[clamp(24rem,62svh,40rem)] cursor-grab touch-pan-y select-none active:cursor-grabbing"
        onPointerDown={(event) => {
          if (busy.current) return;
          drag.current = { x: event.clientX, dx: 0 };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          drag.current.dx = event.clientX - drag.current.x;
          gsap.set(watchRefs.current[current.current], {
            x: drag.current.dx * 0.8,
            rotate: drag.current.dx * 0.02,
          });
        }}
        onPointerUp={() => {
          const dx = drag.current?.dx ?? 0;
          drag.current = null;
          if (Math.abs(dx) > SWIPE) go(current.current + (dx < 0 ? 1 : -1), dx < 0 ? 1 : -1);
          else gsap.to(watchRefs.current[current.current], { x: 0, rotate: 0, duration: 0.8, ease: "elastic.out(1, 0.55)" });
        }}
        onPointerCancel={() => {
          drag.current = null;
          gsap.to(watchRefs.current[current.current], { x: 0, rotate: 0, duration: 0.6 });
        }}
      >
        {/* Forearm on the left, narrowest at the wrist where the watch sits,
            widening again toward the hand. Band is 56% of the stage; its
            narrowest edges sit 12% in, which is what the strap mask matches. */}
        <svg
          ref={bandRef}
          aria-hidden
          viewBox="0 0 1600 400"
          preserveAspectRatio="none"
          className="wrist-band absolute inset-x-0 top-1/2 h-[56%] w-full -translate-y-1/2 overflow-visible"
        >
          <defs>
            <linearGradient id="wrist-shade" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#050505" />
              <stop offset="0.16" stopColor="#141414" />
              <stop offset="0.36" stopColor="#242424" />
              <stop offset="0.56" stopColor="#1a1a1a" />
              <stop offset="0.84" stopColor="#111111" />
              <stop offset="1" stopColor="#050505" />
            </linearGradient>
            <radialGradient ref={sheenRef} id="wrist-sheen" cx="0.5" cy="0.34" r="0.45">
              <stop offset="0" stopColor="#fff" stopOpacity="0.2" />
              <stop offset="1" stopColor="#fff" stopOpacity="0" />
            </radialGradient>
          </defs>
          <path d={WRIST} fill="url(#wrist-shade)" />
          <path d={WRIST} fill="url(#wrist-sheen)" />
        </svg>

        {/* Static mask (the strap turns under at the band's edges) > entry
            animation layer > fixed centring box > the element GSAP moves. */}
        <div className="wrist-mask pointer-events-none absolute inset-0">
          <div ref={watchesRef} className="absolute inset-0">
            {products.map((product, position) => (
              <div
                key={product.id}
                className="absolute top-1/2 left-1/2 aspect-[3/5] h-[72%] -translate-x-1/2 -translate-y-1/2"
              >
                <div
                  ref={(el) => {
                    watchRefs.current[position] = el;
                  }}
                  aria-hidden={position !== index}
                  className="wrist-watch relative size-full"
                  style={position === 0 ? undefined : { opacity: 0, visibility: "hidden" }}
                >
                  <Image
                    src={product.cutout_url!}
                    alt={position === index ? `${product.brand?.name ?? ""} ${modelName(product)}` : ""}
                    fill
                    sizes="(max-width: 768px) 60vw, 26rem"
                    quality={90}
                    draggable={false}
                    preload={position === 0}
                    className="object-contain"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <StageButton side="left" onClick={() => go(current.current - 1, -1)} />
        <StageButton side="right" onClick={() => go(current.current + 1, 1)} />
      </div>

      <div className="shell mt-8 grid items-end gap-8 lg:grid-cols-[1fr_auto]">
        <div key={active.id} aria-live="polite">
          <p className="rise">
            <span className="maker">{active.brand?.name}</span>
          </p>
          <h3 className="rise mt-1 text-[clamp(1.9rem,1.3rem+2vw,3rem)] leading-tight">
            <span style={{ "--delay": "80ms" } as React.CSSProperties}>{modelName(active)}</span>
          </h3>
          <div
            className="fade-in mt-5 flex flex-wrap items-center gap-x-8 gap-y-4"
            style={{ "--delay": "200ms" } as React.CSSProperties}
          >
            <p className="figures text-lg">{isSold(active) ? "Sold" : priceLabel(active)}</p>
            <Link href={`/shop/${active.slug}`} className="btn btn-primary">
              View this watch
            </Link>
            {!isSold(active) && (
              <Link href={`/shop/${active.slug}#request`} className="link-under text-[0.9375rem] text-ink-muted hover:text-ink">
                Request it
              </Link>
            )}
          </div>
        </div>

        {/* The rail: every watch at a glance, and a quicker way to jump. */}
        <div className="flex flex-col gap-3 lg:items-end">
          <p className="figures text-sm text-ink-subtle">
            <span className="text-ink">{String(index + 1).padStart(2, "0")}</span> / {String(count).padStart(2, "0")}
          </p>
          <div role="tablist" aria-label="Choose a watch" className="no-scrollbar -mx-1 flex gap-1 overflow-x-auto px-1">
            {products.map((product, position) => (
              <button
                key={product.id}
                type="button"
                role="tab"
                aria-selected={position === index}
                aria-label={`${product.brand?.name ?? ""} ${modelName(product)}`}
                onClick={() => go(position, position > index ? 1 : -1)}
                className={`relative h-16 w-11 shrink-0 rounded-md transition-[background-color,opacity] duration-500 ${
                  position === index ? "bg-white shadow-sm" : "opacity-55 hover:bg-white/70 hover:opacity-100"
                }`}
              >
                <Image src={product.cutout_url!} alt="" fill sizes="44px" className="object-contain p-1" />
                <span
                  aria-hidden
                  className={`absolute inset-x-2 -bottom-1 h-px bg-ink transition-transform duration-500 ${
                    position === index ? "scale-x-100" : "scale-x-0"
                  }`}
                />
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function StageButton({ side, onClick }: { side: "left" | "right"; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      onPointerDown={(event) => event.stopPropagation()}
      className={`group absolute top-1/2 z-10 grid size-12 -translate-y-1/2 place-items-center rounded-full border border-white/40 bg-white/10 text-white backdrop-blur-sm transition-[background-color,border-color] duration-500 hover:border-white hover:bg-white/20 sm:size-14 ${
        side === "left" ? "left-[var(--spacing-gutter)]" : "right-[var(--spacing-gutter)]"
      }`}
    >
      <span className="sr-only">{side === "left" ? "Previous watch" : "Next watch"}</span>
      <Arrow direction={side} className="!w-6" />
    </button>
  );
}
