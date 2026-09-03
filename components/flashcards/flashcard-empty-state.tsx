"use client";

import Link from "next/link";
import { Layers, Plus, Zap, PartyPopper } from "lucide-react";

interface FlashcardEmptyStateProps {
  mode?: "all" | "due";
}

export function FlashcardEmptyState({ mode = "all" }: FlashcardEmptyStateProps) {
  if (mode === "due") {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-20 text-center">
        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-emerald-500/20 to-emerald-400/5 border border-emerald-500/30 flex items-center justify-center">
          <Zap className="w-9 h-9 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-2xl font-bold text-foreground mb-2 flex items-center justify-center gap-2">You're all caught up! <PartyPopper className="w-6 h-6 text-emerald-400" /></h3>
          <p className="text-muted-foreground max-w-md">
            No cards are due for review right now. Come back later, or create new cards to keep learning.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            href="/flashcards/manage"
            className="px-5 py-2.5 rounded-xl bg-muted hover:bg-muted/80 text-foreground text-sm font-medium transition-colors"
          >
            Manage Cards
          </Link>
          <Link
            href="/quiz"
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white text-sm font-medium transition-all shadow-lg shadow-violet-900/30"
          >
            Take a Quiz
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-6 py-20 text-center">
      <div className="w-20 h-20 rounded-full bg-gradient-to-br from-violet-500/20 to-violet-400/5 border border-violet-500/30 flex items-center justify-center">
        <Layers className="w-9 h-9 text-violet-400" />
      </div>
      <div>
        <h3 className="text-2xl font-bold text-foreground mb-2">No flashcards yet</h3>
        <p className="text-muted-foreground max-w-md">
          Create your first card manually, or take a quiz — cards are automatically
          generated from questions you get wrong.
        </p>
      </div>
      <div className="flex gap-3">
        <Link
          href="/quiz"
          className="px-5 py-2.5 rounded-xl bg-muted hover:bg-muted/80 text-foreground text-sm font-medium transition-colors"
        >
          Take a Quiz
        </Link>
        <Link
          href="/flashcards/manage?create=1"
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white text-sm font-medium transition-all shadow-lg shadow-violet-900/30"
        >
          <Plus className="w-4 h-4" />
          Create Card
        </Link>
      </div>
    </div>
  );
}
