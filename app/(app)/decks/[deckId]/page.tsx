"use client";
import { useParams } from "next/navigation";
import { DeckReader } from "@/components/reader/deck-reader";
import { useContentSessionKey } from "@/store/hooks";

export default function DeckViewPage() {
  const { deckId } = useParams<{ deckId: string }>();
  const sessionKey = useContentSessionKey();
  return <DeckReader key={`${deckId}:${sessionKey}`} deckId={deckId} title="Document" />;
}
