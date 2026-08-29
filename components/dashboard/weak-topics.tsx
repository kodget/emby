"use client";

/**
 * What to revise next.
 *
 * The previous version tried to infer weak topics in the browser by looping over every
 * block and guessing which slide belonged to which topic — its own comment said
 * "you may need to adjust this logic". It now reads the weak-area engine, which derives
 * mastery from actual answers across quizzes, Steeplechase, Histology and battles.
 *
 * Each row shows a mastery bar so the card carries information at a glance rather than
 * being a list of names.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { Axo } from "@/components/brand/axo";
import { Icon3D } from "@/components/brand/icon-3d";
import { learningApi } from "@/lib/api";
import { cn } from "@/lib/utils";

type Area = {
  label: string;
  attempted: number;
  correct: number;
  mastery: number;
  priority: number;
};

export function WeakTopics() {
  const [areas, setAreas] = useState<Area[]>([]);
  const [hasData, setHasData] = useState(false);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Sub-block is the level students actually revise at.
        const data = await learningApi.getWeakAreas("SUB_BLOCK", 4);
        if (cancelled) return;
        setAreas(data.weakest ?? []);
        setHasData(Boolean(data.has_data));
        setState("ready");
      } catch {
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") {
    return (
      <section className="card-3d p-4" aria-busy="true">
        <div className="skeleton h-4 w-32" />
        <div className="skeleton mt-4 h-3 w-full" />
        <div className="skeleton mt-2 h-3 w-4/5" />
      </section>
    );
  }

  if (state === "error") return null;

  return (
    <section className="card-3d flex flex-col p-4">
      <div className="flex items-start gap-3">
        <Icon3D name="target" size="sm" />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-[15px] leading-tight">What to revise</h2>
          <p className="text-[11px] text-muted-foreground">Weakest first</p>
        </div>
        {areas.length > 0 && (
          <Link
            href="/analytics"
            className="press shrink-0 rounded-full bg-secondary px-3 py-1 text-[11px] font-medium text-muted-foreground"
          >
            All
          </Link>
        )}
      </div>

      {areas.length === 0 ? (
        <div className="flex items-center gap-3 py-3">
          <Axo pose="sleeping" size="sm" />
          <p className="text-[13px] leading-snug text-muted-foreground">
            {hasData
              ? "Not enough answers in any one topic yet to call it weak."
              : "Answer a few questions and your weak topics will show up here."}
          </p>
        </div>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {areas.map((area, i) => {
            const pct = Math.round(area.mastery * 100);
            const tone =
              area.mastery < 0.4 ? "weakness" : area.mastery < 0.7 ? "review" : "mastery";
            return (
              <li key={area.label}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="min-w-0 flex-1 truncate text-[13px]">{area.label}</span>
                  <span
                    className={cn(
                      "shrink-0 font-mono text-[11px] tabular",
                      tone === "weakness" && "text-weakness",
                      tone === "review" && "text-review",
                      tone === "mastery" && "text-mastery",
                    )}
                  >
                    {pct}%
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-secondary">
                  <motion.div
                    className={cn(
                      "h-full rounded-full",
                      tone === "weakness" && "bg-weakness",
                      tone === "review" && "bg-review",
                      tone === "mastery" && "bg-mastery",
                    )}
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.max(4, pct)}%` }}
                    transition={{ delay: i * 0.07, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                  />
                </div>
                <p className="mt-0.5 text-[10px] text-muted-foreground tabular">
                  {area.correct}/{area.attempted} correct
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
