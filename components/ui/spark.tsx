"use client";

/**
 * Small data marks for cards.
 *
 * These exist so a card can *show* something rather than just state a number. Every one
 * of them takes real series data — none of them invent or pad values, and each renders a
 * deliberate empty state when there is nothing to plot, because a flat line drawn from
 * zeros reads as "you did nothing" rather than "no data yet".
 *
 * Conventions, applied consistently so a screen of these reads as one system:
 *   - thin marks, 2px strokes, rounded ends
 *   - recessive or absent grid; the shape carries the meaning
 *   - the latest point is emphasised, nothing else is labelled
 *   - colour is status or single-hue, never a rainbow
 */

import { useId } from "react";

import { cn } from "@/lib/utils";

type Tone = "primary" | "mastery" | "review" | "weakness";

const STROKE: Record<Tone, string> = {
  primary: "var(--primary)",
  mastery: "var(--mastery)",
  review: "var(--review)",
  weakness: "var(--weakness)",
};

/* ------------------------------------------------------------------ sparkline */

export function Sparkline({
  values,
  tone = "primary",
  height = 36,
  className,
  label,
}: {
  values: number[];
  tone?: Tone;
  height?: number;
  className?: string;
  label?: string;
}) {
  const id = useId();
  const stroke = STROKE[tone];

  if (!values.length || values.every((v) => v === 0)) {
    return (
      <div
        className={cn("flex items-center text-[11px] text-muted-foreground", className)}
        style={{ height }}
      >
        No activity yet
      </div>
    );
  }

  const w = 100;
  const h = height;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const step = values.length > 1 ? w / (values.length - 1) : w;

  const pts = values.map((v, i) => {
    const x = i * step;
    // Leave 3px of headroom so the stroke is never clipped by the viewBox.
    const y = h - 3 - ((v - min) / span) * (h - 6);
    return [x, y] as const;
  });

  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${w},${h} L0,${h} Z`;
  const [lastX, lastY] = pts[pts.length - 1];

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className={cn("w-full", className)}
      style={{ height }}
      role="img"
      aria-label={label ?? "Trend"}
    >
      <defs>
        <linearGradient id={`sp-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sp-${id})`} />
      <path
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {/* Only the newest point is marked — a dot on every point is noise. */}
      <circle cx={lastX} cy={lastY} r="2.5" fill={stroke} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/* --------------------------------------------------------------- daily tracker */

export type DayPoint = { date: string; value: number };

/**
 * The daily tracker: one cell per day, intensity by effort.
 *
 * This is the piece that makes consistency legible at a glance — the gaps are the
 * information, so days with nothing are drawn as empty cells rather than skipped.
 */
export function DailyTracker({
  days,
  tone = "primary",
  className,
  weekLabels = true,
}: {
  days: DayPoint[];
  tone?: Tone;
  className?: string;
  weekLabels?: boolean;
}) {
  if (!days.length) {
    return (
      <p className={cn("text-[11px] text-muted-foreground", className)}>
        Your daily activity will appear here.
      </p>
    );
  }

  const max = Math.max(...days.map((d) => d.value), 1);
  const stroke = STROKE[tone];

  const intensity = (v: number) => {
    if (v <= 0) return 0;
    const ratio = v / max;
    // Four visible steps: anything done at all is clearly not "nothing".
    if (ratio > 0.66) return 1;
    if (ratio > 0.33) return 0.72;
    return 0.42;
  };

  return (
    <div className={className}>
      <div className="flex flex-wrap gap-[3px]" role="img" aria-label="Daily activity">
        {days.map((d) => {
          const a = intensity(d.value);
          return (
            <span
              key={d.date}
              title={`${d.date}: ${d.value > 0 ? `${d.value} min` : "nothing"}`}
              className="size-[13px] rounded-[3px] transition-transform hover:scale-125"
              style={{
                backgroundColor: a ? stroke : "var(--secondary)",
                opacity: a || 1,
              }}
            />
          );
        })}
      </div>
      {weekLabels && (
        <div className="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
          <span>{days[0]?.date.slice(5)}</span>
          <span>{days[days.length - 1]?.date.slice(5)}</span>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ ring gauge */

export function ProgressRing({
  value,
  size = 56,
  tone = "primary",
  label,
  sublabel,
  className,
}: {
  /** 0..1 */
  value: number | null;
  size?: number;
  tone?: Tone;
  label?: string;
  sublabel?: string;
  className?: string;
}) {
  const stroke = STROKE[tone];
  const r = (size - 7) / 2;
  const c = 2 * Math.PI * r;
  const pct = value === null ? 0 : Math.max(0, Math.min(1, value));

  return (
    <div className={cn("relative inline-flex shrink-0", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} role="img" aria-label={label ?? "Progress"}>
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="var(--secondary)" strokeWidth="5"
        />
        {value !== null && (
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke={stroke} strokeWidth="5" strokeLinecap="round"
            strokeDasharray={`${c * pct} ${c}`}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        )}
      </svg>
      <span className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="font-mono text-[13px] font-medium tabular">
          {value === null ? "—" : `${Math.round(pct * 100)}`}
        </span>
        {sublabel && <span className="text-[8px] text-muted-foreground">{sublabel}</span>}
      </span>
    </div>
  );
}

/* -------------------------------------------------------------------- mini bars */

export function MiniBars({
  values,
  tone = "primary",
  height = 28,
  className,
  label,
}: {
  values: number[];
  tone?: Tone;
  height?: number;
  className?: string;
  label?: string;
}) {
  if (!values.length) return null;
  const max = Math.max(...values, 1);
  const stroke = STROKE[tone];

  return (
    <div
      className={cn("flex items-end gap-[2px]", className)}
      style={{ height }}
      role="img"
      aria-label={label ?? "Recent activity"}
    >
      {values.map((v, i) => (
        <span
          key={i}
          className="flex-1 rounded-t-[2px]"
          style={{
            height: v > 0 ? `${Math.max(12, (v / max) * 100)}%` : "3px",
            backgroundColor: v > 0 ? stroke : "var(--border)",
            opacity: v > 0 ? 0.35 + 0.65 * (v / max) : 1,
          }}
        />
      ))}
    </div>
  );
}
