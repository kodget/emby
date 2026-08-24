"use client";

import { motion } from "framer-motion";
import { Flag, CheckCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { QuizQuestion } from "@/store/quiz-attempt-slice";

interface MCQQuestionCardProps {
  question: QuizQuestion;
  questionNumber: number;
  totalQuestions: number;
  selectedOption?: string;
  isFlagged: boolean;
  onSelect: (option: string) => void;
  onFlag: () => void;
}

const OPTIONS = ["A", "B", "C", "D"] as const;

function getOptionText(q: QuizQuestion, opt: string) {
  const map: Record<string, string | undefined> = { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d };
  return map[opt];
}

export function MCQQuestionCard({ question, questionNumber, totalQuestions, selectedOption, isFlagged, onSelect, onFlag }: MCQQuestionCardProps) {
  return (
    <motion.div key={question.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Badge variant="outline" className="text-xs">Question {questionNumber} of {totalQuestions}</Badge>
            <Badge variant="secondary" className="text-xs capitalize">{question.difficulty}</Badge>
            {question.topic_name && <Badge variant="outline" className="text-xs text-primary border-primary/30">{question.topic_name}</Badge>}
          </div>
          <p className="text-lg font-medium leading-relaxed">{question.question_text}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onFlag}
          className={cn("flex-shrink-0 rounded-full transition-colors", isFlagged ? "text-amber-500 bg-amber-50 hover:bg-amber-100" : "text-muted-foreground")}>
          <Flag className="w-4 h-4" />
        </Button>
      </div>
      <div className="grid gap-3">
        {OPTIONS.map((opt) => {
          const text = getOptionText(question, opt);
          if (!text) return null;
          const selected = selectedOption === opt;
          return (
            <motion.button key={opt} whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }} onClick={() => onSelect(opt)}
              className={cn("w-full text-left p-4 rounded-xl border-2 transition-all duration-200 flex items-start gap-3",
                selected ? "border-primary bg-primary/5 shadow-sm" : "border-border hover:border-primary/40 hover:bg-accent/40")}>
              <div className={cn("w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold transition-all",
                selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>
                {selected ? <CheckCircle className="w-4 h-4" /> : opt}
              </div>
              <span className="pt-0.5 leading-relaxed text-sm">{text}</span>
            </motion.button>
          );
        })}
      </div>
    </motion.div>
  );
}