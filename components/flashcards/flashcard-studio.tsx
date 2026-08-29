"use client";

/**
 * The flashcard home.
 *
 * This screen used to force its own dark theme (`bg-[#080d1a] text-white`) with neon
 * cyan, violet and amber stat tiles — the same mistake the battles page made. It ignored
 * the design system entirely and looked like a different product, so it is rebuilt on
 * the shared tokens.
 *
 * Every figure shown comes from the API: cards due, bank size, recall rate and the
 * per-subject deck sizes. Where there is no evidence yet the tile says so ("No reviews
 * yet") rather than showing a confident-looking zero.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Play, Settings } from "lucide-react";

import { Axo, AxoError, AxoLoader } from "@/components/brand/axo";
import { Icon3D } from "@/components/brand/icon-3d";
import { MiniBars } from "@/components/ui/spark";
import { StatTile } from "@/components/ui/surface";
import { flashcardApi, type Flashcard, type FlashcardStats } from "@/lib/api";
import { CreateFlashcardModal } from "./create-flashcard-modal";
import { FlashcardDeckCard } from "./flashcard-deck-card";
import { FlashcardEmptyState } from "./flashcard-empty-state";

export function FlashcardStudio() {
  const [stats, setStats] = useState<FlashcardStats | null>(null);
  const [dueCards, setDueCards] = useState<Flashcard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [statsData, dueData] = await Promise.all([
        flashcardApi.getStats(),
        flashcardApi.getDue(),
      ]);
      setStats(statsData);
      setDueCards((dueData as any).results || (dueData as any) || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Could not load your flashcards.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const due = dueCards.length;
  const total = (stats as any)?.total_cards ?? 0;
  const retention = (stats as any)?.retention_rate;
  const reviews = (stats as any)?.total_reviews ?? 0;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <header className="flex items-start gap-4">
        <Icon3D name="flashcards" size="lg" />
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl tracking-tight sm:text-3xl">Flashcards</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Spaced repetition, fed by the questions you get wrong.
          </p>
        </div>
      </header>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <CreateFlashcardModal onCreated={loadData} />
        <Link
          href="/flashcards/manage"
          id="manage-flashcards-btn"
          className="press inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm"
        >
          <Settings className="size-4" />
          Manage
        </Link>
      </div>

      {loading ? (
        <AxoLoader label="Fetching your cards…" pose="flashcards" />
      ) : error ? (
        <AxoError description={error} onRetry={loadData} />
      ) : stats ? (
        <div className="mt-5 space-y-5">
          {/* Review CTA — the one thing worth doing on this screen. */}
          {due > 0 ? (
            <section className="flex items-center gap-4 rounded-2xl border border-primary/20 plinth p-5">
              {/* No ring here: "share of your cards that are due" is not a number anyone
                  acts on, and it reads 100% whenever every card happens to be due. The
                  headline below already carries the only figure that matters. */}
              <Axo pose="flashcards" size="sm" />
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
                  Ready to review
                </p>
                <h2 className="font-display text-xl leading-tight">
                  {due} card{due === 1 ? "" : "s"} due
                </h2>
                <Link
                  href="/flashcards/study"
                  id="start-review-session-btn"
                  className="press mt-2.5 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground"
                >
                  <Play className="size-4 fill-current" />
                  Start review
                </Link>
              </div>
            </section>
          ) : (
            <section className="flex items-center gap-4 rounded-2xl border border-mastery/25 bg-mastery/10 p-5">
              <Axo pose="celebrate" size="sm" />
              <div>
                <p className="font-display text-[15px]">All caught up</p>
                <p className="text-[13px] text-muted-foreground">
                  Nothing due right now — new cards appear as you get questions wrong.
                </p>
              </div>
            </section>
          )}

          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <StatTile
              label="Due now"
              value={due}
              tone={due ? "review" : "mastery"}
              icon={<Icon3D name="notification" size="sm" />}
            />
            <StatTile
              label="Total cards"
              value={total}
              icon={<Icon3D name="flashcards" size="sm" />}
            />
            <StatTile
              label="Recall"
              value={
                retention === null || retention === undefined
                  ? "—"
                  : `${Math.round(Number(retention))}%`
              }
              hint={reviews ? `${reviews} reviews` : "No reviews yet"}
              tone="mastery"
              icon={<Icon3D name="target" size="sm" />}
            />
            <StatTile
              label="Decks"
              value={stats.decks?.length ?? 0}
              icon={<Icon3D name="resource" size="sm" />}
            />
          </div>

          {/* Deck sizes at a glance — the shape tells you where your cards actually are. */}
          {stats.decks?.length > 1 && (
            <section className="card-3d p-4">
              <div className="flex items-baseline justify-between">
                <h2 className="font-display text-[15px]">Cards by subject</h2>
                <span className="text-[11px] text-muted-foreground tabular">
                  {total} total
                </span>
              </div>
              <MiniBars
                className="mt-3"
                values={stats.decks.map((d: any) => d.total_cards ?? d.card_count ?? 0)}
                tone="primary"
                height={34}
                label="Cards per subject"
              />
              <div className="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
                <span className="truncate">{(stats.decks[0] as any)?.subject_name}</span>
                <span className="truncate">
                  {(stats.decks[stats.decks.length - 1] as any)?.subject_name}
                </span>
              </div>
            </section>
          )}

          {stats.decks?.length > 0 ? (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                  Your decks
                </h2>
                <Link href="/flashcards/manage" className="text-[11px] text-primary">
                  View all
                </Link>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {stats.decks.map((deck: any) => (
                  <FlashcardDeckCard key={deck.subject_id} deck={deck} />
                ))}
              </div>
            </section>
          ) : (
            <FlashcardEmptyState mode="all" />
          )}
        </div>
      ) : (
        <FlashcardEmptyState mode="all" />
      )}
    </div>
  );
}
