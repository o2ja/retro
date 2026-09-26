"use client";

/**
 * Dashboard charts, as inline SVG.
 *
 * Every chart here plots ONE measure, so this needs one hue — not a categorical
 * palette. There is no series identity to confuse, so no legend is required and
 * there is no colourblind pair problem to design around: the bark stroke and
 * clay fill sit on the light panel, and every value is also written as text, so
 * nothing is carried by colour alone.
 *
 * No chart library. These are a polyline and some rectangles.
 */

import { formatMoney } from "@/components/admin/ui";
import type { LabelledValue, SeriesPoint } from "@/lib/admin-types";

const EMPTY = "No data in this period yet.";

function EmptyPlot({ label }: { label: string }) {
  return (
    <div className="grid h-40 place-items-center text-sm text-ink-subtle">
      {label}
    </div>
  );
}

/**
 * Trend over time. Values are never invented: the API returns one point per day
 * including zeros, so a flat line means "nothing happened", not "no data".
 */
export function TrendChart({
  points,
  money = false,
  currency = "USD",
}: {
  points: SeriesPoint[];
  money?: boolean;
  currency?: string;
}) {
  const values = points.map((p) => Number(p.value));
  const total = values.reduce((sum, value) => sum + value, 0);

  if (points.length === 0) return <EmptyPlot label={EMPTY} />;
  if (total === 0) {
    return (
      <EmptyPlot
        label={`Nothing recorded across these ${points.length} days.`}
      />
    );
  }

  const width = 640;
  const height = 160;
  const pad = 8;
  const max = Math.max(...values, 1);
  const step = points.length > 1 ? (width - pad * 2) / (points.length - 1) : 0;

  const coords = values.map((value, index) => {
    const x = pad + index * step;
    const y = height - pad - (value / max) * (height - pad * 2);
    return [x, y] as const;
  });

  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${pad},${height - pad} ${line} ${(pad + (points.length - 1) * step).toFixed(1)},${height - pad}`;
  const peakIndex = values.indexOf(max);

  return (
    <figure className="px-4 py-4">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-40 w-full"
        role="img"
        aria-label={`Trend over ${points.length} days, peak ${max}`}
        preserveAspectRatio="none"
      >
        <polygon points={area} fill="var(--color-clay)" opacity="0.14" />
        <polyline
          points={line}
          fill="none"
          stroke="var(--color-bark)"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
        {coords[peakIndex] && (
          <circle
            cx={coords[peakIndex][0]}
            cy={coords[peakIndex][1]}
            r="4"
            fill="var(--color-bark)"
            stroke="var(--color-surface)"
            strokeWidth="2"
          />
        )}
      </svg>
      <figcaption className="mt-2 flex justify-between text-xs text-ink-subtle">
        <span>{points[0]?.date}</span>
        <span>
          Peak {money ? formatMoney(String(max), currency) : max} · total{" "}
          {money ? formatMoney(String(total), currency) : total}
        </span>
        <span>{points[points.length - 1]?.date}</span>
      </figcaption>
    </figure>
  );
}

/**
 * Magnitude across named things. A labelled bar list rather than a pie: it is
 * readable, sortable and doubles as the table view.
 */
export function BarList({
  rows,
  unit = "money",
  currency = "USD",
}: {
  rows: LabelledValue[];
  unit?: "money" | "units";
  currency?: string;
}) {
  if (rows.length === 0) return <EmptyPlot label={EMPTY} />;

  const valueOf = (row: LabelledValue) =>
    unit === "money" ? Number(row.revenue ?? 0) : (row.units ?? 0);
  const max = Math.max(...rows.map(valueOf), 1);

  return (
    <ul className="divide-y divide-line">
      {rows.map((row) => {
        const value = valueOf(row);
        const percent = Math.max((value / max) * 100, 1.5);
        return (
          <li key={row.label} className="px-4 py-3">
            <div className="flex items-baseline justify-between gap-4 text-sm">
              <span className="min-w-0 truncate">{row.label}</span>
              <span className="shrink-0 tabular-nums">
                {unit === "money"
                  ? formatMoney(row.revenue, currency)
                  : `${row.units ?? 0} sold`}
              </span>
            </div>
            <div
              className="mt-2 h-1.5 w-full bg-surface-muted"
              role="presentation"
            >
              <div
                className="h-full rounded-r-[2px] bg-clay"
                style={{ width: `${percent}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function StatTile({
  label,
  value,
  note,
  emphasis = false,
}: {
  label: string;
  value: string | number;
  note?: string;
  emphasis?: boolean;
}) {
  return (
    <div className="border border-line bg-surface px-4 py-4">
      <p className="eyebrow">{label}</p>
      <p
        className={`mt-2 font-display tabular-nums ${emphasis ? "text-3xl" : "text-2xl"}`}
      >
        {value}
      </p>
      {note && <p className="mt-1 text-xs text-ink-subtle">{note}</p>}
    </div>
  );
}
