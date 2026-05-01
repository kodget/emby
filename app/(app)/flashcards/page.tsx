"use client";

import { flashcards } from "@/lib/data";
import { FlashcardStudio } from "@/components/flashcards/flashcard-studio";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";

export default function FlashcardsPage() {
  const userCards = useSelector(
    (state: RootState) => state.flashcards.userCards,
  );
  const allCards = [...flashcards, ...userCards];
  return <FlashcardStudio cards={allCards} />;
}
