"use client";
import { motion } from "framer-motion";
import { Flag, PenLine, AlignLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { QuizQuestion } from "@/store/quiz-attempt-slice";

interface TheoryQuestionCardProps {
  question: QuizQuestion;
  questionNumber: number;
  totalQuestions: number;
  answer: string;
  isFlagged: boolean;
  onChange: (text: string) => void;
  onFlag: () => void;
}

export function TheoryQuestionCard({ question, questionNumber, totalQuestions, answer, isFlagged, onChange, onFlag }: TheoryQuestionCardProps) {
  const wordCount = answer.trim().split(/\s+/).filter(Boolean).length;
  const hasEnough = wordCount >= 30;
  return (
    <motion.div key={question.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Badge variant="outline" className="text-xs">Question {questionNumber} of {totalQuestions}</Badge>
            <Badge className="text-xs bg-emerald-100 text-emerald-700 border border-emerald-200"><PenLine className="w-3 h-3 mr-1" />Theory</Badge>
            <Badge variant="secondary" className="text-xs capitalize">{question.difficulty}</Badge>
          </div>
          <p className="text-lg font-medium leading-relaxed">{question.question_text}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onFlag} className={cn("flex-shrink-0 rounded-full", isFlagged ? "text-amber-500 bg-amber-50" : "text-muted-foreground")}><Flag className="w-4 h-4" /></Button>
      </div>
      <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100 flex items-start gap-2">
        <AlignLeft className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
        <p className="text-sm text-emerald-700">Write a detailed answer. Aim for at least 30 words. AI will evaluate your response.</p>
      </div>
      <div className="space-y-2">
        <Textarea value={answer} onChange={(e) => onChange(e.target.value)} placeholder="Start writing your answer here..." className="min-h-[220px] resize-y text-base leading-relaxed" autoFocus />
        <div className="flex items-center justify-between px-1">
          <span className={cn("text-xs transition-colors", hasEnough ? "text-emerald-600" : "text-muted-foreground")}>{wordCount} word{wordCount !== 1 ? "s" : ""}{ !hasEnough ? " (30+ recommended)" : " check"}</span>
          <span className="text-xs text-muted-foreground">{answer.length} chars</span>
        </div>
      </div>
    </motion.div>
  );
}