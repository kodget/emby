"use client";

import { useEffect, useState, use, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Trophy, Target, Brain, ArrowRight, RefreshCw, BookOpen, Crown, CheckCircle, XCircle, AlertCircle, Clock, Layers, Sparkles } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import api from "@/lib/api";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { SessionFooter } from "@/components/session-footer";

interface ResultData {
  historical_read_only?: boolean;
  history_notice?: string;
  recorded_result?: { mcq_score: number; mcq_total: number; theory_score: number | string; overall_percentage: number } | null;
  feedback?: {
    note: string; mcq: { correct: number; incorrect: number; unanswered: number };
    difficulty_breakdown: { difficulty: string; correct: number; incorrect: number; unanswered: number; total: number; sufficient_evidence: boolean }[];
    questions_to_review: { question_id: string; question_number: number; question_text: string; outcome: string;
      next_step: string; explanation?: string; criteria_to_review?: { criterion: string; marks_allocated: number; marks_awarded: number; feedback: string }[] }[];
  } | null;
  assessment?: string | null;
  answers_released?: boolean;
  theory_grading_pending?: boolean;
  grading?: { status: string; can_retry: boolean; completed_questions: number; total_questions: number; retry_after?: string | null } | null;
  questions?: (MissedQuestion & { option_a?: string; option_b?: string; option_c?: string; option_d?: string })[];
  responses?: { question: { id: string }; selected_option?: string; text_answer?: string; is_correct?: boolean;
    ai_score?: number | string | null; ai_evaluation_status?: string; ai_feedback?: { feedback?: string };
    ai_rubric_breakdown?: { criterion: string; marks_allocated: number; marks_awarded: number; feedback: string }[] }[];
  id: string;
  overall_percentage: number;
  mcq_score: number;
  mcq_total: number;
  total_mcq: number;
  theory_score: number | string | null;
  theory_total: number;
  total_theory: number;
  status: string;
  started_at?: string;
  submitted_at?: string;
  exam_type: string;
  subject_name?: string;
  time_taken_minutes?: number;
  passed?: boolean;
  grade?: string;
  analysis_data?: {
    theory_maximum_marks?: number;
    total_maximum_marks?: number;
    insights?: string;
    next_steps?: string;
    weakest_topics?: string[];
  };
  topic_breakdown?: { topic_name: string; percentage: number; correct: number; total: number }[];
  difficulty_breakdown?: { difficulty: string; percentage: number; correct: number; total: number }[];
  weakest_topics?: string[];
  strongest_topics?: string[];
  avg_time_per_question_seconds?: number;
}

interface MissedQuestion {
  maximum_marks?: number;
  ideal_answer?: string;
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
  const nextStep = searchParams.get("nextStep") || "4";
  const { hasAccess } = useFeatureAccess();
  const [result, setResult] = useState<ResultData | null>(null);
  const [missed, setMissed] = useState<MissedQuestion[]>([]);
  const [totalMissed, setTotalMissed] = useState(0);
  const [loading, setLoading] = useState(true);
  const [missedError, setMissedError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const [statusError, setStatusError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setStatusError("");
      // Fetch result first – if this fails, show error
      try {
        const resultRes = await api.get(`/api/quiz-attempts/${attemptId}/result/`);
        if (cancelled) return;
        setResult(resultRes.data);
      } catch (e) {
        if (cancelled) return;
        setStatusError("Could not load the latest result. Please retry.");
        console.error("Failed to load result:", e);
        setLoading(false);
        return;
      }

      // Fetch missed questions independently – failure is non-fatal
      try {
        const missedRes = await api.get(`/api/quiz-attempts/${attemptId}/missed/`);
        if (cancelled) return;
        setMissed(missedRes.data?.missed_questions ?? []);
        setTotalMissed(missedRes.data?.total_missed ?? missedRes.data?.count ?? 0);
      } catch (e: any) {
        if (cancelled) return;
        const errData = e.response?.data;
        if (errData?.error) {
          setMissedError(errData.message || errData.error);
        }
        // Silently ignore other errors (missed questions not critical)
      }

      setLoading(false);
    };
    load();
    return () => { cancelled = true; };
  }, [attemptId, refresh]);

  useEffect(() => {
    if (!result?.theory_grading_pending || !result.grading || result.grading.status === "failed") return;
    const timer = setTimeout(() => setRefresh(value => value + 1), 15000);
    return () => clearTimeout(timer);
  }, [result]);

  const retryGrading = async () => {
    setRetrying(true); setStatusError("");
    try {
      await api.post(`/api/quiz-attempts/${attemptId}/retry-grading/`, {});
      setRefresh(value => value + 1);
    } catch (error: any) {
      setStatusError(error.response?.data?.error || "Grading could not be queued. Please try again.");
    } finally { setRetrying(false); }
  };

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

  if (!result) return <div className="min-h-screen flex flex-col gap-3 items-center justify-center text-muted-foreground"><p role="alert">{statusError || "Results not found"}</p><Button onClick={() => setRefresh(value => value + 1)}>Refresh result</Button></div>;

  if (result.historical_read_only) return <main className="mx-auto max-w-3xl space-y-4 p-6">
    <h1 className="text-2xl font-bold">Historical assessment record</h1>
    <p>{result.history_notice}</p>
    {result.recorded_result ? <p>Previously recorded score: {result.recorded_result.overall_percentage}% (unverified).</p>
      : <p>This attempt was never submitted.</p>}
    <p>Available saved responses:</p>
    {(result.responses || []).map((response, index) => <div key={index} className="rounded border p-3">
      <p>Response {index + 1}</p><p>{response.text_answer || response.selected_option || "No answer recorded"}</p>
    </div>)}
    <Link href="/quiz">Start a new practice or mock exam</Link>
  </main>;

  const score = Math.round(result.overall_percentage ?? 0);
  const isPassing = score >= 50;
  const isPremium = hasAccess("premium" as any);

  // Normalize field names – backend returns both mcq_total and total_mcq
  const mcqTotal = result.total_mcq ?? result.mcq_total ?? 0;
  const theoryTotal = result.total_theory ?? result.theory_total ?? 0;
  
  let timeTakenMinutes = result.time_taken_minutes;
  if (timeTakenMinutes == null && result.started_at && result.submitted_at) {
    const start = new Date(result.started_at);
    const end = new Date(result.submitted_at);
    timeTakenMinutes = (end.getTime() - start.getTime()) / (1000 * 60);
  }

  const scoreColor = score >= 70 ? "text-emerald-600" : score >= 50 ? "text-amber-600" : "text-rose-600";
  const scoreBg = score >= 70 ? "bg-emerald-50" : score >= 50 ? "bg-amber-50" : "bg-rose-50";

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-accent/10">
      <div className="max-w-4xl mx-auto px-4 py-10 space-y-8">
        {statusError && <p role="alert" className="rounded border border-destructive p-3 text-destructive">{statusError}</p>}
        {result.feedback && <Card><CardHeader><CardTitle>Study guidance from this paper</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">{result.feedback.note}</p>
            <p>MCQs: {result.feedback.mcq.correct} correct, {result.feedback.mcq.incorrect} incorrect, {result.feedback.mcq.unanswered} unanswered.</p>
            {result.feedback.difficulty_breakdown.map(row => <p key={row.difficulty} className="text-sm">
              {row.difficulty}: {row.correct}/{row.total} correct
              {!row.sufficient_evidence && " — too few questions to infer a pattern."}
            </p>)}
            {!result.feedback.questions_to_review.length && <p>No missed questions or rubric gaps were recorded in this paper. Try a different paper to broaden the evidence.</p>}
            {result.feedback.questions_to_review.map(row => <div key={row.question_id} className="rounded border p-3 space-y-2">
              <h3 className="font-medium">Question {row.question_number}: {row.question_text}</h3>
              <p className="text-sm">Recorded outcome: {row.outcome}</p>
              {row.explanation && <p className="text-sm">{row.explanation}</p>}
              {row.criteria_to_review?.map((criterion, index) => <p key={index} className="text-sm">
                {criterion.criterion}: {criterion.marks_awarded}/{criterion.marks_allocated}. {criterion.feedback}
              </p>)}
              <p className="text-sm">{row.next_step}</p>
            </div>)}
          </CardContent></Card>}
        {result.grading && <Card><CardHeader><CardTitle>Written grading</CardTitle></CardHeader><CardContent className="space-y-3">
          <p role="status">{result.grading.status === "completed" ? "Written grading complete." : result.grading.status === "failed" ? "Grading could not finish. Your answers and completed marks are saved." : result.grading.status === "retry_wait" ? "Grading was interrupted and will retry automatically." : result.grading.status === "running" ? "Your written answers are being graded." : "Your written answers are queued for grading."}</p>
          <p>{result.grading.completed_questions} of {result.grading.total_questions} written questions graded.</p>
          <div className="flex gap-3 flex-wrap"><Button variant="outline" disabled={retrying} onClick={() => setRefresh(value => value + 1)}>Refresh result</Button>
            {result.grading.status === "failed" && <Button disabled={retrying || !result.grading.can_retry} onClick={retryGrading}>Retry grading</Button>}</div>
          {result.grading.status === "failed" && !result.grading.can_retry && <p className="text-sm text-muted-foreground">Please wait a few minutes, then refresh to retry. Completed questions will keep their marks.</p>}
        </CardContent></Card>}

        {/* Hero Score Card */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="border-2">
            <CardContent className="pt-8 pb-6 text-center">
              <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", delay: 0.2 }}
                className={`w-28 h-28 rounded-full mx-auto flex items-center justify-center mb-6 ${scoreBg}`}>
                {isPassing ? <Trophy className={`w-12 h-12 ${scoreColor}`} /> : <Target className="w-12 h-12 text-rose-500" />}
              </motion.div>
              <div className={`text-7xl font-bold mb-2 ${scoreColor}`}>{result.theory_grading_pending && !mcqTotal ? "Pending" : `${score}%`}</div>
              <p className="text-xl font-medium mb-1">{result.theory_grading_pending ? mcqTotal ? "MCQ result only — written grading is pending" : "Written grading is pending" : isPassing ? "Well done!" : "Keep practicing!"}</p>
              {(result.assessment || result.exam_type === "mock") && !result.theory_grading_pending && result.analysis_data?.total_maximum_marks !== undefined && <p className="text-sm text-muted-foreground">Overall mark: {result.mcq_score + Number(result.theory_score || 0)} / {result.analysis_data.total_maximum_marks}</p>}
              {result.assessment && !result.answers_released && <p className="mt-3 text-sm text-muted-foreground">Answer keys will be available after your class head closes entries and releases them.</p>}
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
                      ? (!result.theory_grading_pending && result.theory_score !== null && result.theory_score !== undefined
                          ? `${result.theory_score}/${result.analysis_data?.theory_maximum_marks ?? theoryTotal}`
                          : "Pending")
                      : "—"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">Theory Score</div>
                </div>
                <div className="p-3 rounded-xl bg-card border text-center">
                  <div className="text-2xl font-bold text-amber-600">{result.assessment && !result.answers_released ? "Withheld" : totalMissed}</div>
                  <div className="text-xs text-muted-foreground mt-1">{result.assessment ? "Missed MCQs" : "Missed"}</div>
                </div>
                <div className="p-3 rounded-xl bg-card border text-center">
                  <div className="text-2xl font-bold text-foreground flex items-center justify-center gap-1">
                    <Clock className="w-5 h-5" />
                    {timeTakenMinutes != null ? `${Math.round(timeTakenMinutes)}m` : "—"}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">Time Taken</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Exam Features Highlights */}
        {result.exam_type === "mock" && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <div className="flex flex-wrap items-center justify-center gap-4 py-2">
              <Badge variant="secondary" className="px-3 py-1.5 text-sm gap-2 bg-amber-50 text-amber-700 border-amber-200">
                <Clock className="w-4 h-4" /> Timed practice
              </Badge>
              <Badge variant="secondary" className="px-3 py-1.5 text-sm gap-2 bg-amber-50 text-amber-700 border-amber-200">
                <Brain className="w-4 h-4" /> Performance analytics
              </Badge>
              <Badge variant="secondary" className="px-3 py-1.5 text-sm gap-2 bg-amber-50 text-amber-700 border-amber-200">
                <Layers className="w-4 h-4" /> Detailed breakdown
              </Badge>
            </div>
          </motion.div>
        )}
        
        {result.exam_type === "formal" && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <div className="flex flex-wrap items-center justify-center gap-4 py-2">
              <Badge variant="secondary" className="px-3 py-1.5 text-sm gap-2 bg-primary/10 text-primary border-primary/20">
                <CheckCircle className="w-4 h-4" /> One attempt
              </Badge>
              <Badge variant="secondary" className="px-3 py-1.5 text-sm gap-2 bg-primary/10 text-primary border-primary/20">
                <Clock className="w-4 h-4" /> Class-head time limit
              </Badge>
              <Badge variant="secondary" className="px-3 py-1.5 text-sm gap-2 bg-primary/10 text-primary border-primary/20">
                <BookOpen className="w-4 h-4" /> Saved answers
              </Badge>
            </div>
          </motion.div>
        )}

        {/* AI Performance Analysis (Mock & Formal) */}
        {!isPremium && result.exam_type === "mock" && (result.analysis_data?.insights || result.analysis_data?.next_steps) ? (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card className="border-indigo-200 bg-indigo-50/30 overflow-hidden relative">
              <div className="absolute inset-0 bg-white/40 backdrop-blur-[2px] z-10 flex flex-col items-center justify-center p-6 text-center">
                <Crown className="w-12 h-12 text-amber-500 mb-4" />
                <h3 className="text-xl font-bold text-indigo-950 mb-2">Unlock Deep AI Analysis</h3>
                <p className="text-indigo-800 mb-6 max-w-md">Upgrade to premium to get better analysis of your performance, including key insights and a personalized action plan.</p>
                <Link href="/premium">
                  <Button className="bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg">
                    Upgrade to Premium
                  </Button>
                </Link>
              </div>
              <CardHeader className="opacity-40">
                <CardTitle className="flex items-center gap-2 text-indigo-900">
                  <Brain className="w-5 h-5 text-indigo-600" /> AI Performance Analysis
                </CardTitle>
                <CardDescription>Detailed insights and recommended next steps</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6 opacity-40 blur-sm pointer-events-none">
                <div className="space-y-2">
                  <h4 className="font-semibold text-indigo-900 text-sm flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-indigo-600" /> Key Insights
                  </h4>
                  <div className="space-y-2">
                    <div className="h-4 bg-indigo-200 rounded w-full"></div>
                    <div className="h-4 bg-indigo-200 rounded w-5/6"></div>
                    <div className="h-4 bg-indigo-200 rounded w-4/6"></div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ) : result.analysis_data && (result.analysis_data.insights || result.analysis_data.next_steps) ? (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card className="border-indigo-200 bg-indigo-50/30">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-indigo-900">
                  <Brain className="w-5 h-5 text-indigo-600" /> AI Performance Analysis
                </CardTitle>
                <CardDescription>Detailed insights and recommended next steps</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {result.analysis_data.insights && (
                  <div className="space-y-2">
                    <h4 className="font-semibold text-indigo-900 text-sm flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-indigo-600" /> Key Insights
                    </h4>
                    <p className="text-sm text-indigo-800/80 leading-relaxed whitespace-pre-wrap">
                      {result.analysis_data.insights}
                    </p>
                  </div>
                )}
                {result.analysis_data.next_steps && (
                  <div className="space-y-2">
                    <h4 className="font-semibold text-indigo-900 text-sm flex items-center gap-2">
                      <ArrowRight className="w-4 h-4 text-indigo-600" /> Recommended Action Plan
                    </h4>
                    <p className="text-sm text-indigo-800/80 leading-relaxed whitespace-pre-wrap">
                      {result.analysis_data.next_steps}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        ) : null}


        {/* Advanced Analytics */}
        {result.topic_breakdown && result.topic_breakdown.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="w-5 h-5 text-primary" /> Performance Analytics
                </CardTitle>
                <CardDescription>MCQ topic review, including unanswered questions.</CardDescription>
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

        {(result.exam_type === "practice" || result.exam_type === "mock" || (result.assessment && result.answers_released)) && result.questions && <Card>
          <CardHeader><CardTitle>Answer review</CardTitle><CardDescription>Your saved answers and the correct answer for each question.</CardDescription></CardHeader>
          <CardContent className="space-y-5">{result.questions.filter(q => q.question_type === "mcq").map((q, index) => {
            const response = result.responses?.find(r => r.question?.id === q.id);
            const option = q[`option_${q.correct_option?.toLowerCase()}` as "option_a" | "option_b" | "option_c" | "option_d"];
            return <div key={q.id} className="rounded border p-4 space-y-2">
              <p className="font-medium">{index + 1}. {q.question_text}</p>
              <p>{!response ? "Unanswered" : response.is_correct ? "Correct" : "Incorrect"} · Your answer: {response?.selected_option ?? "None"}</p>
              <p>Correct answer: {q.correct_option}{option ? ` — ${option}` : ""}</p>
              {result.exam_type === "mock" && q.explanation && <p>Explanation: {q.explanation}</p>}
            </div>;
          })}</CardContent>
        </Card>}
        {(result.assessment || result.exam_type === "mock") && result.questions?.some(q => q.question_type === "theory") && <Card>
          <CardHeader><CardTitle>Your written answers</CardTitle><CardDescription>{result.theory_grading_pending ? "Grading is pending. These are your saved answers." : "Saved written responses."}</CardDescription></CardHeader>
          <CardContent className="space-y-5">{result.questions.filter(q => q.question_type === "theory").map(q => {
            const response = result.responses?.find(r => r.question?.id === q.id);
            return <div key={q.id} className="space-y-2 rounded border p-4">
            <p className="font-medium">{q.question_text}</p>
            <p className="whitespace-pre-wrap">{response?.text_answer || "Unanswered"}</p>
            <p>{response?.ai_evaluation_status === "completed" ? `Written mark: ${response.ai_score} / ${q.maximum_marks}` : "Mark pending"}</p>
            {result.answers_released && response?.ai_feedback?.feedback && <p className="whitespace-pre-wrap">Feedback: {response.ai_feedback.feedback}</p>}
            {result.answers_released && response?.ai_rubric_breakdown?.map((row, i) => <div key={i} className="border-l-2 pl-3 text-sm"><p>{row.criterion}: {row.marks_awarded} / {row.marks_allocated}</p><p>{row.feedback}</p></div>)}
            {result.answers_released && q.ideal_answer && <p className="whitespace-pre-wrap">Model answer: {q.ideal_answer}</p>}
          </div>; })}</CardContent>
        </Card>}
        {/* Link to review resources; no flashcard creation is implied. */}
        {totalMissed > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
            <div className="rounded-2xl bg-violet-950/60 border border-violet-500/30 px-6 py-5 flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-violet-500/20 border border-violet-500/30 flex items-center justify-center flex-shrink-0">
                <Layers className="w-5 h-5 text-violet-400" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-violet-200 text-sm">
                  Review what you missed
                </p>
                <p className="text-violet-300/60 text-xs mt-0.5">
                  Revisit these questions and use flashcards to practise the underlying concepts.
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
        {result.exam_type !== "practice" && missed.length > 0 && (
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
        {!loading && !missedError && missed.length === 0 && totalMissed === 0 && mcqTotal > 0 && result.mcq_score === mcqTotal && (
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
          {!isSession && (
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
      {isSession && <SessionFooter currentStep={3} />}
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
