"use client";

import { useEffect, useState, use, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Trophy, Target, Brain, ArrowRight, RefreshCw, BookOpen, Crown, CheckCircle, XCircle, AlertCircle, Clock, Layers } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import api from "@/lib/api";
import { useFeatureAccess } from "@/hooks/use-feature-access";

interface ResultData {
  id: string;
  score_percentage: number;
  mcq_score: number;
  mcq_total: number;
  total_mcq: number;
  theory_score: number | null;
  theory_total: number;
  total_theory: number;
  status: string;
  exam_type: string;
  subject_name?: string;
  time_taken_minutes?: number;
  passed?: boolean;
  grade?: string;
  topic_breakdown?: { topic_name: string; percentage: number; correct: number; total: number }[];
  difficulty_breakdown?: { difficulty: string; percentage: number; correct: number; total: number }[];
  weakest_topics?: string[];
  strongest_topics?: string[];
  avg_time_per_question_seconds?: number;
}

interface MissedQuestion {
  id: string;
  question_text: string;
  question_type: string;
  correct_option?: string;
  correct_answer?: string;
  selected_option?: string;
  student_answer?: string;
  explanation?: string;
  topic?: string;
  topic_name?: string;
}

function ResultsPageContent({ attemptId }: { attemptId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isSession = searchParams.get("session") === "true";
  const { hasAccess } = useFeatureAccess();
  const [result, setResult] = useState<ResultData | null>(null);
  const [missed, setMissed] = useState<MissedQuestion[]>([]);
  const [totalMissed, setTotalMissed] = useState(0);
  const [loading, setLoading] = useState(true);
  const [missedError, setMissedError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      // Fetch result first – if this fails, show error
      try {
        const resultRes = await api.get(`/api/quiz-attempts/${attemptId}/result/`);
        setResult(resultRes.data);
      } catch (e) {
        console.error("Failed to load result:", e);
        setLoading(false);
        return;
      }

      // Fetch missed questions independently – failure is non-fatal
      try {
        const missedRes = await api.get(`/api/quiz-attempts/${attemptId}/missed/`);
        setMissed(missedRes.data?.missed_questions ?? []);
        setTotalMissed(missedRes.data?.total_missed ?? missedRes.data?.count ?? 0);
      } catch (e: any) {
        const errData = e.response?.data;
        if (errData?.error) {
          setMissedError(errData.message || errData.error);
        }
        // Silently ignore other errors (missed questions not critical)
      }

      setLoading(false);
    };
    load();
  }, [attemptId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-muted-foreground">Calculating your results...</p>
        </div>
      </div>
    );
  }

  if (!result) return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Results not found</div>;

  const score = Math.round(result.score_percentage);
  const isPassing = score >= 50;
  const isPremium = hasAccess("premium" as any);

  // Normalize field names – backend returns both mcq_total and total_mcq
  const mcqTotal = result.total_mcq ?? result.mcq_total ?? 0;
  const theoryTotal = result.total_theory ?? result.theory_total ?? 0;

  const scoreColor = score >= 70 ? "text-emerald-600" : score >= 50 ? "text-amber-600" : "text-rose-600";
  const scoreBg = score >= 70 ? "bg-emerald-50" : score >= 50 ? "bg-amber-50" : "bg-rose-50";

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-accent/10">
      <div className="max-w-4xl mx-auto px-4 py-10 space-y-8">

        {/* Hero Score Card */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="border-2">
            <CardContent className="pt-8 pb-6 text-center">
              <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", delay: 0.2 }}
                className={`w-28 h-28 rounded-full mx-auto flex items-center justify-center mb-6 ${scoreBg}`}>
                {isPassing ? <Trophy className={`w-12 h-12 ${scoreColor}`} /> : <Target className="w-12 h-12 text-rose-500" />}
              </motion.div>
              <div className={`text-7xl font-bold mb-2 ${scoreColor}`}>{score}%</div>
              <p className="text-xl font-medium mb-1">{isPassing ? "Well done!" : "Keep practicing!"}</p>
              <div className="flex items-center justify-center gap-2 text-muted-foreground flex-wrap">
                {result.subject_name && <span>{result.subject_name}</span>}
                {result.subject_name && <span>•</span>}
                <span className="capitalize">{result.exam_type} exam</span>
                {result.grade && <Badge variant="outline" className="ml-1">{result.grade}</Badge>}
              </div>

              <Progress value={score} className="mt-6 h-3 max-w-xs mx-auto" />

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
                <div className="p-3 rounded-xl bg-card border text-center">
                  <div className="text-2xl font-bold text-primary">
                    {mcqTotal > 0 ? `${result.mcq_score}/${mcqTotal}` : "—"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">MCQ Score</div>
                </div>
                <div className="p-3 rounded-xl bg-card border text-center">
                  <div className="text-2xl font-bold text-emerald-600">
                    {theoryTotal > 0
                      ? (result.theory_score !== null && result.theory_score !== undefined
                          ? `${result.theory_score}/${theoryTotal}`
                          : "Pending")
                      : "—"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">Theory Score</div>
                </div>
                <div className="p-3 rounded-xl bg-card border text-center">
                  <div className="text-2xl font-bold text-amber-600">{totalMissed}</div>
                  <div className="text-xs text-muted-foreground mt-1">Missed</div>
                </div>
                <div className="p-3 rounded-xl bg-card border text-center">
                  <div className="text-2xl font-bold text-foreground flex items-center justify-center gap-1">
                    <Clock className="w-5 h-5" />
                    {result.time_taken_minutes != null ? `${Math.round(result.time_taken_minutes)}m` : "—"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">Time Taken</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Advanced Analytics */}
        {result.topic_breakdown && result.topic_breakdown.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="w-5 h-5 text-primary" /> Performance Analytics
                </CardTitle>
                <CardDescription>Detailed breakdown of your performance</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Topic Performance */}
                  <div className="space-y-4">
                    <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">By Topic</h4>
                    <div className="space-y-3">
                      {result.topic_breakdown.map((topic, i) => (
                        <div key={i} className="space-y-1">
                          <div className="flex justify-between text-sm">
                            <span className="font-medium truncate pr-2">{topic.topic_name}</span>
                            <span className="text-muted-foreground whitespace-nowrap">{topic.correct}/{topic.total} ({Math.round(topic.percentage)}%)</span>
                          </div>
                          <Progress value={topic.percentage} className="h-1.5" />
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Difficulty & Timing */}
                  <div className="space-y-6">
                    {result.difficulty_breakdown && result.difficulty_breakdown.length > 0 && (
                      <div className="space-y-4">
                        <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">By Difficulty</h4>
                        <div className="flex gap-4">
                          {result.difficulty_breakdown.map((diff, i) => (
                            <div key={i} className="flex-1 p-3 rounded-lg border bg-card text-center">
                              <div className="text-xs text-muted-foreground uppercase">{diff.difficulty}</div>
                              <div className="font-bold text-lg">{Math.round(diff.percentage)}%</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    <div className="grid grid-cols-2 gap-4">
                      {result.weakest_topics && result.weakest_topics.length > 0 && (
                        <div className="p-3 rounded-lg border border-rose-100 bg-rose-50/30 text-sm">
                          <div className="text-rose-600 font-semibold mb-1 flex items-center gap-1"><ArrowRight className="w-3 h-3" /> Focus on</div>
                          <div className="text-muted-foreground truncate">{result.weakest_topics[0]}</div>
                        </div>
                      )}
                      {result.avg_time_per_question_seconds !== undefined && (
                        <div className="p-3 rounded-lg border bg-card text-sm">
                          <div className="text-muted-foreground font-semibold mb-1 flex items-center gap-1"><Clock className="w-3 h-3" /> Avg. Time</div>
                          <div>{result.avg_time_per_question_seconds}s per question</div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Flashcard Banner — appears when student missed questions */}
        {totalMissed > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
            <div className="rounded-2xl bg-violet-950/60 border border-violet-500/30 px-6 py-5 flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-violet-500/20 border border-violet-500/30 flex items-center justify-center flex-shrink-0">
                <Layers className="w-5 h-5 text-violet-400" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-violet-200 text-sm">
                  {totalMissed} flashcard{totalMissed !== 1 ? "s" : ""} added to your review queue
                </p>
                <p className="text-violet-300/60 text-xs mt-0.5">
                  Questions you missed are now in spaced repetition — review them before they fade!
                </p>
              </div>
              <Link
                href="/flashcards/study"
                id="review-flashcards-now-btn"
                className="flex-shrink-0 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors whitespace-nowrap"
              >
                Review Now
              </Link>
            </div>
          </motion.div>
        )}

        {/* Missed Questions */}
        {missed.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 text-rose-500" />Review These Questions
                </CardTitle>
                <CardDescription>
                  Study {totalMissed > missed.length ? `these ${missed.length} of ${totalMissed}` : `these ${missed.length}`} questions to improve your score
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {missed.map((q, i) => {
                  const userAnswer = q.selected_option || q.student_answer;
                  const correctAnswer = q.correct_option || q.correct_answer;
                  return (
                    <motion.div key={q.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
                      <div className="p-4 rounded-xl border border-rose-100 bg-rose-50/50 space-y-3">
                        <div className="flex items-start gap-2">
                          <XCircle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
                          <p className="font-medium text-sm">{q.question_text}</p>
                        </div>
                        {q.question_type === "mcq" && (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                            <div className="flex items-center gap-1.5 text-emerald-700 bg-emerald-50 rounded-lg px-3 py-1.5">
                              <CheckCircle className="w-3.5 h-3.5 flex-shrink-0" />
                              <span><strong>Correct:</strong> {correctAnswer || "—"}</span>
                            </div>
                            <div className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 ${userAnswer ? "text-rose-600 bg-rose-50" : "text-muted-foreground bg-muted/40"}`}>
                              <XCircle className="w-3.5 h-3.5 flex-shrink-0" />
                              <span><strong>Your answer:</strong> {userAnswer || "No answer"}</span>
                            </div>
                          </div>
                        )}
                        {q.explanation && (
                          <div className="p-3 rounded-lg bg-white border text-sm text-muted-foreground">
                            <span className="font-medium text-foreground">Explanation: </span>{q.explanation}
                          </div>
                        )}
                        {q.topic && (
                          <Badge variant="outline" className="text-xs">{q.topic}</Badge>
                        )}
                      </div>
                    </motion.div>
                  );
                })}

                {/* Premium upsell when more questions are locked */}
                {!isPremium && totalMissed > missed.length && (
                  <div className="p-4 rounded-xl border-2 border-dashed border-primary/20 text-center space-y-2">
                    <Crown className="w-6 h-6 text-primary mx-auto" />
                    <p className="font-medium">Unlock {totalMissed - missed.length} more missed questions</p>
                    <p className="text-sm text-muted-foreground">Upgrade to Premium for full review access, AI explanations, and detailed feedback</p>
                    <Button size="sm" onClick={() => router.push("/upgrade")} className="mt-2">Upgrade to Premium</Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* No missed questions - show congrats */}
        {!loading && missed.length === 0 && totalMissed === 0 && mcqTotal > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <Card className="border-emerald-200 bg-emerald-50/30">
              <CardContent className="pt-6 pb-6 text-center space-y-2">
                <CheckCircle className="w-10 h-10 text-emerald-600 mx-auto" />
                <p className="font-semibold text-emerald-700">Perfect Score on MCQs!</p>
                <p className="text-sm text-muted-foreground">You answered all MCQ questions correctly.</p>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Action Buttons */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="flex flex-col sm:flex-row gap-3 justify-center">
          {isSession ? (
            <Button onClick={() => router.push(`/session?step=3&quizId=${attemptId}`)} className="gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold">
              Next: Review Mistakes <ArrowRight className="w-4 h-4" />
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => router.push("/quiz")} className="gap-2">
                <RefreshCw className="w-4 h-4" />Take Another Quiz
              </Button>
              <Button onClick={() => router.push("/dashboard")} className="gap-2">
                <ArrowRight className="w-4 h-4" />Back to Dashboard
              </Button>
            </>
          )}
        </motion.div>

      </div>
    </div>
  );
}

export default function ResultsPage({ params }: { params: Promise<{ id: string }> }) {
  const unwrappedParams = use(params);
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <ResultsPageContent attemptId={unwrappedParams.id} />
    </Suspense>
  );
}