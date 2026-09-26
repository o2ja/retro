import Image from "next/image";
import Link from "next/link";

import { getSiteSettings } from "@/lib/api";

export const metadata = {
  title: "About",
  description: "Retro Watches is a private collection of fine pre-owned watches, curated one piece at a time.",
};

/**
 * Describes only how the business works: no heritage, founding dates or
 * certifications are claimed, because none were supplied.
 */
const PRINCIPLES = [
  {
    title: "Selected one at a time",
    body: "There is no catalogue to fill and no quota to meet. A piece is listed only once we would happily wear it ourselves.",
  },
  {
    title: "Described as it is",
    body: "Condition is stated plainly and what comes with the watch is listed exactly, box, papers or neither.",
  },
  {
    title: "Priced openly",
    body: "Where a price is set, it is shown. Where it is not, we say so rather than inventing a figure.",
  },
  {
    title: "Sold in conversation",
    body: "Nothing is bought with a click. You request a watch, and the store speaks with you before anything changes hands.",
  },
];

export default async function AboutPage() {
  const settings = await getSiteSettings().catch(() => null);
  const brand = settings?.brand_name ?? "Retro Watches";

  return (
    <>
      <section className="on-dark relative isolate flex min-h-[92svh] items-end overflow-hidden bg-surface-deep">
        <Image
          data-parallax
          src="/editorial/movement-macro.jpg"
          alt=""
          fill
          preload
          sizes="100vw"
          className="-z-10 scale-125 object-cover opacity-60"
        />
        <div aria-hidden className="absolute inset-0 -z-10 bg-[linear-gradient(to_top,rgb(0_0_0/0.95),rgb(0_0_0/0.2)_70%)]" />
        <div className="shell pb-16 sm:pb-24">
          <h1 className="max-w-5xl text-[clamp(3rem,1.6rem+6vw,8rem)] leading-[0.92] tracking-[-0.03em]">
            <span className="rise">
              <span>A small collection,</span>
            </span>
            <span className="rise">
              <span style={{ "--delay": "120ms" } as React.CSSProperties}>kept properly.</span>
            </span>
          </h1>
        </div>
      </section>

      <section className="shell grid gap-10 py-section lg:grid-cols-12">
        <p data-split className="font-display text-[clamp(1.9rem,1.2rem+2.4vw,3.4rem)] leading-[1.12] text-balance lg:col-span-9">
          {brand} is a private collection of fine pre-owned watches
          {settings?.owner_name ? `, curated by ${settings.owner_name}` : ""}. Pieces are bought carefully, described
          honestly, and offered to a small number of collectors at a time.
        </p>
      </section>

      <section className="shell pb-section">
        <ul className="grid border-t border-line sm:grid-cols-2">
          {PRINCIPLES.map((principle, index) => (
            <li
              key={principle.title}
              data-reveal
              className={`border-b border-line py-12 sm:py-16 ${index % 2 === 0 ? "sm:pr-12" : "sm:border-l sm:pl-12"}`}
            >
              <h2 className="text-[2rem] leading-tight">{principle.title}</h2>
              <p className="mt-4 max-w-md leading-relaxed text-ink-muted">{principle.body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="bg-surface-muted">
        <div className="shell flex flex-col items-start justify-between gap-10 py-section-sm md:flex-row md:items-end">
          <h2 data-split className="max-w-2xl text-[clamp(2.25rem,1.5rem+3vw,4.25rem)] leading-[1.02]">
            Looking for something particular?
          </h2>
          <Link href="/contact" className="btn btn-primary">
            Get in touch
          </Link>
        </div>
      </section>
    </>
  );
}
