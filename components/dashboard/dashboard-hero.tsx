"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, useInView, useSpring, useTransform } from "framer-motion";
import { ArrowRight, BookOpen, Flame, Play, Upload } from "lucide-react";
import { useAppSelector } from "@/store/hooks";
import { progressApi } from "@/lib/api";
import { canUploadMaterials } from "@/lib/guards";

/**
 * Dashboard hero, single focus: "Continue where you stopped".
 * The brief demands no exploration: when a student logs in, they should
 * be one click away from resuming. Streak is secondary, inline.
 */
export function DashboardHero() {
  const user = useAppSelector((s) => s.user);
  const [lastProgress, setLastProgress] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const canUpload = canUploadMaterials();

  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });
  const spring = useSpring(0, { stiffness: 60, damping: 20 });
  const width = useTransform(spring, (v) => `${v}%`);

  useEffect(() => {
    loadLastProgress();
  }, []);

  const loadLastProgress = async () => {
    try {
      const recentProgress = await progressApi.getRecentProgress();
      if (recentProgress && recentProgress.length > 0) {
        setLastProgress(recentProgress[0]);
      }
    } catch (error) {
      console.error("Failed to load progress:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (inView && lastProgress) {
      spring.set(lastProgress.progress_percentage || 0);
    }
  }, [inView, spring, lastProgress]);

  // Show upload prompt for class heads/material uploaders with no materials
  if (!loading && !lastProgress && canUpload) {
    return (
      <section
        ref={ref}
        aria-label="Get started"
        className="noise-overlay relative overflow-hidden rounded-2xl border border-border bg-card study-glow"
      >
        <div
          aria-hidden="true"
          className="ambient-orb pointer-events-none absolute inset-0 opacity-[0.55]"
          style={{
            background:
              "radial-gradient(60% 70% at 85% 0%, color-mix(in oklab, var(--learning) 22%, transparent), transparent 60%)",
          }}
        />

        <div className="relative grid gap-6 p-6 md:grid-cols-[1.6fr_1fr] md:items-center md:gap-10 md:p-8">
          <div className="min-w-0">
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="inline-flex items-center gap-2 rounded-full border border-learning/30 bg-learning/10 px-2.5 py-1 text-[11px] font-medium text-learning"
            >
              <Upload className="size-3" aria-hidden="true" />
              Get Started
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              className="mt-4 font-serif text-[28px] font-semibold leading-tight tracking-tight md:text-[32px]"
            >
              Upload Your First Material
            </motion.h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Share study materials with your class to get started
            </p>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                <Link
                  href="/materials/upload"
                  className="inline-flex h-11 items-center gap-2 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 transition-shadow hover:shadow-primary/40"
                >
                  <Upload className="size-4" aria-hidden="true" />
                  Upload Material
                </Link>
              </motion.div>
              <Link
                href="/materials"
                className="inline-flex h-11 items-center gap-2 rounded-full border border-border bg-card px-5 text-sm text-muted-foreground transition-colors hover:text-foreground hover:border-primary/50"
              >
                <BookOpen className="size-4" aria-hidden="true" />
                Browse Materials
              </Link>
            </div>
          </div>

          <motion.div
            className="grid grid-cols-1 gap-3 sm:grid-cols-2"
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, staggerChildren: 0.05 }}
          >
            <StreakTile />
            <StatTile
              label="Points"
              value={`${user.points}`}
              tone="learning"
              delay={0.25}
            />
            <StatTile label="Materials" value="0" tone="mastery" delay={0.3} />
            <StatTile
              label="Class rank"
              value={`#${user.rank}`}
              tone="review"
              delay={0.35}
            />
          </motion.div>
        </div>
      </section>
    );
  }

  // Show browse materials for students with no progress
  if (!loading && !lastProgress) {
    return (
      <section
        ref={ref}
        aria-label="Get started"
        className="noise-overlay relative overflow-hidden rounded-2xl border border-border bg-card study-glow"
      >
        <div
          aria-hidden="true"
          className="ambient-orb pointer-events-none absolute inset-0 opacity-[0.55]"
          style={{
            background:
              "radial-gradient(60% 70% at 85% 0%, color-mix(in oklab, var(--learning) 22%, transparent), transparent 60%)",
          }}
        />

        <div className="relative grid gap-6 p-6 md:grid-cols-[1.6fr_1fr] md:items-center md:gap-10 md:p-8">
          <div className="min-w-0">
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="inline-flex items-center gap-2 rounded-full border border-learning/30 bg-learning/10 px-2.5 py-1 text-[11px] font-medium text-learning"
            >
              <BookOpen className="size-3" aria-hidden="true" />
              Get Started
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              className="mt-4 font-serif text-[28px] font-semibold leading-tight tracking-tight md:text-[32px]"
            >
              Start Your Learning Journey
            </motion.h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Browse available materials and begin studying
            </p>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                <Link
                  href="/materials"
                  className="inline-flex h-11 items-center gap-2 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 transition-shadow hover:shadow-primary/40"
                >
                  <BookOpen className="size-4" aria-hidden="true" />
                  Browse Materials
                </Link>
              </motion.div>
              <Link
                href="/courses"
                className="inline-flex h-11 items-center gap-2 rounded-full border border-border bg-card px-5 text-sm text-muted-foreground transition-colors hover:text-foreground hover:border-primary/50"
              >
                All Courses
              </Link>
            </div>
          </div>

          <motion.div
            className="grid grid-cols-1 gap-3 sm:grid-cols-2"
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, staggerChildren: 0.05 }}
          >
            <StreakTile />
            <StatTile
              label="Points"
              value={`${user.points}`}
              tone="learning"
              delay={0.25}
            />
            <StatTile label="Progress" value="0%" tone="mastery" delay={0.3} />
            <StatTile
              label="Class rank"
              value={`#${user.rank}`}
              tone="review"
              delay={0.35}
            />
          </motion.div>
        </div>
      </section>
    );
  }

  // Show loading state
  if (loading) {
    return (
      <section
        ref={ref}
        className="noise-overlay relative overflow-hidden rounded-2xl border border-border bg-card study-glow"
      >
        <div className="relative p-6 md:p-8">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-muted rounded w-1/4"></div>
            <div className="h-8 bg-muted rounded w-3/4"></div>
            <div className="h-4 bg-muted rounded w-1/2"></div>
          </div>
        </div>
      </section>
    );
  }

  // Show continue where you stopped with actual progress
  return (
    <section
      ref={ref}
      aria-label="Continue where you stopped"
      className="noise-overlay relative overflow-hidden rounded-2xl border border-border bg-card study-glow"
    >
      <div
        aria-hidden="true"
        className="ambient-orb pointer-events-none absolute inset-0 opacity-[0.55]"
        style={{
          background:
            "radial-gradient(60% 70% at 85% 0%, color-mix(in oklab, var(--learning) 22%, transparent), transparent 60%)",
        }}
      />

      <div className="relative grid gap-6 p-6 md:grid-cols-[1.6fr_1fr] md:items-center md:gap-10 md:p-8">
        <div className="min-w-0">
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="inline-flex items-center gap-2 rounded-full border border-learning/30 bg-learning/10 px-2.5 py-1 text-[11px] font-medium text-learning"
          >
            <Play className="size-3" aria-hidden="true" />
            Continue where you stopped
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="mt-4 font-serif text-[28px] font-semibold leading-tight tracking-tight md:text-[32px]"
          >
            {lastProgress.slide_title}
          </motion.h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Page {lastProgress.current_page} of {lastProgress.total_pages}
          </p>

          <div className="mt-5 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <motion.div
                className="h-full rounded-full bg-learning"
                style={{ width }}
                aria-hidden="true"
              />
            </div>
            <span className="font-mono text-xs text-muted-foreground tabular-nums">
              {Math.round(lastProgress.progress_percentage)}%
            </span>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Link
                href={`/read?slide=${lastProgress.slide}`}
                className="inline-flex h-11 items-center gap-2 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 transition-shadow hover:shadow-primary/40"
              >
                Resume reading
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </motion.div>
            <Link
              href="/materials"
              className="inline-flex h-11 items-center gap-2 rounded-full border border-border bg-card px-5 text-sm text-muted-foreground transition-colors hover:text-foreground hover:border-primary/50"
            >
              <BookOpen className="size-4" aria-hidden="true" />
              All materials
            </Link>
          </div>
        </div>

        <motion.div
          className="grid grid-cols-1 gap-3 sm:grid-cols-2"
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2, staggerChildren: 0.05 }}
        >
          <StreakTile />
          <StatTile
            label="Points"
            value={`${user.points}`}
            tone="learning"
            delay={0.25}
          />
          <StatTile 
            label="Progress" 
            value={`${Math.round(lastProgress.progress_percentage)}%`} 
            tone="mastery" 
            delay={0.3} 
          />
          <StatTile
            label="Class rank"
            value={`#${user.rank}`}
            tone="review"
            delay={0.35}
          />
        </motion.div>
      </div>
    </section>
  );
}

function StreakTile() {
  const user = useAppSelector((s) => s.user);
  
  return (
    <motion.div
      whileHover={{ scale: 1.03, y: -1 }}
      className="relative col-span-2 cursor-default overflow-hidden rounded-xl border border-review/25 bg-review/10 p-4 transition-shadow hover:shadow-lg hover:shadow-review/10"
    >
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-review">
        <Flame className="size-3.5" aria-hidden="true" />
        Streak
      </div>
      <p className="mt-1.5 font-serif text-3xl font-semibold tracking-tight text-foreground">
        {user.streak} days
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Any small session today keeps it going.
      </p>
    </motion.div>
  );
}

function StatTile({
  label,
  value,
  tone,
  delay = 0,
}: {
  label: string;
  value: string;
  tone: "learning" | "mastery" | "review";
  delay?: number;
}) {
  const toneClass =
    tone === "mastery"
      ? "text-mastery"
      : tone === "review"
        ? "text-review"
        : "text-learning";
  const shadowClass =
    tone === "mastery"
      ? "hover:shadow-mastery/15"
      : tone === "review"
        ? "hover:shadow-review/15"
        : "hover:shadow-learning/15";
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay }}
      whileHover={{ scale: 1.05, y: -2 }}
      className={`cursor-default rounded-xl border border-border bg-background/40 p-4 transition-shadow hover:shadow-lg ${shadowClass}`}
    >
      <p
        className={`text-[10px] font-semibold uppercase tracking-widest ${toneClass}`}
      >
        {label}
      </p>
      <p className="mt-1.5 font-serif text-xl font-semibold tracking-tight">
        {value}
      </p>
    </motion.div>
  );
}
