"use client";

import Image from "next/image";
import { useState } from "react";

import { PhotoPlaceholder } from "@/components/primitives";
import type { ProductImage } from "@/lib/types";

/**
 * Phones: a full-bleed swipe carousel (native scroll-snap, so it moves under
 * the finger) with a counter. Large screens: the photographs stacked down the
 * page beside the sticky details, the second set smaller and offset.
 */
export function ProductGallery({
  images,
  productName,
  seed = 0,
}: {
  images: ProductImage[];
  productName: string;
  seed?: number;
}) {
  const [current, setCurrent] = useState(0);

  if (images.length === 0) {
    return (
      <div className="aspect-[4/5]">
        <PhotoPlaceholder seed={seed} label="Photograph to follow" markClassName="w-2/5" />
      </div>
    );
  }

  return (
    <div className="relative">
      <div
        className="no-scrollbar flex snap-x snap-mandatory overflow-x-auto lg:block lg:overflow-visible"
        onScroll={(event) => {
          const el = event.currentTarget;
          setCurrent(Math.round(el.scrollLeft / el.clientWidth));
        }}
      >
        {images.map((image, index) => (
          <figure
            key={image.id}
            className={`w-full shrink-0 snap-center ${
              index === 0 ? "" : "lg:mt-24 lg:ml-auto lg:w-[58%]"
            }`}
          >
            <div className="relative aspect-[4/5] overflow-hidden bg-surface-muted">
              <Image
                src={image.url}
                alt={image.alt_text ?? productName}
                fill
                preload={index === 0}
                sizes={index === 0 ? "(max-width: 1024px) 100vw, 58vw" : "(max-width: 1024px) 100vw, 34vw"}
                quality={90}
                className={`object-cover ${index === 0 ? "fade-in" : ""}`}
              />
            </div>
            {index > 0 && image.alt_text && (
              <figcaption className="mt-4 hidden text-sm text-ink-subtle lg:block">{image.alt_text}</figcaption>
            )}
          </figure>
        ))}
      </div>

      {images.length > 1 && (
        <div className="pointer-events-none absolute right-5 bottom-5 flex items-center gap-2 lg:hidden">
          {images.map((image, index) => (
            <span
              key={image.id}
              className={`block h-px transition-all duration-500 ${index === current ? "w-8 bg-white" : "w-4 bg-white/50"}`}
            />
          ))}
          <span className="sr-only">
            Photograph {current + 1} of {images.length}
          </span>
        </div>
      )}
    </div>
  );
}
