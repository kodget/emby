"use client";
import Link from "next/link";
import { Layers, Check } from "lucide-react";
import { WorkspaceEmpty } from "@/components/ui/workspace-header";
import { Button } from "@/components/ui/button";
export function FlashcardEmptyState({ mode = "all" }: { mode?: "all" | "due" }) {
  const caughtUp = mode === "due";
  return <WorkspaceEmpty icon={caughtUp ? Check : Layers} title={caughtUp ? "A little breathing room." : "Your first card is a start."} description={caughtUp ? "No reviews are due right now. Come back later, or explore another part of your study day." : "Make a card from something you want to remember, generate cards from your class material, or practise a quiz to revisit mistakes."}>
    <Button variant="outline" asChild><Link href={caughtUp ? "/flashcards/manage" : "/courses"}>{caughtUp ? "Manage cards" : "Explore your materials"}</Link></Button>
    <Button asChild><Link href={caughtUp ? "/quiz" : "/flashcards/manage?create=1"}>{caughtUp ? "Practise a question" : "Create a card"}</Link></Button>
  </WorkspaceEmpty>;
}

