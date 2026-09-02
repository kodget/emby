"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { FlashcardStudy } from "@/components/flashcards/flashcard-study";
import { Loader2 } from "lucide-react";
import { SessionFooter } from "@/components/session-footer";

function StudyPageContent() {
  const params = useSearchParams();
  const subject = params.get("subject") ?? undefined;
  const block = params.get("block") ?? undefined;
  const subBlockParam = params.get("sub_block");
  const subBlock = subBlockParam ? parseInt(subBlockParam, 10) : undefined;
  const topicParam = params.get("topic");
  const topic = topicParam ? parseInt(topicParam, 10) : undefined;
  const isSession = params.get("session") === "true";

  return (
    <div className="flex flex-col min-h-screen">
      <div className="flex-1">
        <FlashcardStudy subjectId={subject} blockId={block} subBlockId={subBlock} topicId={topic} />
      </div>
      {isSession && <SessionFooter currentStep={2} />}
    </div>
  );
}

export default function FlashcardStudyPage() {
  return (
    <Suspense fallback={<div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>}>
      <StudyPageContent />
    </Suspense>
  );
}
