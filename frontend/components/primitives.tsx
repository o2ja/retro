/**
 * Small shared presentational pieces.
 *
 * Grouped in one file because each is a handful of lines and they are always
 * imported together; splitting them would be more files, not more clarity.
 */

/**
 * Stands in for a photograph that has not been taken yet.
 *
 * Deliberately a drawn dial rather than a grey box or a stock image: it says
 * "photography to come" without pretending to show the watch. Swapping in a
 * real photograph needs no code change - the image simply appears.
 */
export function PhotoPlaceholder({
  seed = 0,
  label,
  className = "",
  markClassName = "w-1/2",
}: {
  seed?: number;
  label?: string;
  className?: string;
  markClassName?: string;
}) {
  return (
    <div
      className={`flex h-full w-full flex-col items-center justify-center gap-4 bg-surface-muted ${className}`}
    >
      <DialMark seed={seed} className={`text-clay/45 ${markClassName}`} />
      {label && (
        <span className="text-sm text-ink-subtle">
          {label}
        </span>
      )}
    </div>
  );
}

/**
 * Dial geometry, reduced to a few hairlines. Decorative, so it is hidden from
 * assistive technology.
 *
 * `seed` sets the time the hands show. It is deterministic, so a given watch
 * always gets the same dial and a grid of placeholders reads as a set of
 * different timepieces rather than one image repeated.
 */
export function DialMark({
  className = "",
  seed,
}: {
  className?: string;
  seed?: number;
}) {
  const ticks = Array.from({ length: 12 }, (_, index) => index * 30);
  const minute = seed === undefined ? 0 : (seed * 37) % 60;
  const hour = seed === undefined ? 0 : (seed * 7) % 12;
  const minuteAngle = minute * 6;
  const hourAngle = hour * 30 + minute * 0.5;
  return (
    <svg
      viewBox="0 0 200 200"
      aria-hidden
      className={className}
      fill="none"
      stroke="currentColor"
    >
      <circle cx="100" cy="100" r="96" strokeWidth="0.5" />
      <circle cx="100" cy="100" r="74" strokeWidth="0.5" />
      <circle cx="100" cy="100" r="2" strokeWidth="0.75" />
      {ticks.map((angle) => (
        <line
          key={angle}
          x1="100"
          y1="10"
          x2="100"
          y2={angle % 90 === 0 ? 26 : 19}
          strokeWidth={angle % 90 === 0 ? 1 : 0.5}
          transform={`rotate(${angle} 100 100)`}
        />
      ))}
      <line
        x1="100"
        y1="100"
        x2="100"
        y2="52"
        strokeWidth="1.5"
        transform={`rotate(${hourAngle} 100 100)`}
      />
      <line
        x1="100"
        y1="100"
        x2="100"
        y2="34"
        strokeWidth="1"
        transform={`rotate(${minuteAngle} 100 100)`}
      />
    </svg>
  );
}

/** A long hairline arrow. Drawn, not an icon-font glyph, so it matches the type. */
export function Arrow({
  direction = "right",
  className = "",
}: {
  direction?: "left" | "right";
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 40 12"
      aria-hidden
      fill="none"
      stroke="currentColor"
      strokeWidth="1"
      className={`h-3 w-10 ${direction === "left" ? "-scale-x-100" : ""} ${className}`}
    >
      <path d="M0 6h39M33 0.5 39 6l-6 5.5" />
    </svg>
  );
}
