"use client";

/**
 * The dashboard's opening band: who you are, how you're doing, and Axo.
 *
 * This replaces a stack of same-weight widgets with one clear entry point. The greeting
 * carries the AI message (cached server-side for six hours, so it no longer changes on
 * every reload), and the stat rail shows the four numbers a student actually checks:
 * streak, XP, AI credits and cards due.
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { Axo } from "@/components/brand/axo";
import { Icon3D } from "@/components/brand/icon-3d";
import { StatTile } from "@/components/ui/surface";
import { useAppSelector } from "@/store/hooks";

type Snapshot = {
  streak: number;
  xp: number;
  creditsRemaining: number | null;
  cardsDue: number | null;
};

function greeting(date = new Date()): string {
  const h = date.getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function DashboardHeader({
  message,
  snapshot,
  loading = false,
}: {
  message?: { headline?: string; body?: string } | null;
  snapshot?: Partial<Snapshot>;
  loading?: boolean;
}) {
  const name = useAppSelector((s) => s.user.name) || "";
  const storeStreak = useAppSelector((s) => s.user.streak) || 0;
  const [mounted, setMounted] = useState(false);

  // Greeting depends on local time, so render it only after hydration to avoid a
  // server/client mismatch.
  useEffect(() => setMounted(true), []);

  // The profile may not have resolved yet, so the headline has to read correctly with
  // no name at all rather than greeting an empty string.
  const firstName = name.trim().split(/\s+/)[0];
  const fallbackHeadline = firstName ? `${firstName}, ready to study?` : "Ready to study?";
  const streak = snapshot?.streak ?? storeStreak;

  return (
    <section className="relative overflow-hidden rounded-[calc(var(--radius)+6px)] border border-primary/15 plinth depth-3">
      {/* Soft ambient wash behind the greeting */}
      <div
        aria-hidden="true"
        className="ambient-orb pointer-events-none absolute -right-16 -top-24 size-72 rounded-full opacity-60 blur-3xl"
        style={{
          background:
            "radial-gradient(circle, color-mix(in oklab, var(--primary) 32%, transparent), transparent 70%)",
        }}
      />

      <div className="relative flex items-start gap-4 p-5 sm:p-6">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-primary">
            {mounted ? greeting() : "Welcome back"}
          </p>

          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight sm:text-3xl">
            {message?.headline || fallbackHeadline}
          </h1>

          {loading ? (
            <div className="mt-2.5 space-y-2" aria-hidden="true">
              <div className="skeleton h-3 w-4/5" />
              <div className="skeleton h-3 w-3/5" />
            </div>
          ) : (
            message?.body && (
              <motion.p
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-2 max-w-xl text-pretty text-sm leading-relaxed text-muted-foreground"
              >
                {message.body}
              </motion.p>
            )
          )}
        </div>

        {/* Axo waves from the corner at a size that suits the viewport, so the
            mascot is present on phones without crowding the greeting. */}
        <Axo pose="hero" size="md" float priority className="sm:hidden" />
        <Axo pose="hero" size="lg" float priority className="hidden sm:block" />
      </div>

      <div className="relative grid grid-cols-2 gap-2.5 px-5 pb-5 sm:grid-cols-4 sm:px-6 sm:pb-6">
        <StatTile
          label="Streak"
          value={`${streak}d`}
          icon={<Icon3D name="streak" size="sm" />}
          tone="review"
        />
        <StatTile
          label="XP"
          value={snapshot?.xp?.toLocaleString() ?? "—"}
          icon={<Icon3D name="xp" size="sm" />}
          tone="primary"
        />
        <StatTile
          label="AI credits"
          value={snapshot?.creditsRemaining ?? "—"}
          icon={<Icon3D name="credits" size="sm" />}
        />
        <StatTile
          label="Cards due"
          value={snapshot?.cardsDue ?? "—"}
          icon={<Icon3D name="flashcards" size="sm" />}
          tone={snapshot?.cardsDue ? "weakness" : "mastery"}
        />
      </div>
    </section>
  );
}
