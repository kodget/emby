"use client";

/**
 * Icon3D — the generated 3D clay icon set.
 *
 * These replace the emoji and generic glyphs that were scattered through the app. They
 * are deliberately *not* a replacement for small line icons: at 16-20px a rendered 3D
 * object turns to mush, so Lucide still handles dense UI affordances. Use Icon3D where
 * an icon is a feature's identity — nav tiles, section headers, stat cards, empty states.
 */

import Image from "next/image";

import { type IconName, iconSrc } from "@/lib/brand";
import { cn } from "@/lib/utils";

const SIZES = {
  xs: 20,
  sm: 28,
  md: 40,
  lg: 56,
  xl: 80,
} as const;

export type Icon3DSize = keyof typeof SIZES;

type Icon3DProps = {
  name: IconName;
  size?: Icon3DSize;
  className?: string;
  /** Supply when the icon is the only thing conveying meaning. */
  label?: string;
  priority?: boolean;
};

export function Icon3D({
  name,
  size = "md",
  className,
  label,
  priority = false,
}: Icon3DProps) {
  const px = SIZES[size];
  return (
    <Image
      src={iconSrc(name)}
      alt={label ?? ""}
      width={px}
      height={px}
      priority={priority}
      draggable={false}
      aria-hidden={label ? undefined : true}
      className={cn("select-none object-contain", className)}
    />
  );
}

/**
 * An icon seated on a tinted, softly-lit plinth.
 *
 * Gives feature tiles a consistent physical footing so a grid of them reads as one set
 * rather than a pile of stickers.
 */
export function Icon3DTile({
  name,
  size = "md",
  tone = "primary",
  className,
  label,
}: Icon3DProps & { tone?: "primary" | "mastery" | "review" | "weakness" | "neutral" }) {
  const toneClass = {
    primary: "from-primary/14 to-primary/5 ring-primary/15",
    mastery: "from-mastery/16 to-mastery/5 ring-mastery/15",
    review: "from-review/18 to-review/6 ring-review/15",
    weakness: "from-weakness/14 to-weakness/5 ring-weakness/15",
    neutral: "from-foreground/8 to-foreground/3 ring-foreground/10",
  }[tone];

  const pad = { xs: "p-1.5", sm: "p-2", md: "p-2.5", lg: "p-3", xl: "p-4" }[size];

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-2xl bg-gradient-to-br ring-1 ring-inset",
        "shadow-[inset_0_1px_0_0_rgba(255,255,255,0.6)]",
        toneClass,
        pad,
        className,
      )}
    >
      <Icon3D name={name} size={size} label={label} />
    </span>
  );
}
