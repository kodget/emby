"use client";

/**
 * The practice launcher.
 *
 * A phone app puts its verbs on the home screen. This is that: a grid of large, tappable
 * tiles for the six things a student comes to Emby to do, each carrying its own 3D icon
 * so the grid is scannable by shape rather than by reading every label.
 *
 * Two columns on phones (thumb-sized targets), three from `sm` up.
 */

import Link from "next/link";
import { motion } from "framer-motion";

import { Icon3D } from "@/components/brand/icon-3d";
import type { IconName } from "@/lib/brand";
import { cn } from "@/lib/utils";

type Action = {
  label: string;
  sublabel: string;
  href: string;
  icon: IconName;
  tone: "primary" | "mastery" | "review" | "weakness";
};

const ACTIONS: Action[] = [
  { label: "Read", sublabel: "Slides & notes", href: "/courses", icon: "read", tone: "primary" },
  { label: "Quiz", sublabel: "MCQ & theory", href: "/quiz", icon: "quiz", tone: "mastery" },
  { label: "Steeplechase", sublabel: "30s stations", href: "/steeplechase", icon: "steeplechase", tone: "weakness" },
  { label: "Histology", sublabel: "Spot the tissue", href: "/histology", icon: "histology", tone: "primary" },
  { label: "Flashcards", sublabel: "Due for review", href: "/flashcards", icon: "flashcards", tone: "review" },
  { label: "Brain Battle", sublabel: "Play a friend", href: "/battles", icon: "battle", tone: "mastery" },
];

const TONE_RING: Record<Action["tone"], string> = {
  primary: "hover:border-primary/35",
  mastery: "hover:border-mastery/35",
  review: "hover:border-review/35",
  weakness: "hover:border-weakness/35",
};

export function QuickActions({ className }: { className?: string }) {
  return (
    <section className={className} aria-labelledby="quick-actions-heading">
      <h2
        id="quick-actions-heading"
        className="px-1 pb-2.5 text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
      >
        Jump back in
      </h2>

      <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
        {ACTIONS.map((action, i) => (
          <motion.li
            key={action.href}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04, duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
          >
            <Link
              href={action.href}
              className={cn(
                "press card-3d card-3d-hover flex h-full flex-col items-start gap-2.5 p-3.5 transition-colors sm:p-4",
                TONE_RING[action.tone],
              )}
            >
              <Icon3D name={action.icon} size="md" />
              <span className="min-w-0">
                <span className="block truncate font-display text-[15px] font-semibold leading-tight">
                  {action.label}
                </span>
                <span className="block truncate text-[11px] leading-tight text-muted-foreground">
                  {action.sublabel}
                </span>
              </span>
            </Link>
          </motion.li>
        ))}
      </ul>
    </section>
  );
}
