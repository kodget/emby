"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { BookOpen, Play, Plus, Settings, PartyPopper } from "lucide-react";
import { flashcardApi, type Flashcard, type FlashcardStats } from "@/lib/api";
import { FlashcardStatsBar } from "./flashcard-stats";
import { FlashcardDeckCard } from "./flashcard-deck-card";
import { FlashcardEmptyState } from "./flashcard-empty-state";
import { CreateFlashcardModal } from "./create-flashcard-modal";

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
      setDueCards(dueData.results || dueData || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to load flashcard data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCardCreated = (card: Flashcard) => {
    loadData();
  };

  return (
    <div className="min-h-screen bg-[#080d1a] text-white">
      {/* Header */}
      <div className="px-6 pt-8 pb-6 max-w-6xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-white via-violet-200 to-violet-400 bg-clip-text text-transparent">
              Flashcards
            </h1>
            <p className="text-white/50 text-sm mt-1">
              Spaced repetition powered by your quiz performance
            </p>
          </div>
          <div className="flex items-center gap-3">
            <CreateFlashcardModal onCreated={handleCardCreated} />
            <Link
              href="/flashcards/manage"
              id="manage-flashcards-btn"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-white text-sm font-medium transition-colors border border-white/10"
            >
              <Settings className="w-4 h-4" />
              Manage
            </Link>
          </div>
        </div>
      </div>

      <div className="px-6 pb-8 max-w-6xl mx-auto space-y-8">
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <div className="w-10 h-10 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
          </div>
        ) : error ? (
          <div className="rounded-2xl bg-red-900/20 border border-red-500/30 p-6 text-center">
            <p className="text-red-400">{error}</p>
            <button onClick={loadData} className="mt-3 text-sm text-white/60 hover:text-white underline">
              Try again
            </button>
          </div>
        ) : stats ? (
          <>
            {/* Stats Row */}
            <FlashcardStatsBar stats={stats} />

            {/* Study Now CTA */}
            {dueCards.length > 0 ? (
              <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-violet-900/60 via-violet-800/40 to-[#0f1729] border border-violet-500/30 p-8 flex flex-col sm:flex-row items-start sm:items-center gap-6">
                {/* Decorative glow */}
                <div className="absolute inset-0 bg-gradient-to-r from-violet-500/5 to-transparent pointer-events-none" />
                <div className="flex-1 relative">
                  <p className="text-xs font-semibold text-violet-400 uppercase tracking-widest mb-1">
                    Ready to Review
                  </p>
                  <h2 className="text-2xl font-bold text-white">
                    {dueCards.length} card{dueCards.length !== 1 ? "s" : ""} due today
                  </h2>
                  <p className="text-white/50 text-sm mt-1">
                    Keep your streak going — reviewing now improves long-term retention.
                  </p>
                </div>
                <Link
                  href="/flashcards/study"
                  id="start-review-session-btn"
                  className="flex items-center gap-3 px-7 py-3.5 rounded-2xl bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white font-semibold transition-all shadow-xl shadow-violet-900/40 whitespace-nowrap relative"
                >
                  <Play className="w-5 h-5 fill-current" />
                  Start Review
                </Link>
              </div>
            ) : (
              <div className="rounded-3xl bg-gradient-to-br from-emerald-900/30 to-[#0f1729] border border-emerald-500/20 p-8 text-center">
                <p className="text-emerald-400 font-semibold text-lg flex items-center justify-center gap-2"><PartyPopper className="w-5 h-5" /> All caught up!</p>
                <p className="text-white/40 text-sm mt-1">No cards due right now. Check back later.</p>
              </div>
            )}

            {/* Decks Grid */}
            {stats.decks.length > 0 ? (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">Your Decks</h2>
                  <Link
                    href="/flashcards/manage"
                    className="text-sm text-violet-400 hover:text-violet-300 transition-colors"
                  >
                    View all
                  </Link>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {stats.decks.map((deck) => (
                    <FlashcardDeckCard key={deck.subject_id} deck={deck} />
                  ))}
                </div>
              </div>
            ) : (
              <FlashcardEmptyState mode="all" />
            )}
          </>
        ) : (
          <FlashcardEmptyState mode="all" />
        )}
      </div>
    </div>
  );
}
