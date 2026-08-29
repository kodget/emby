"use client";

/**
 * The practice landing.
 *
 * The previous version was four full-width cards, each roughly a phone screen tall, with
 * an icon, a sentence and a coloured button — a lot of scrolling for four links and no
 * information. It also advertised Histology as "Coming soon" behind a toast, which had
 * stopped being true.
 *
 * This version is a dense grid where every tile carries a real number: how much of the
 * question bank you have seen, how many questions you have actually missed, how many
 * Steeplechase and Histology stations are available and how many rounds you have left.
 * Tiles with nothing behind them say so instead of leading to an empty screen.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Settings } from "lucide-react";

import { Axo } from "@/components/brand/axo";
import { Icon3D } from "@/components/brand/icon-3d";
import { ProgressRing } from "@/components/ui/spark";
import { analyticsApi, practiceApi, type PracticeEntitlement } from "@/lib/api";
import { cn } from "@/lib/utils";

type Stats = {
  bankSeen: number;
  bankTotal: number;
  missed: number;
  accuracy: number | null;
  steeplechase: { stations: number; remaining: number | null; premium: boolean } | null;
  histology: { stations: number; remaining: number | null; premium: boolean } | null;
};

export function PracticeArena({
  onMissedQuestions,
  creatingMissed,
  onAdvanced,
}: {
  onMissedQuestions: () => void;
  creatingMissed: boolean;
  onAdvanced: () => void;
}) {
  const [stats, setStats] = useState<Partial<Stats>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Each source is independent so one failure cannot blank the whole screen.
      const [report, steeple, histo] = await Promise.allSettled([
        analyticsApi.getReport(30),
        practiceApi.getOptions("STEEPLECHASE"),
        practiceApi.getOptions("HISTOLOGY"),
      ]);
      if (cancelled) return;

      const asMode = (r: PromiseSettledResult<{ entitlement: PracticeEntitlement }>) =>
        r.status === "fulfilled"
          ? {
              stations: r.value.entitlement.stations_available,
              remaining: r.value.entitlement.rounds_remaining,
              premium: r.value.entitlement.is_premium,
            }
          : null;

      setStats({
        bankSeen: report.status === "fulfilled" ? report.value.question_bank?.seen ?? 0 : 0,
        bankTotal: report.status === "fulfilled" ? report.value.question_bank?.total ?? 0 : 0,
        missed: report.status === "fulfilled" ? report.value.question_bank?.missed ?? 0 : 0,
        accuracy: report.status === "fulfilled" ? report.value.overview.accuracy : null,
        steeplechase: asMode(steeple),
        histology: asMode(histo),
      });
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const rounds = (m: Stats["steeplechase"]) =>
    !m ? "" : m.premium ? "Unlimited rounds" : `${m.remaining ?? 0} free rounds left`;

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
      <header className="flex items-start gap-4">
        <Icon3D name="quiz" size="lg" />
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl tracking-tight sm:text-3xl">Practice</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {stats.accuracy !== null && stats.accuracy !== undefined
              ? `You're at ${Math.round(stats.accuracy * 100)}% over the last 30 days.`
              : "Pick a way in."}
          </p>
        </div>
        <Axo pose="clipboard" size="md" float className="hidden sm:block" />
      </header>

      {/* Coverage — the single most useful thing to know before practising. */}
      <section className="card-3d mt-5 flex items-center gap-4 p-4">
        <ProgressRing
          value={stats.bankTotal ? (stats.bankSeen ?? 0) / stats.bankTotal : null}
          tone="primary"
          sublabel="%"
          label="Share of the question bank seen"
        />
        <div className="min-w-0 flex-1">
          <p className="font-display text-[15px] leading-tight">Question bank</p>
          <p className="mt-0.5 text-[13px] text-muted-foreground tabular">
            {loading
              ? "Checking…"
              : stats.bankTotal
                ? `${stats.bankSeen} of ${stats.bankTotal} seen · ${stats.missed} missed at least once`
                : "No questions generated yet — upload a slide to build the bank."}
          </p>
        </div>
      </section>

      <div className="mt-4 grid gap-2.5 sm:grid-cols-2">
        <ActionTile
          icon="target"
          title="Your mistakes"
          detail={
            loading
              ? "Checking…"
              : stats.missed
                ? `${stats.missed} question${stats.missed === 1 ? "" : "s"} to revisit`
                : "Nothing missed yet"
          }
          disabled={!loading && !stats.missed}
          busy={creatingMissed}
          onClick={onMissedQuestions}
        />

        <ActionTile
          icon="quiz"
          title="Custom quiz"
          detail="Pick subject, type and length"
          onClick={onAdvanced}
        />

        <ActionTile
          icon="steeplechase"
          title="Steeplechase"
          detail={
            loading
              ? "Checking…"
              : stats.steeplechase?.stations
                ? `${stats.steeplechase.stations} station${stats.steeplechase.stations === 1 ? "" : "s"} · ${rounds(stats.steeplechase)}`
                : "No approved stations yet"
          }
          href="/steeplechase"
          disabled={!loading && !stats.steeplechase?.stations}
        />

        <ActionTile
          icon="histology"
          title="Histology"
          detail={
            loading
              ? "Checking…"
              : stats.histology?.stations
                ? `${stats.histology.stations} slide${stats.histology.stations === 1 ? "" : "s"} · ${rounds(stats.histology)}`
                : "No approved slides yet"
          }
          href="/histology"
          disabled={!loading && !stats.histology?.stations}
        />
      </div>

      <button
        type="button"
        onClick={onAdvanced}
        className="press mt-5 flex w-full items-center justify-center gap-2 rounded-full border border-border bg-card py-3 text-sm text-muted-foreground"
      >
        <Settings className="size-4" />
        Advanced quiz configurator
      </button>
    </div>
  );
}

function ActionTile({
  icon,
  title,
  detail,
  href,
  onClick,
  disabled = false,
  busy = false,
}: {
  icon: "target" | "quiz" | "steeplechase" | "histology";
  title: string;
  detail: string;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  busy?: boolean;
}) {
  const inner = (
    <>
      <Icon3D name={icon} size="md" />
      <span className="min-w-0 flex-1">
        <span className="block font-display text-[15px] leading-tight">{title}</span>
        <span className="block truncate text-[12px] text-muted-foreground tabular">
          {busy ? "Building your set…" : detail}
        </span>
      </span>
    </>
  );

  const classes = cn(
    "card-3d flex w-full items-center gap-3 p-3.5 text-left",
    disabled ? "cursor-not-allowed opacity-55" : "press card-3d-hover",
  );

  const body = (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      className="contents"
    >
      {inner}
    </motion.div>
  );

  if (href && !disabled) {
    return (
      <Link href={href} className={classes}>
        {body}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} disabled={disabled || busy} className={classes}>
      {body}
    </button>
  );
}
