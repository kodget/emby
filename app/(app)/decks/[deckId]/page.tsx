"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { deckApi, type SlideDeck } from "@/lib/api";
import { DeckReader } from "@/components/reader/deck-reader";
import { ArrowLeft, Loader2 } from "lucide-react";

export default function DeckViewPage() {
  const params = useParams();
  const router = useRouter();
  const deckId = params.deckId as string;

  const [deck, setDeck] = useState<SlideDeck | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDeck = async () => {
      try {
        setLoading(true);
        const data = await deckApi.getDeck(deckId);
        setDeck(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load deck");
      } finally {
        setLoading(false);
      }
    };

    loadDeck();
  }, [deckId]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-100">
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin" />
          <p className="text-gray-600">Loading deck...</p>
        </div>
      </div>
    );
  }

  if (error || !deck) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-gray-100">
        <div className="rounded-lg bg-white p-8 text-center shadow-lg">
          <h3 className="text-lg font-semibold text-red-600">Error</h3>
          <p className="mt-2 text-gray-600">{error || "Failed to load deck"}</p>
          <button
            onClick={() => router.back()}
            className="mt-4 inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Go Back</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen overflow-hidden">
      <DeckReader deckId={deckId} title={deck.title} />
    </div>
  );
}
