"use client";

/**
 * Surface — the app's card primitive.
 *
 * Emby's cards previously all had the same flat weight, which is what made a dashboard
 * of ten widgets read as an undifferentiated pile. Surface gives them a deliberate
 * hierarchy instead:
 *
 *   tone="raised"   the default object on the canvas
 *   tone="flat"     supporting content that should recede
 *   tone="feature"  a single primary action, tinted and lifted
 *   tone="inset"    a well *inside* another surface
 *
 * `interactive` adds hover lift and press feedback, so a tappable card behaves like a
 * physical control on both mouse and touch.
 */

import * as React from "react";

import { cn } from "@/lib/utils";

type SurfaceTone = "raised" | "flat" | "feature" | "inset";

const TONES: Record<SurfaceTone, string> = {
  raised: "card-3d",
  flat: "rounded-[var(--radius)] border border-border/70 bg-card/60",
  feature:
    "rounded-[var(--radius)] border border-primary/20 plinth depth-3 text-foreground",
  inset:
    "rounded-[var(--radius-md)] border border-border/60 bg-secondary/40 shadow-[inset_0_1px_2px_0_color-mix(in_oklab,var(--foreground)_6%,transparent)]",
};

export interface SurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: SurfaceTone;
  interactive?: boolean;
  as?: "div" | "section" | "article" | "li";
}

export const Surface = React.forwardRef<HTMLDivElement, SurfaceProps>(
  ({ className, tone = "raised", interactive = false, as = "div", ...props }, ref) => {
    // `as` lets a card be a <li> inside a list without losing its styling. React can't
    // narrow the union of intrinsic element props here, so the tag is widened once.
    const Tag = as as React.ElementType;
    return (
      <Tag
        ref={ref}
        className={cn(
          TONES[tone],
          interactive && "press card-3d-hover cursor-pointer",
          className,
        )}
        {...props}
      />
    );
  },
);
Surface.displayName = "Surface";

/** Standard card header: an optional leading visual, a title, and trailing actions. */
export function SurfaceHeader({
  title,
  description,
  icon,
  action,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start gap-3", className)}>
      {icon && <span className="shrink-0">{icon}</span>}
      <div className="min-w-0 flex-1">
        <h2 className="font-display text-base font-semibold leading-tight tracking-tight">
          {title}
        </h2>
        {description && (
          <p className="mt-0.5 text-pretty text-[13px] leading-snug text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/**
 * A single headline number.
 *
 * Values use tabular figures so a row of tiles does not jitter as numbers update, and
 * the label sits above the value so the eye lands on the number first.
 */
export function StatTile({
  label,
  value,
  hint,
  icon,
  tone = "neutral",
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: "neutral" | "mastery" | "review" | "weakness" | "primary";
  className?: string;
}) {
  const accent = {
    neutral: "text-foreground",
    primary: "text-primary",
    mastery: "text-mastery",
    review: "text-review",
    weakness: "text-weakness",
  }[tone];

  return (
    <div className={cn("card-3d flex items-center gap-3 p-3.5", className)}>
      {icon && <span className="shrink-0">{icon}</span>}
      <div className="min-w-0">
        <p className="truncate text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          {label}
        </p>
        <p className={cn("font-display text-xl font-semibold leading-tight tabular", accent)}>
          {value}
        </p>
        {hint && (
          <p className="truncate text-[11px] leading-tight text-muted-foreground">{hint}</p>
        )}
      </div>
    </div>
  );
}

/** Loading placeholder shaped like a Surface, so layouts don't jump when data lands. */
export function SurfaceSkeleton({
  className,
  lines = 3,
}: {
  className?: string;
  lines?: number;
}) {
  return (
    <div className={cn("card-3d space-y-3 p-5", className)} aria-hidden="true">
      <div className="skeleton h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton h-3"
          style={{ width: `${88 - i * 14}%` }}
        />
      ))}
    </div>
  );
}
