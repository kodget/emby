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
  CheckSquare,
  Square,
  RefreshCw,
  History,
  ListTodo
} from "lucide-react";
import { FlashcardStudy } from "@/components/flashcards/flashcard-study";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { SessionFooter } from "@/components/session-footer";
import api, { quizApi, curriculumApi, aiApi } from "@/lib/api";

function SessionContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const initialStep = searchParams.get("step") ? Number(searchParams.get("step")) : 1;
  const initialQuizId = searchParams.get("quizId") || "";

  const [step, setStep] = useState(initialStep);
  const [quizId, setQuizId] = useState(initialQuizId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingQuiz, setLoadingQuiz] = useState(false);
  
  // Session Data
  const [sessionData, setSessionData] = useState<any>(null);
  const [targetSubjectId, setTargetSubjectId] = useState<string | null>(null);

  useEffect(() => {
    async function loadSessionContext() {
      try {
        const [statsRes, subjectsRes] = await Promise.all([
          aiApi.getRecommendations().catch(() => null),
          curriculumApi.getSubjects().catch(() => []),
        ]);

        if (statsRes) {
          setSessionData(statsRes);
        }
        if (subjectsRes && subjectsRes.length > 0) {
          setTargetSubjectId(subjectsRes[0].id);
        }
      } catch (err) {
        console.error("Failed to load session context", err);
      } finally {
        setLoading(false);
      }
    }
    loadSessionContext();
  }, []);

  const startPracticeQuiz = async () => {
    setLoadingQuiz(true);
    setError(null);
    try {
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

      // Redirect to quiz, and on submit, redirect back to session?step=4
      router.push(`/quiz/attempt/${attempt.id}?session=true&nextStep=4`);
    } catch (err: any) {
      console.error("Failed to create quiz attempt:", err);
      setError(err?.response?.data?.message || "Failed to initialize practice quiz.");
      setLoadingQuiz(false);
    }
  };

  const toggleStudyPlanItem = async (itemId: number, currentStatus: string) => {
    try {
      const nextStatus = currentStatus === 'pending' ? 'in_progress' : 'completed';
      await api.patch(`/api/schedule/${itemId}/`, { status: nextStatus });
      
      // Update local state
      setSessionData((prev: any) => ({
        ...prev,
        study_plan_items: prev.study_plan_items.map((item: any) => 
          item.id === itemId ? { ...item, status: nextStatus } : item
        )
      }));
    } catch (err) {
      console.error("Failed to update schedule item:", err);
    }
  };

  const exitSession = () => {
    if (confirm("Are you sure you want to pause and exit your study session? Progress is saved.")) {
      router.push("/dashboard");
    }
  };

  const getProgressPercentage = () => {
    if (step === 1) return 10;
    if (step === 2) return 30;
    if (step === 3) return 50;
    if (step === 4) return 70;
    if (step === 5) return 90;
    if (step === 6) return 100;
    return 0;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center space-y-4">
        <Loader2 className="size-8 animate-spin text-primary" />
        <p className="text-zinc-500 font-medium">Preparing your study session...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Dynamic Header */}
      {step < 6 && (
        <header className="border-b border-border bg-card px-6 py-4 flex items-center justify-between sticky top-0 z-10 shadow-xs">
          <div className="flex items-center gap-4">
            <button
              onClick={exitSession}
              className="p-2 rounded-xl bg-card hover:bg-muted text-zinc-400 hover:text-foreground transition-colors"
              aria-label="Exit Session"
            >
              <X className="size-4" />
            </button>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-primary">Active Study Session</p>
              <h1 className="text-sm font-semibold text-foreground">
                {step === 1 && "Step 1: Read New Material"}
                {step === 2 && "Step 2: Spaced Repetition Review"}
                {step === 3 && "Step 3: Target Practice"}
                {step === 4 && "Step 4: Revise Stale Concepts"}
                {step === 5 && "Step 5: Study Plan Checkoff"}
              </h1>
            </div>
          </div>
          
          <div className="flex items-center gap-3 w-48 hidden sm:flex">
            <Progress value={getProgressPercentage()} className="h-1.5 bg-card" />
            <span className="text-[11px] font-semibold text-zinc-400 whitespace-nowrap">
              {getProgressPercentage()}% Complete
            </span>
          </div>
        </header>
      )}

      {/* Main Container */}
      <main className="flex-1 flex flex-col items-center justify-center p-6">
        <AnimatePresence mode="wait">
          
          {/* STEP 1: READ */}
          {step === 1 && (
            <motion.div
              key="step1"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="w-full max-w-lg text-center"
            >
              <Card className="border-border bg-card text-foreground p-6 md:p-8 rounded-3xl shadow-2xl">
                <CardContent className="space-y-6 pt-6">
                  <div className="w-16 h-16 rounded-full bg-blue-500/10 border border-blue-500/25 flex items-center justify-center mx-auto text-blue-500">
                    <BookOpen className="size-8" />
                  </div>
                  
                  <div className="space-y-2">
                    <h2 className="font-serif text-2xl font-bold">Read Material</h2>
                    <p className="text-zinc-400 text-sm">
                      Read through the following slide to expand your knowledge before moving on.
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-card border border-border text-left space-y-4">
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span>NEXT TO READ</span>
                    </div>
                    {sessionData?.slide_to_read?.id ? (
                      <div>
                        <h3 className="font-semibold text-foreground mb-4">
                          {sessionData.slide_to_read.title}
                        </h3>
                        <Button 
                          asChild
                          variant="secondary"
                          className="w-full"
                        >
                          <a href={`/read/general/${sessionData.slide_to_read.id}?session=true&step=1`} target="_self">
                            Open Reader <ArrowUpRight className="size-4 ml-2" />
                          </a>
                        </Button>
                      </div>
                    ) : (
                      <p className="text-sm font-medium text-zinc-400 italic">No new slides to read at the moment.</p>
                    )}
                  </div>

                  <Button
                    onClick={() => setStep(2)}
                    className="w-full h-12 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg text-sm"
                  >
                    Mark as Read & Continue
                    <ArrowRight className="size-4 ml-2" />
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* STEP 2: REVIEW (FLASHCARDS) */}
          {step === 2 && (
            <motion.div
              key="step2"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="w-full max-w-3xl"
            >
              <div className="rounded-3xl border border-border bg-card p-1">
                <FlashcardStudy onComplete={() => setStep(3)} />
              </div>
            </motion.div>
          )}

          {/* STEP 3: PRACTICE */}
          {step === 3 && (
            <motion.div
              key="step3"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="w-full max-w-lg text-center"
            >
              <Card className="border-border bg-card text-foreground p-6 md:p-8 rounded-3xl shadow-2xl">
                <CardContent className="space-y-6 pt-6">
                  <div className="w-16 h-16 rounded-full bg-mastery/10 border border-mastery/25 flex items-center justify-center mx-auto text-mastery">
                    <CheckCircle className="size-8" />
                  </div>
                  
                  <div className="space-y-2">
                    <h2 className="font-serif text-2xl font-bold">Step 2 Completed!</h2>
                    <p className="text-zinc-400 text-sm">
                      Decks reviewed. Next, test your clinical knowledge and retrieve concepts actively.
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-card border border-border text-left space-y-2">
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span>NEXT ACTIVITY</span>
                      <span className="text-mastery font-semibold uppercase tracking-wider">Practice Quiz</span>
                    </div>
                    <h3 className="font-semibold text-foreground flex items-center gap-1.5">
                      <BookOpen className="size-4 text-primary" />
                      10 Questions focus: {sessionData?.practice_topic || "General"}
                    </h3>
                    <p className="text-xs text-zinc-500">
                      Emby will generate medium-difficulty questions focusing on your weakest subject area.
                    </p>
                  </div>

                  {error && (
                    <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2 text-left">
                      <AlertCircle className="size-4 shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}

                  <div className="flex gap-3">
                    <Button
                      onClick={() => setStep(4)}
                      variant="outline"
                      className="flex-1 h-12 rounded-xl text-sm"
                    >
                      Skip
                    </Button>
                    <Button
                      onClick={startPracticeQuiz}
                      disabled={loadingQuiz}
                      className="flex-[2] h-12 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg text-sm"
                    >
                      {loadingQuiz ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <>Start Practice Quiz <ArrowRight className="size-4 ml-2" /></>
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* STEP 4: REVISE (STALE SLIDES) */}
          {step === 4 && (
            <motion.div
              key="step4"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="w-full max-w-xl text-center"
            >
              <Card className="border-border bg-card text-foreground p-6 md:p-8 rounded-3xl shadow-2xl">
                <CardContent className="space-y-6 pt-6">
                  <div className="w-16 h-16 rounded-full bg-rose-500/10 border border-rose-500/25 flex items-center justify-center mx-auto text-rose-500">
                    <History className="size-8" />
                  </div>
                  
                  <div className="space-y-2">
                    <h2 className="font-serif text-2xl font-bold">Revise Stale Concepts</h2>
                    <p className="text-zinc-400 text-sm">
                      You haven't looked at these slides in over a week. Refresh your memory before they fade.
                    </p>
                  </div>

                  <div className="space-y-3">
                    {sessionData?.stale_slides?.length > 0 ? (
                      <div className="p-4 rounded-2xl bg-card border border-border flex items-center justify-between text-left group hover:border-primary/50 transition-colors">
                        <div>
                          <h3 className="font-semibold text-foreground">
                            {sessionData.stale_slides.length} slides need revision
                          </h3>
                          <p className="text-xs text-zinc-400">Read them sequentially</p>
                        </div>
                        <Button asChild size="sm" variant="default" className="shrink-0 rounded-xl bg-primary text-primary-foreground">
                          <a href={`/read/general/${sessionData.stale_slides[0].id}?session=true&step=4&queue=${sessionData.stale_slides.map((s: any) => s.id).join(',')}`} target="_self">
                            Start Revision <ArrowUpRight className="size-3 ml-1" />
                          </a>
                        </Button>
                      </div>
                    ) : (
                      <div className="p-6 rounded-2xl bg-card border border-border">
                        <p className="text-zinc-400 text-sm font-medium italic">You are all caught up! No stale slides to revise.</p>
                      </div>
                    )}
                  </div>

                  <Button
                    onClick={() => setStep(5)}
                    className="w-full h-12 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg text-sm"
                  >
                    Finish Revision & Continue
                    <ArrowRight className="size-4 ml-2" />
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* STEP 5: STUDY PLAN (TASKS) */}
          {step === 5 && (
            <motion.div
              key="step5"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="w-full max-w-xl text-center"
            >
              <Card className="border-border bg-card text-foreground p-6 md:p-8 rounded-3xl shadow-2xl">
                <CardContent className="space-y-6 pt-6">
                  <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/25 flex items-center justify-center mx-auto text-amber-500">
                    <ListTodo className="size-8" />
                  </div>
                  
                  <div className="space-y-2">
                    <h2 className="font-serif text-2xl font-bold">Today's Study Plan</h2>
                    <p className="text-zinc-400 text-sm">
                      Check off your planned tasks for today as you complete them.
                    </p>
                  </div>

                  <div className="space-y-3">
                    {sessionData?.study_plan_items?.length > 0 ? (
                      sessionData.study_plan_items.map((item: any) => (
                        <div key={item.id} className="p-4 rounded-2xl bg-card border border-border flex items-center justify-between text-left">
                          <div className="flex items-center gap-3">
                            <button 
                              onClick={() => toggleStudyPlanItem(item.id, item.status)}
                              className="text-muted-foreground hover:text-primary transition-colors focus:outline-none"
                            >
                              {item.status === 'completed' ? (
                                <CheckSquare className="size-5 text-mastery" />
                              ) : item.status === 'in_progress' ? (
                                <RefreshCw className="size-5 text-amber-500" />
                              ) : (
                                <Square className="size-5" />
                              )}
                            </button>
                            <div>
                              <h3 className={`font-semibold text-sm ${item.status === 'completed' ? 'line-through text-zinc-500' : 'text-foreground'}`}>
                                {item.title}
                              </h3>
                              <p className="text-[10px] text-zinc-400 uppercase tracking-wider">{item.item_type} - {item.status.replace('_', ' ')}</p>
                            </div>
                          </div>
                          
                          <Button 
                            onClick={() => toggleStudyPlanItem(item.id, item.status)}
                            size="sm" 
                            variant={item.status === 'completed' ? 'outline' : 'default'} 
                            className="shrink-0 rounded-xl"
                            disabled={item.status === 'completed'}
                          >
                            {item.status === 'pending' ? 'Start' : item.status === 'in_progress' ? 'Complete' : 'Done'}
                          </Button>
                        </div>
                      ))
                    ) : (
                      <div className="p-6 rounded-2xl bg-card border border-border">
                        <p className="text-zinc-400 text-sm font-medium italic">No custom study plan items left for today.</p>
                      </div>
                    )}
                  </div>

                  <Button
                    onClick={() => setStep(6)}
                    className="w-full h-12 rounded-xl bg-primary text-primary-foreground font-semibold shadow-lg text-sm"
                  >
                    Finish Session
                    <CheckCircle className="size-4 ml-2" />
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* FINISH SCREEN */}
          {step === 6 && (
            <motion.div
              key="step6"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="w-full max-w-md text-center"
            >
              <Card className="border-border bg-card text-foreground p-8 rounded-3xl shadow-2xl">
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

                  <div className="p-4 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Zap className="size-5 text-primary fill-current" />
                      <div className="text-left leading-tight">
                        <p className="text-[10px] uppercase font-bold text-primary">XP AWARDED</p>
                        <p className="text-sm font-semibold text-foreground mt-0.5">Session Completed</p>
                      </div>
                    </div>
                    <span className="text-lg font-bold text-primary">+150 XP</span>
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

      {/* Global Footer Navigation */}
      <SessionFooter 
        currentStep={step} 
        isEmbedded={true}
        onPrev={() => setStep(Math.max(1, step - 1))}
        onNext={() => setStep(Math.min(6, step + 1))}
      />
    </div>
  );
}

export default function SessionPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    }>
      <SessionContent />
    </Suspense>
  );
}
