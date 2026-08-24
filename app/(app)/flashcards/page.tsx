import { FlashcardStudio } from "@/components/flashcards/flashcard-studio";

export const metadata = {
  title: "Flashcards | Emby",
  description: "Review your flashcards with spaced repetition. Cards are automatically generated from quiz mistakes.",
};

export default function FlashcardsPage() {
  return <FlashcardStudio />;
}
