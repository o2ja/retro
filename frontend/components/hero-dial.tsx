"use client";

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Link from "next/link";
import { useEffect, useRef } from "react";

gsap.registerPlugin(ScrollTrigger);

const MINUTES = Array.from({ length: 60 }, (_, i) => i * 6);
const HOURS = Array.from({ length: 12 }, (_, i) => i * 30);

/** Hand angles for the local time. The seconds hand steps 8 times a second, like a 28,800 vph movement. */
function liveAngles() {
  const now = new Date();
  const seconds = now.getSeconds() + Math.floor(now.getMilliseconds() / 125) / 8;
  const minutes = now.getMinutes() + seconds / 60;
  const hours = (now.getHours() % 12) + minutes / 60;
  return { hour: hours * 30, minute: minutes * 6, second: seconds * 6 };
}

export function HeroDial({ title, body, brand }: { title: string; body: string; brand: string }) {
  const sectionRef = useRef<HTMLElement>(null);
  const dialRef = useRef<HTMLDivElement>(null);
  const hourRef = useRef<SVGGElement>(null);
  const minuteRef = useRef<SVGGElement>(null);
  const secondRef = useRef<SVGGElement>(null);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const wind = { progress: reduced ? 1 : 0 };

    const render = () => {
      const live = liveAngles();
      const p = wind.progress;
      // While winding, the minute hand makes one extra turn on its way to the time.
      hourRef.current?.setAttribute("transform", `rotate(${live.hour * p} 200 200)`);
      minuteRef.current?.setAttribute("transform", `rotate(${(live.minute + 360) * p} 200 200)`);
      secondRef.current?.setAttribute("transform", `rotate(${live.second * p} 200 200)`);
    };
    render();
    gsap.ticker.add(render);

    const ctx = gsap.context(() => {
      if (reduced) return;
      gsap
        .timeline({ delay: 0.2 })
        .from(dialRef.current, { autoAlpha: 0, scale: 0.86, rotate: -12, duration: 2, ease: "expo.out" })
        .to(wind, { progress: 1, duration: 2.6, ease: "expo.inOut" }, 0.3);

      gsap.to(dialRef.current, {
        yPercent: 18,
        scale: 0.82,
        rotate: -10,
        ease: "none",
        scrollTrigger: { trigger: sectionRef.current, start: "top top", end: "bottom top", scrub: true },
      });
      gsap.to("[data-hero-copy]", {
        yPercent: -30,
        autoAlpha: 0,
        ease: "none",
        scrollTrigger: { trigger: sectionRef.current, start: "top top", end: "80% top", scrub: true },
      });
    }, sectionRef);

    return () => {
      gsap.ticker.remove(render);
      ctx.revert();
    };
  }, []);

  // The sunburst catches the light from wherever the pointer is.
  function tilt(event: React.PointerEvent) {
    const dial = dialRef.current;
    if (!dial || event.pointerType !== "mouse") return;
    const box = dial.getBoundingClientRect();
    const angle = Math.atan2(event.clientY - (box.top + box.height / 2), event.clientX - (box.left + box.width / 2));
    dial.style.setProperty("--light", `${(angle * 180) / Math.PI + 60}deg`);
  }

  return (
    <section
      ref={sectionRef}
      onPointerMove={tilt}
      className="relative isolate flex min-h-[100svh] items-center overflow-hidden pt-24 pb-16"
    >
      <div
        aria-hidden
        className="absolute inset-0 -z-10 bg-[radial-gradient(60%_70%_at_72%_45%,#eaeaea_0%,transparent_70%)]"
      />

      <div className="shell grid w-full items-center gap-12 lg:grid-cols-12 lg:gap-6">
        <div data-hero-copy className="order-2 lg:order-1 lg:col-span-6">
          <h1 className="text-[clamp(3.25rem,1.4rem+6.6vw,8.5rem)] leading-[0.98] tracking-[-0.035em] text-balance">
            {title.split(/(?<=,)\s+/).map((line, index) => (
              <span key={line} className="rise">
                <span style={{ "--delay": `${900 + index * 130}ms` } as React.CSSProperties}>{line}</span>
              </span>
            ))}
          </h1>
          <p
            className="fade-in mt-8 max-w-md text-[1.075rem] leading-relaxed text-ink-muted"
            style={{ "--delay": "1350ms" } as React.CSSProperties}
          >
            {body}
          </p>
          <div
            className="fade-in mt-10 flex flex-wrap items-center gap-x-8 gap-y-4"
            style={{ "--delay": "1500ms" } as React.CSSProperties}
          >
            <Link href="/shop" className="btn btn-primary">
              Browse the collection
            </Link>
            <Link href="#wrist" className="link-under text-[0.9375rem] text-ink-muted hover:text-ink">
              See them on the wrist
            </Link>
          </div>
        </div>

        <div className="order-1 flex justify-center lg:order-2 lg:col-span-6 lg:justify-end">
          <div
            ref={dialRef}
            role="img"
            aria-label="A watch dial showing the current time"
            className="dial-face on-dark relative aspect-square w-[min(78vw,26rem)] rounded-full lg:w-[min(40vw,36rem)]"
          >
            <svg viewBox="0 0 400 400" className="absolute inset-0 size-full" aria-hidden>
              <g stroke="var(--color-ink)" strokeOpacity="0.55">
                {MINUTES.map((a) => (
                  <line
                    key={a}
                    x1="200"
                    y1="14"
                    x2="200"
                    y2={a % 30 === 0 ? 26 : 21}
                    strokeWidth={a % 30 === 0 ? 1.4 : 0.6}
                    transform={`rotate(${a} 200 200)`}
                  />
                ))}
              </g>
              <circle cx="200" cy="200" r="178" fill="none" stroke="var(--color-ink)" strokeOpacity="0.14" />

              <g fill="var(--color-clay)">
                {HOURS.map((a) =>
                  a === 0 ? (
                    <g key={a}>
                      <rect x="189" y="36" width="7" height="40" rx="1" />
                      <rect x="204" y="36" width="7" height="40" rx="1" />
                    </g>
                  ) : (
                    <rect key={a} x="196.5" y="38" width="7" height={a % 90 === 0 ? 38 : 30} rx="1" transform={`rotate(${a} 200 200)`} />
                  ),
                )}
              </g>

              <text
                x="200"
                y="132"
                textAnchor="middle"
                fill="var(--color-ink)"
                style={{ fontFamily: "var(--font-display)", fontSize: 15, letterSpacing: "0.32em" }}
              >
                {brand.toUpperCase()}
              </text>
              <text
                x="200"
                y="285"
                textAnchor="middle"
                fill="var(--color-clay)"
                style={{ fontFamily: "var(--font-display)", fontSize: 12, fontStyle: "italic" }}
              >
                Pre-owned, kept well
              </text>

              <g ref={hourRef}>
                <path d="M200 92 L208 200 L200 212 L192 200 Z" fill="var(--color-ink)" />
                <path d="M200 92 L200 212 L192 200 Z" fill="#000" fillOpacity="0.18" />
              </g>
              <g ref={minuteRef}>
                <path d="M200 44 L206 200 L200 214 L194 200 Z" fill="var(--color-ink)" />
                <path d="M200 44 L200 214 L194 200 Z" fill="#000" fillOpacity="0.18" />
              </g>
              <g ref={secondRef}>
                <line x1="200" y1="240" x2="200" y2="34" stroke="var(--color-clay)" strokeWidth="1.4" />
                <circle cx="200" cy="232" r="5" fill="var(--color-clay)" />
              </g>
              <circle cx="200" cy="200" r="7" fill="var(--color-clay)" />
              <circle cx="200" cy="200" r="2.5" fill="var(--color-surface-deep)" />
            </svg>
          </div>
        </div>
      </div>

      <div aria-hidden className="absolute bottom-8 left-1/2 hidden h-14 w-px -translate-x-1/2 overflow-hidden bg-line-strong md:block">
        <span className="block h-1/2 w-full animate-[scroll-cue_2.4s_var(--ease-glide)_infinite] bg-clay" />
      </div>
    </section>
  );
}
