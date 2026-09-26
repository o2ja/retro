"use client";

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import Lenis from "lenis";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

gsap.registerPlugin(ScrollTrigger, SplitText);

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Smooth scrolling plus the site's scroll choreography. Pages opt in with
 * attributes, so they can stay server components:
 *   data-split          heading whose lines rise out of masks
 *   data-reveal         block that fades up once
 *   data-reveal="image" frame that fades in, its photo settling from a slight zoom
 *   data-parallax       photo that drifts against the scroll (give it room: scale-125)
 *   data-draw           rule that draws down as its section scrolls past
 */
export function Motion() {
  const pathname = usePathname();

  useEffect(() => {
    if (reducedMotion()) return;
    const lenis = new Lenis({ anchors: true });
    lenis.on("scroll", ScrollTrigger.update);
    const tick = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return () => {
      gsap.ticker.remove(tick);
      lenis.destroy();
    };
  }, []);

  useEffect(() => {
    if (reducedMotion() || pathname.startsWith("/admin")) return;

    const ctx = gsap.context(() => {
      const once = (trigger: Element) => ({ trigger, start: "top 88%", once: true });

      gsap.utils.toArray<HTMLElement>("[data-split]").forEach((el) => {
        SplitText.create(el, {
          type: "lines",
          mask: "lines",
          autoSplit: true,
          onSplit: (self) =>
            gsap.from(self.lines, {
              yPercent: 115,
              duration: 1.3,
              ease: "expo.out",
              stagger: 0.1,
              scrollTrigger: once(el),
            }),
        });
      });

      gsap.utils.toArray<HTMLElement>("[data-reveal]:not([data-reveal=image])").forEach((el) => {
        gsap.from(el, { y: 16, autoAlpha: 0, duration: 1.1, ease: "power2.out", scrollTrigger: once(el) });
      });

      // Photographs fade in and settle from a slight zoom; nothing slides.
      gsap.utils.toArray<HTMLElement>("[data-reveal=image]").forEach((el) => {
        const tl = gsap.timeline({ scrollTrigger: once(el) });
        tl.from(el, { autoAlpha: 0, duration: 1.2, ease: "power2.out" });
        const img = el.querySelector("img");
        if (img) tl.from(img, { scale: 1.08, duration: 1.8, ease: "power3.out" }, 0);
      });

      gsap.utils.toArray<HTMLElement>("[data-parallax]").forEach((el) => {
        gsap.fromTo(
          el,
          { yPercent: -9 },
          {
            yPercent: 9,
            ease: "none",
            scrollTrigger: { trigger: el.parentElement, start: "top bottom", end: "bottom top", scrub: true },
          },
        );
      });

      gsap.utils.toArray<HTMLElement>("[data-draw]").forEach((el) => {
        gsap.fromTo(
          el,
          { scaleY: 0 },
          {
            scaleY: 1,
            ease: "none",
            transformOrigin: "top",
            scrollTrigger: { trigger: el.parentElement, start: "top 70%", end: "bottom 60%", scrub: true },
          },
        );
      });
    });

    return () => ctx.revert();
  }, [pathname]);

  return null;
}
