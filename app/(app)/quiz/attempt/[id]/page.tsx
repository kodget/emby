"use client";

import { useEffect, useCallback, use } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, Send, Menu, X, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/components/ui/use-toast";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  loadAttempt, saveAnswer, flagQuestion, submitAttempt, autoSubmitAttempt,
  navigateToQuestion, nextQuestion, prevQuestion,
  setMCQAnswer, setTheoryAnswer, toggleFlag, tickTimer, startTimer, resetAttempt
} from "@/store/quiz-attempt-slice";
import { ExamTimer } from "@/components/quiz/exam-timer";
import { MCQQuestionCard } from "@/components/quiz/mcq-question-card";
import { TheoryQuestionCard } from "@/components/quiz/theory-question-card";
import { QuestionNavigator } from "@/components/quiz/question-navigator";
import { SessionFooter } from "@/components/session-footer";

interface ExamInterfacePageProps {
  params: Promise<{ id: string }>;
}

export default function ExamInterfacePage({ params }: ExamInterfacePageProps) {
  const unwrappedParams = use(params);
  const attemptId = unwrappedParams.id;
  const router = useRouter();
  const { toast } = useToast();
  const dispatch = useAppDispatch();
  const { currentAttempt, currentQuestionIndex, answers, questionStatuses, timeRemainingSeconds, timerActive, loading, submitting, isSubmitted } = useAppSelector((s) => s.quizAttempt);

  useEffect(() => {
    dispatch(loadAttempt(attemptId)).then(() => { dispatch(startTimer()); });
    return () => { dispatch(resetAttempt()); };
  }, [attemptId, dispatch]);

  const searchParams = useSearchParams();
  const isSession = searchParams.get("session") === "true";
  const nextStep = searchParams.get("nextStep") || "4";

  useEffect(() => {
    if (isSubmitted) {
      if (isSession) {
        router.push(`/quiz/attempt/${attemptId}/results?session=true&nextStep=${nextStep}`);
      } else {
        router.push(`/quiz/attempt/${attemptId}/results`);
      }
    }
  }, [isSubmitted, attemptId, router, isSession, nextStep]);

  const handleTick = useCallback(() => { dispatch(tickTimer()); }, [dispatch]);

  const handleTimerExpire = useCallback(() => {
    toast({ title: "Time is up!", description: "Your exam has been automatically submitted." });
    dispatch(autoSubmitAttempt(attemptId));
  }, [dispatch, attemptId, toast]);

  const handleMCQSelect = (questionId: string, option: string) => {
    dispatch(setMCQAnswer({ questionId, option }));
    dispatch(saveAnswer({ attemptId, answer: { question_id: questionId, selected_option: option, time_taken_seconds: 30 } }));
  };

  const handleTheoryChange = (questionId: string, text: string) => {
    dispatch(setTheoryAnswer({ questionId, text }));
  };

  const handleTheoryBlur = (questionId: string) => {
    const answer = answers[questionId];
    if (answer?.text_answer) {
      dispatch(saveAnswer({ attemptId, answer: { question_id: questionId, text_answer: answer.text_answer, time_taken_seconds: 60 } }));
    }
  };

  const handleFlag = (questionId: string) => {
    dispatch(toggleFlag(questionId));
    dispatch(flagQuestion({ attemptId, questionId }));
  };

  const handleSubmit = async () => {
    await dispatch(submitAttempt(attemptId));
  };

  if (loading || !currentAttempt) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-muted-foreground">Loading your exam...</p>
        </div>
      </div>
    );
  }

  const questions = currentAttempt.questions;

  if (!questions || questions.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="text-center space-y-4 max-w-md">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto" />
          <h2 className="text-xl font-semibold">No Questions Available</h2>
          <p className="text-muted-foreground">
            This quiz attempt has no questions associated with it. This usually happens if there are no questions available for the selected topic or difficulty.
          </p>
          <Button onClick={() => router.push("/quiz")}>Back to Quizzes</Button>
        </div>
      </div>
    );
  }

  const currentQuestion = questions[currentQuestionIndex];
  if (!currentQuestion) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="text-center space-y-4 max-w-md">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto" />
          <h2 className="text-xl font-semibold">Question Not Found</h2>
          <p className="text-muted-foreground">The requested question could not be loaded.</p>
          <Button onClick={() => dispatch(navigateToQuestion(0))}>Reset to First Question</Button>
        </div>
      </div>
    );
  }
  const questionIds = questions.map((q) => q.id);
  const answeredCount = Object.values(questionStatuses).filter((s) => s === "answered").length;
  const totalSeconds = currentAttempt.duration_minutes ? currentAttempt.duration_minutes * 60 : 0;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Top Nav */}
      <header className="sticky top-0 z-50 bg-card/95 backdrop-blur border-b px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="md:hidden"><Menu className="w-4 h-4" /></Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80">
                <SheetHeader><SheetTitle>Question Navigator</SheetTitle></SheetHeader>
                <div className="mt-4">
                  <QuestionNavigator totalQuestions={questions.length} currentIndex={currentQuestionIndex} statuses={questionStatuses} questionIds={questionIds} onNavigate={(i) => dispatch(navigateToQuestion(i))} />
                </div>
              </SheetContent>
            </Sheet>
            <div>
              <h1 className="font-semibold text-sm">{currentAttempt.subject_name || "Quiz"}</h1>
              <p className="text-xs text-muted-foreground capitalize">{currentAttempt.exam_type} exam</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {currentAttempt.is_timed && timeRemainingSeconds !== null && (
              <ExamTimer totalSeconds={totalSeconds} remainingSeconds={timeRemainingSeconds} onTick={handleTick} onExpire={handleTimerExpire} active={timerActive} />
            )}
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button size="sm" className="gap-2" disabled={submitting}>
                  {submitting ? <><div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></div> Submitting...</> : <><Send className="w-3.5 h-3.5" />Submit</> }
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Submit your exam?</AlertDialogTitle>
                  <AlertDialogDescription>You have answered {answeredCount} of {questions.length} questions. This action cannot be undone.</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Review First</AlertDialogCancel>
                  <AlertDialogAction onClick={handleSubmit}>Submit Exam</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 max-w-6xl mx-auto w-full px-4 py-6 grid grid-cols-1 md:grid-cols-[1fr_280px] gap-6">
        {/* Question Area */}
        <Card className="h-fit">
          <CardContent className="pt-6 pb-8 px-6">
            <AnimatePresence mode="wait">
              {currentQuestion.question_type === "mcq" ? (
                <MCQQuestionCard
                  key={currentQuestion.id}
                  question={currentQuestion}
                  questionNumber={currentQuestionIndex + 1}
                  totalQuestions={questions.length}
                  selectedOption={answers[currentQuestion.id]?.selected_option}
                  isFlagged={questionStatuses[currentQuestion.id] === "flagged"}
                  onSelect={(opt) => handleMCQSelect(currentQuestion.id, opt)}
                  onFlag={() => handleFlag(currentQuestion.id)}
                />
              ) : (
                <TheoryQuestionCard
                  key={currentQuestion.id}
                  question={currentQuestion}
                  questionNumber={currentQuestionIndex + 1}
                  totalQuestions={questions.length}
                  answer={answers[currentQuestion.id]?.text_answer || ""}
                  isFlagged={questionStatuses[currentQuestion.id] === "flagged"}
                  onChange={(text) => handleTheoryChange(currentQuestion.id, text)}
                  onFlag={() => handleFlag(currentQuestion.id)}
                />
              )}
            </AnimatePresence>
          </CardContent>

          {/* Navigation footer */}
          <div className="border-t px-6 py-4 flex items-center justify-between">
            <Button variant="outline" onClick={() => dispatch(prevQuestion())} disabled={currentQuestionIndex === 0} className="gap-2">
              <ChevronLeft className="w-4 h-4" />Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              {currentQuestionIndex + 1} / {questions.length}
            </span>
            <Button onClick={() => dispatch(nextQuestion())} disabled={currentQuestionIndex === questions.length - 1} className="gap-2">
              Next<ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </Card>

        {/* Navigator Sidebar (desktop) */}
        <div className="hidden md:block space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Questions</CardTitle>
            </CardHeader>
            <CardContent>
              <QuestionNavigator totalQuestions={questions.length} currentIndex={currentQuestionIndex} statuses={questionStatuses} questionIds={questionIds} onNavigate={(i) => dispatch(navigateToQuestion(i))} />
            </CardContent>
          </Card>
        </div>
      </div>
      
      <SessionFooter currentStep={3} />
    </div>
  );
}