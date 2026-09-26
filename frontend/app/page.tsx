import Image from "next/image";
import Link from "next/link";

import { HeroDial } from "@/components/hero-dial";
import { WristStage } from "@/components/wrist-stage";
import { getCollection, getHomepage, getSiteSettings, isSold } from "@/lib/api";
import type { HomepageSection } from "@/lib/types";

const STEPS = [
  {
    title: "Choose the piece",
    body: "Every listing shows the watch itself, its condition and exactly what comes with it.",
  },
  {
    title: "Request it",
    body: "Leave your name, email and phone number. Nothing is paid online and no card details are asked for.",
  },
  {
    title: "Speak with the store",
    body: "The store contacts you personally to answer questions and arrange viewing and delivery.",
  },
];

export default async function Page() {
  const [homepage, collection, settings] = await Promise.all([
    getHomepage().catch(() => null),
    getCollection().catch(() => null),
    getSiteSettings().catch(() => null),
  ]);

  const section = (type: HomepageSection["section_type"]) =>
    homepage?.sections.find((item) => item.section_type === type) ?? null;
  const hero = section("HERO");
  const story = section("BRAND_STORY");
  const brand = settings?.brand_name ?? "Retro Watches";

  // Only watches with a cutout can go on the wrist; available pieces lead.
  const onWrist = (collection?.products ?? [])
    .filter((product) => product.cutout_url)
    .sort((a, b) => Number(isSold(a)) - Number(isSold(b)));

  return (
    <>
      <HeroDial
        brand={brand}
        title={hero?.title ?? "Time, kept well"}
        body={hero?.subtitle ?? "A private collection of fine pre-owned watches, selected one piece at a time."}
      />

      {onWrist.length > 0 && <WristStage products={onWrist} />}

      {/* The house, in one paragraph */}
      <section className="shell grid gap-14 py-section lg:grid-cols-12 lg:items-center lg:gap-6">
        <div className="lg:col-span-6">
          <p
            data-split
            className="font-display text-[clamp(1.9rem,1.2rem+2.4vw,3.4rem)] leading-[1.12] tracking-[-0.01em] text-balance"
          >
            {story?.body ??
              "Every watch here was bought carefully, is described honestly, and is offered to a small number of collectors at a time."}
          </p>
          <Link href="/about" className="link-under mt-10 inline-block text-[0.9375rem] text-ink-muted hover:text-ink">
            About the house
          </Link>
        </div>
        <div data-reveal="image" className="relative aspect-[4/5] overflow-hidden lg:col-span-5 lg:col-start-8">
          <Image
            src="/editorial/movement-exposed.jpg"
            alt=""
            fill
            sizes="(max-width: 1024px) 100vw, 40vw"
            className="object-cover"
          />
        </div>
      </section>

      {/* How buying works: a real sequence, so it is numbered. */}
      <section className="border-t border-line">
        <div className="shell grid gap-14 py-section lg:grid-cols-12 lg:gap-6">
          <div className="relative aspect-[4/5] overflow-hidden lg:sticky lg:top-24 lg:col-span-5 lg:self-start">
            <Image
              data-parallax
              src="/editorial/movement-macro.jpg"
              alt=""
              fill
              sizes="(max-width: 1024px) 100vw, 40vw"
              className="scale-125 object-cover"
            />
          </div>
          <div className="lg:col-span-6 lg:col-start-7">
            <h2 data-split className="max-w-lg text-[clamp(2.25rem,1.5rem+3vw,4.25rem)] leading-[1.02] text-balance">
              Buying a watch, the considered way
            </h2>
            <ol className="relative mt-14 sm:mt-20">
              <span aria-hidden className="absolute top-0 bottom-0 left-[0.95rem] w-px bg-line-strong sm:left-[1.2rem]" />
              <span
                aria-hidden
                data-draw
                className="absolute top-0 bottom-0 left-[0.95rem] w-px origin-top bg-clay sm:left-[1.2rem]"
              />
              {STEPS.map((step, index) => (
                <li key={step.title} data-reveal className="relative grid grid-cols-[3.5rem_1fr] gap-x-4 pb-14 last:pb-0 sm:grid-cols-[5rem_1fr]">
                  <span className="relative grid size-8 place-items-center rounded-full border border-clay bg-surface font-display text-lg text-clay italic sm:size-10 sm:text-xl">
                    {index + 1}
                  </span>
                  <div>
                    <h3 className="text-[1.75rem] leading-tight sm:text-[2rem]">{step.title}</h3>
                    <p className="mt-3 max-w-md text-[1rem] leading-relaxed text-ink-muted">{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>
            <div className="mt-16">
              <Link href="/shop" className="btn btn-primary">
                Browse the collection
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Closing invitation */}
      <section className="on-dark relative isolate overflow-hidden bg-surface-deep">
        <Image
          data-parallax
          src="/editorial/movement-mono.jpg"
          alt=""
          fill
          sizes="100vw"
          className="-z-10 scale-125 object-cover opacity-40"
        />
        <div aria-hidden className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,rgb(7_12_20/0.9),rgb(7_12_20/0.2))]" />
        <div className="shell flex min-h-[80svh] flex-col items-start justify-center py-section">
          <h2 data-split className="max-w-4xl text-[clamp(2.75rem,1.4rem+5vw,6.5rem)] leading-[0.96] tracking-[-0.025em]">
            Looking for a particular reference?
          </h2>
          <p data-reveal className="mt-8 max-w-md text-[1.05rem] text-ink-muted">
            Tell us the watch you have in mind. If it is not in the collection, we will let you know when it is.
          </p>
          <div data-reveal>
            <Link href="/contact" className="btn btn-light mt-10">
              Tell us what you are after
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
