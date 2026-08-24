"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Trophy,
  ArrowRight,
  BookOpen,
  CheckCircle,
  XCircle,
  Sparkles,
  Loader2,
  X,
  AlertCircle,
  HelpCircle,
  ArrowUpRight,
  Zap,
} from "lucide-react";
import { FlashcardStudy } from "@/components/flashcards/flashcard-study";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import api, { quizApi, curriculumApi, statsApi } from "@/lib/api";

function SessionContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Determine starting step based on query params (e.g. returning from quiz)
  const initialStep = searchParams.get("step") ? Number(searchParams.get("step")) : 1;
  const initialQuizId = searchParams.get("quizId") || "";

  const [step, setStep] = useState(initialStep);
  const [quizId, setQuizId] = useState(initialQuizId);
  const [loadingQuiz, setLoadingQuiz] = useState(false);
  const [loadingMissed, setLoadingMissed] = useState(false);
  const [missedQuestions, setMissedQuestions] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  // Weak area context
  const [weakTopic, setWeakTopic] = useState("Neuroanatomy");
  const [targetSubjectId, setTargetSubjectId] = useState<string | null>(null);

  useEffect(() => {
    // Load weak topic and first subject to prep the quiz
    async function loadSessionContext() {
      try {
        const [statsRes, subjectsRes] = await Promise.all([
          statsApi.getRecommendations().catch(() => null),
          curriculumApi.getSubjects().catch(() => []),
        ]);

        if (statsRes?.focus_areas && statsRes.focus_areas.length > 0) {
          setWeakTopic(statsRes.focus_areas[0]);
        }

        if (subjectsRes && subjectsRes.length > 0) {
          setTargetSubjectId(subjectsRes[0].id);
        }
      } catch (err) {
        console.error("Failed to load session context", err);
      }
    }
    loadSessionContext();
  }, []);

  // Fetch missed questions if we land on Step 3
  useEffect(() => {
    if (step === 3 && quizId) {
      loadMissedQuestions(quizId);
    }
  }, [step, quizId]);

  const loadMissedQuestions = async (id: string) => {
    setLoadingMissed(true);
    setError(null);
    try {
      const response = await api.get(`/api/quiz-attempts/${id}/missed/`);
      setMissedQuestions(response.data?.missed_questions || []);
    } catch (err) {
      console.error("Failed to load missed questions:", err);
      setError("Failed to load your missed questions summary.");
    } finally {
      setLoadingMissed(false);
    }
  };

  const startPracticeQuiz = async () => {
    setLoadingQuiz(true);
    setError(null);
    try {
      // Start a practice quiz attempt
      const attempt = await quizApi.createQuizAttempt({
        subject: targetSubjectId || undefined,
        exam_type: "practice",
        is_timed: false,
        configuration: {
          mcq_count: 10,
          theory_count: 0,
          difficulty: "medium",
        },
      });

      // Redirect user to the active quiz runner with session mode query param
      router.push(`/quiz/attempt/${attempt.id}?session=true`);
    } catch (err: any) {
      console.error("Failed to create quiz attempt:", err);
      setError(err?.response?.data?.message || "Failed to initialize practice quiz.");
      setLoadingQuiz(false);
    }
  };

  const exitSession = () => {
    if (confirm("Are you sure you want to pause and exit your study session? Progress is saved.")) {
      router.push("/dashboard");
    }
  };

  const getProgressPercentage = () => {
    if (step === 1) return 15;
    if (step === 2) return 50;
    if (step === 3) return 85;
    if (step === 4) return 100;
    return 0;
  };

  return (
    <div className="min-h-screen bg-[#080d1a] text-zinc-100 flex flex-col">
      {/* Dynamic Header */}
      {step < 4 && (
        <header className="border-b border-white/5 bg-[#0b1326] px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={exitSession}
              className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-zinc-100 transition-colors"
              aria-label="Exit Session"
            >
              <X className="size-4" />
            </button>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-primary">Active Study Session</p>
              <h1 className="text-sm font-semibold text-zinc-200">
                {step === 1 && "Step 1: Spaced Repetition Review"}
                {step === 2 && "Step 2: Target Practice"}
                {step === 3 && "Step 3: Reinforce Missed Concepts"}
              </h1>
            </div>
          </div>
          
          <div className="flex items-center gap-3 w-48 hidden sm:flex">
            <Progress value={getProgressPercentage()} className="h-1.5 bg-white/5" />
            <span className="text-[11px] font-semibold text-zinc-400 whitespace-nowrap">
              {getProgressPercentage()}% Complete
            </span>
          </div>
        </header>
      )}

      {/* Main Container */}
      <main className="flex-1 flex flex-col items-center justify-center p-6">
        <AnimatePresence mode="wait">
          {step === 1 && (
            <motion.div
              key="step1"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="w-full max-w-3xl"
            >
              <div className="rounded-3xl border border-white/5 bg-[#0b1326]/60 p-1">
                <FlashcardStudy onComplete={() => setStep(2)} />
              </div>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div
              key="step2"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="w-full max-w-lg text-center"
            >
              <Card className="border-white/5 bg-[#0b1326]/60 text-zinc-200 p-6 md:p-8 rounded-3xl shadow-2xl">
                <CardContent className="space-y-6 pt-6">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto text-emerald-400">
                    <CheckCircle className="size-8" />
                  </div>
                  
                  <div className="space-y-2">
                    <h2 className="font-serif text-2xl font-bold">Step 1 Completed!</h2>
                    <p className="text-zinc-400 text-sm">
                      Decks reviewed. Next, test your clinical knowledge and retrieve concepts actively.
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-white/5 border border-white/5 text-left space-y-2">
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span>NEXT ACTIVITY</span>
                      <span className="text-emerald-400 font-semibold uppercase tracking-wider">Practice Quiz</span>
                    </div>
                    <h3 className="font-semibold text-zinc-100 flex items-center gap-1.5">
                      <BookOpen className="size-4 text-primary" />
                      10 Questions focus: {weakTopic}
                    </h3>
                    <p className="text-xs text-zinc-500">
                      Emby will generate medium-difficulty questions focusing on your weakest subject area to strengthen weak nodes.
                    </p>
                  </div>

                  {error && (
                    <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2 text-left">
                      <AlertCircle className="size-4 shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}

                  <Button
                    onClick={startPracticeQuiz}
                    disabled={loadingQuiz}
                    className="w-full h-12 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg text-sm"
                  >
                    {loadingQuiz ? (
                      <>
                        <Loader2 className="size-4 animate-spin mr-2" />
                        Generating Quiz...
                      </>
                    ) : (
                      <>
                        Start Practice Quiz
                        <ArrowRight className="size-4 ml-2" />
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {step === 3 && (
            <motion.div
              key="step3"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="w-full max-w-2xl"
            >
              <div className="space-y-6">
                <div className="text-center space-y-2">
                  <div className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/20 bg-rose-500/10 px-3 py-1 text-[11px] font-semibold text-rose-400">
                    <AlertCircle className="size-3.5" />
                    REINFORCE CONCEPTS
                  </div>
                  <h2 className="font-serif text-3xl font-bold">Review Your Mistakes</h2>
                  <p className="text-zinc-400 text-sm">
                    Read the clinical explanations for questions you answered incorrectly during the test.
                  </p>
                </div>

                {loadingMissed ? (
                  <div className="flex flex-col items-center py-12 space-y-3">
                    <Loader2 className="size-8 animate-spin text-primary" />
                    <p className="text-zinc-500 text-sm">Fetching incorrect answers...</p>
                  </div>
                ) : error ? (
                  <Card className="border-white/5 bg-[#0b1326]/60 text-zinc-200 p-6 rounded-2xl text-center">
                    <p className="text-rose-400 mb-4">{error}</p>
                    <Button onClick={() => loadMissedQuestions(quizId)} variant="outline">Retry</Button>
                  </Card>
                ) : missedQuestions.length === 0 ? (
                  <Card className="border-emerald-500/20 bg-emerald-500/5 text-zinc-200 p-8 rounded-3xl text-center space-y-3">
                    <CheckCircle className="size-10 text-emerald-400 mx-auto" />
                    <h3 className="font-bold text-zinc-100">Perfect Practice Run!</h3>
                    <p className="text-zinc-400 text-sm">
                      You answered 100% of the quiz questions correctly. No concepts to reinforce!
                    </p>
                    <Button onClick={() => setStep(4)} className="bg-primary text-primary-foreground mt-2">Proceed to Summary</Button>
                  </Card>
                ) : (
                  <div className="space-y-4">
                    {missedQuestions.map((q, idx) => (
                      <Card key={q.id} className="border-white/5 bg-[#0b1326]/60 text-zinc-200 rounded-2xl">
                        <CardHeader className="pb-3 flex flex-row items-start justify-between gap-4">
                          <div className="space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400">Question {idx + 1}</span>
                            <CardTitle className="text-sm font-semibold leading-snug">{q.question_text}</CardTitle>
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-3 text-sm">
                          <div className="grid gap-2 grid-cols-1 sm:grid-cols-2">
                            <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/10 px-3 py-2 text-emerald-400">
                              <CheckCircle className="size-4 shrink-0" />
                              <span>Correct: {q.correct_option || q.correct_answer || "—"}</span>
                            </div>
                            <div className="flex items-center gap-2 rounded-xl bg-rose-500/10 border border-rose-500/10 px-3 py-2 text-rose-400">
                              <XCircle className="size-4 shrink-0" />
                              <span>Your answer: {q.selected_option || q.student_answer || "No answer"}</span>
                            </div>
                          </div>
                          
                          {q.explanation && (
                            <div className="p-3 rounded-xl bg-white/5 border border-white/5 text-zinc-300 text-xs">
                              <strong className="text-zinc-100 font-semibold block mb-1">Clinical Rationale:</strong>
                              <p className="leading-relaxed">{q.explanation}</p>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                    
                    <Button onClick={() => setStep(4)} className="w-full h-12 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg mt-6">
                      Finish Study Session
                    </Button>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {step === 4 && (
            <motion.div
              key="step4"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="w-full max-w-md text-center"
            >
              <Card className="border-white/5 bg-[#0b1326]/60 text-zinc-200 p-8 rounded-3xl shadow-2xl">
                <CardContent className="space-y-6 pt-6">
                  <div className="w-20 h-20 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto text-primary relative">
                    <Trophy className="size-10" />
                    <Sparkles className="size-5 absolute -top-1 -right-1 text-yellow-400 animate-pulse" />
                  </div>
                  
                  <div className="space-y-2">
                    <h2 className="font-serif text-3xl font-bold">Session Complete!</h2>
                    <p className="text-zinc-400 text-sm">
                      Fantastic work! You completed today's optimized study sequence.
                    </p>
                  </div>

                  <div className="divide-y divide-white/5 border-y border-white/5 py-4 text-left space-y-3">
                    <div className="flex items-center justify-between text-sm py-1">
                      <span className="text-zinc-400">Step 1: Spaced Repetition</span>
                      <span className="text-zinc-200 font-medium">Completed</span>
                    </div>
                    <div className="flex items-center justify-between text-sm py-2">
                      <span className="text-zinc-400">Step 2: Weak-Area Quiz</span>
                      <span className="text-zinc-200 font-medium">10 Questions answered</span>
                    </div>
                    <div className="flex items-center justify-between text-sm py-2">
                      <span className="text-zinc-400">Step 3: Mistakes Reviewed</span>
                      <span className="text-zinc-200 font-medium">{missedQuestions.length} Concepts corrected</span>
                    </div>
                  </div>

                  <div className="p-4 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Zap className="size-5 text-primary fill-current" />
                      <div className="text-left leading-tight">
                        <p className="text-[10px] uppercase font-bold text-primary">XP AWARDED</p>
                        <p className="text-sm font-semibold text-zinc-200 mt-0.5">Maintain Streak</p>
                      </div>
                    </div>
                    <span className="text-lg font-bold text-primary">+50 XP</span>
                  </div>

                  <Button
                    onClick={() => router.push("/dashboard")}
                    className="w-full h-12 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg"
                  >
                    Return to Dashboard
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

export default function SessionPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#080d1a] flex items-center justify-center">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    }>
      <SessionContent />
    </Suspense>
  );
}
