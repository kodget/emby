"use client";

/**
 * Axo — the Emby mascot, and the components that put him to work.
 *
 * The mascot is not decoration. He carries the app's loading, empty, error and success
 * moments, which are exactly the moments where a study app usually shows a bare spinner
 * or a grey box. Each component here pairs a pose with the right message so those states
 * feel authored rather than left over.
 *
 *   <Axo pose="thinking" size="md" />     raw mascot
 *   <AxoLoader label="Building your quiz" />
 *   <AxoEmpty title="No decks yet" ... />
 *   <AxoError onRetry={...} />
 *   <AxoCelebrate score={82} />
 */

import Image from "next/image";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

import { type AxoPose, LOADING_LINES, mascotSrc } from "@/lib/brand";
import { cn } from "@/lib/utils";

const SIZES = {
  xs: 32,
  sm: 48,
  md: 80,
  lg: 128,
  xl: 180,
  hero: 260,
} as const;

export type AxoSize = keyof typeof SIZES;

type AxoProps = {
  pose?: AxoPose;
  size?: AxoSize;
  className?: string;
  /** Gentle idle float. Disabled automatically when the OS asks for reduced motion. */
  float?: boolean;
  priority?: boolean;
  alt?: string;
};

export function Axo({
  pose = "hero",
  size = "md",
  className,
  float = false,
  priority = false,
  alt,
}: AxoProps) {
  const reduce = useReducedMotion();
  const px = SIZES[size];
  const shouldFloat = float && !reduce;

  const image = (
    <Image
      src={mascotSrc(pose)}
      alt={alt ?? "Axo, the Emby mascot"}
      width={px}
      height={px}
      priority={priority}
      className="select-none object-contain"
      draggable={false}
      // The mascot is atmosphere in most placements; announce it only when it carries
      // meaning the surrounding text does not already convey.
      aria-hidden={alt ? undefined : true}
    />
  );

  if (!shouldFloat) {
    return <div className={cn("shrink-0", className)}>{image}</div>;
  }

  return (
    <motion.div
      className={cn("shrink-0", className)}
      animate={{ y: [0, -7, 0] }}
      transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
    >
      {image}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ loading */

type AxoLoaderProps = {
  label?: string;
  /** Cycle through the stock lines rather than showing a fixed one. */
  rotate?: boolean;
  size?: AxoSize;
  className?: string;
  pose?: AxoPose;
};

/**
 * The app's standard busy state.
 *
 * Long waits get a rotating line so the screen still feels alive after a few seconds,
 * which matters because question generation and AI replies are genuinely slow.
 */
export function AxoLoader({
  label,
  rotate = true,
  size = "md",
  className,
  pose = "thinking",
}: AxoLoaderProps) {
  const [index, setIndex] = useState(0);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!rotate || label) return;
    const id = setInterval(() => setIndex((i) => i + 1), 2600);
    return () => clearInterval(id);
  }, [rotate, label]);

  const text = label ?? LOADING_LINES[index % LOADING_LINES.length];

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 py-10 text-center",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <motion.div
        animate={reduce ? undefined : { y: [0, -8, 0], rotate: [-2, 2, -2] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
      >
        <Axo pose={pose} size={size} />
      </motion.div>

      <motion.p
        key={text}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-sm text-muted-foreground"
      >
        {text}
      </motion.p>

      <span className="sr-only">Loading</span>

      <div className="flex gap-1.5" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="size-1.5 rounded-full bg-primary/60"
            animate={reduce ? undefined : { opacity: [0.25, 1, 0.25] }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              delay: i * 0.18,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
    </div>
  );
}

/** Compact inline spinner for buttons and toolbars. */
export function AxoSpinner({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.span
      className={cn("inline-flex", className)}
      animate={reduce ? undefined : { rotate: [0, -8, 8, 0] }}
      transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
    >
      <Axo pose="thinking" size="xs" />
    </motion.span>
  );
}

/* -------------------------------------------------------------------- empty */

type AxoEmptyProps = {
  title: string;
  description?: string;
  pose?: AxoPose;
  action?: React.ReactNode;
  className?: string;
};

export function AxoEmpty({
  title,
  description,
  pose = "empty",
  action,
  className,
}: AxoEmptyProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 px-6 py-14 text-center",
        className,
      )}
    >
      <Axo pose={pose} size="lg" float />
      <div className="space-y-1.5">
        <h3 className="font-display text-lg font-semibold tracking-tight">{title}</h3>
        {description && (
          <p className="mx-auto max-w-sm text-pretty text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}

/* -------------------------------------------------------------------- error */

export function AxoError({
  title = "That didn't work",
  description = "Something went wrong on our side. Try again in a moment.",
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 px-6 py-12 text-center",
        className,
      )}
      role="alert"
    >
      <Axo pose="oops" size="lg" />
      <div className="space-y-1.5">
        <h3 className="font-display text-lg font-semibold tracking-tight">{title}</h3>
        <p className="mx-auto max-w-sm text-pretty text-sm text-muted-foreground">
          {description}
        </p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-full bg-primary px-5 py-2 text-sm font-medium text-primary-foreground transition-transform active:scale-95"
        >
          Try again
        </button>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- celebrate */

/**
 * Shown after a finished quiz, session or battle. The pose shifts with the result so a
 * weak score gets encouragement rather than confetti.
 */
export function AxoCelebrate({
  score,
  title,
  description,
  className,
  children,
}: {
  score?: number;
  title?: string;
  description?: string;
  className?: string;
  children?: React.ReactNode;
}) {
  const strong = score === undefined || score >= 70;
  const pose: AxoPose = strong ? "celebrate" : "heart";
  const heading =
    title ?? (strong ? "Nicely done" : "Good effort — keep going");

  return (
    <div
      className={cn("flex flex-col items-center gap-4 py-8 text-center", className)}
    >
      <motion.div
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 18 }}
      >
        <Axo pose={pose} size="xl" />
      </motion.div>
      <div className="space-y-1.5">
        <h2 className="font-display text-2xl font-semibold tracking-tight">{heading}</h2>
        {description && (
          <p className="mx-auto max-w-sm text-pretty text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}
