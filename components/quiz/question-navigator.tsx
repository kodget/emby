"use client";

import { motion } from "framer-motion";
import { Flag, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QuestionStatus } from "@/store/quiz-attempt-slice";

interface QuestionNavigatorProps {
  totalQuestions: number;
  currentIndex: number;
  statuses: Record<string, QuestionStatus>;
  questionIds: string[];
  onNavigate: (index: number) => void;
}

export function QuestionNavigator({ totalQuestions, currentIndex, statuses, questionIds, onNavigate }: QuestionNavigatorProps) {
  const answered = questionIds.filter((id) => statuses[id] === "answered").length;
  const flagged = questionIds.filter((id) => statuses[id] === "flagged").length;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="p-2 rounded-lg bg-primary/10"><div className="text-xl font-bold text-primary">{answered}</div><div className="text-xs text-muted-foreground">Answered</div></div>
        <div className="p-2 rounded-lg bg-amber-50"><div className="text-xl font-bold text-amber-600">{flagged}</div><div className="text-xs text-muted-foreground">Flagged</div></div>
        <div className="p-2 rounded-lg bg-muted"><div className="text-xl font-bold text-muted-foreground">{totalQuestions - answered - flagged}</div><div className="text-xs text-muted-foreground">Remaining</div></div>
      </div>
      <div className="grid grid-cols-5 gap-1.5">
        {questionIds.map((id, i) => {
          const status = statuses[id] ?? "unanswered";
          return (
            <motion.button key={id} whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }} onClick={() => onNavigate(i)}
              className={cn("w-9 h-9 rounded-lg text-xs font-semibold flex items-center justify-center border transition-all",
                i === currentIndex ? "ring-2 ring-primary ring-offset-1" : "",
                status === "answered" ? "bg-primary text-primary-foreground border-primary"
                  : status === "flagged" ? "bg-amber-100 text-amber-700 border-amber-300"
                  : "bg-muted text-muted-foreground hover:bg-accent border-border")}>
              {status === "answered" ? <Check className="w-3.5 h-3.5" /> : status === "flagged" ? <Flag className="w-3.5 h-3.5" /> : i + 1}
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}