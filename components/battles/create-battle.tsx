"use client";

import { useState, useEffect, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, Plus, Trophy, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import api from "@/lib/api";

type HierarchyItem = { id: string | number; name: string };
type Question = { question: string; options: string[]; correct_index: number; explanation: string };
const blankQuestion = (): Question => ({ question: "", options: ["", "", "", ""], correct_index: 0, explanation: "" });
const selectStyle = "h-11 w-full rounded-md border border-input bg-background px-3 text-sm";

export function CreateBattle() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("manual");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("mixed");
  const [numQuestions, setNumQuestions] = useState(10);
  const [timePerQuestion, setTimePerQuestion] = useState(20);
  const [questions, setQuestions] = useState<Question[]>([blankQuestion()]);
  const [subjects, setSubjects] = useState<HierarchyItem[]>([]);
  const [subjectId, setSubjectId] = useState("");
  const [subjectError, setSubjectError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.get("/api/subjects/").then(res => {
      if (!cancelled) setSubjects(res.data.results ?? res.data ?? []);
    }).catch(() => { if (!cancelled) setSubjectError(true); });
    return () => { cancelled = true; };
  }, []);

  const updateQuestion = (index: number, update: Partial<Question>) => {
    setQuestions(previous => previous.map((q, i) => i === index ? { ...q, ...update } : q));
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (isSubmitting) return;
    setError("");
    if (!title.trim()) { setError("Enter a battle title."); return; }
    if (source === "ai" && !topic.trim() && !subjectId) {
      setError("Choose a course or enter a topic for the AI questions."); return;
    }
    if (source === "manual" && questions.some(q => !q.question.trim() || q.options.some(o => !o.trim()))) {
      setError("Complete each question and its answer options."); return;
    }
    if (source === "manual" && questions.some(q => new Set(q.options.map(o => o.trim().toLowerCase())).size !== q.options.length)) {
      setError("Each question must have different answer options."); return;
    }
    setIsSubmitting(true);
    try {
      const response = await api.post("/api/battles/", {
        title: title.trim(), topic: topic.trim(), difficulty,
        question_source: source, num_questions: numQuestions,
        time_per_question: timePerQuestion, linked_subject: subjectId || null,
        ...(source === "manual" ? { manual_questions: questions } : {}),
      }, { timeout: 120000 });
      if (source === "ai") window.dispatchEvent(new Event("credits-updated"));
      router.push(`/battles/${response.data.id}`);
    } catch (err: any) {
      const detail = err?.response?.data;
      const message = typeof detail?.detail === "string" ? detail.detail
        : Array.isArray(detail) ? detail.join(" ")
        : typeof detail === "object" && detail ? Object.values(detail).flat().filter(v => typeof v === "string").join(" ") : "";
      setError(message || "Could not create the battle. Check your class membership and connection, then try again.");
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleCreate} className="mx-auto max-w-3xl space-y-6 pb-12">
      <Button variant="ghost" asChild><Link href="/battles"><ArrowLeft className="mr-2 size-4" /> Brain Battles</Link></Button>
      <div>
        <h1 className="flex items-center gap-2 text-3xl font-bold"><Trophy className="size-8 text-primary" /> Host a Brain Battle</h1>
        <p className="mt-2 text-muted-foreground">Create questions, share your game code, then start a timed quiz together.</p>
      </div>
      <fieldset disabled={isSubmitting} className="space-y-6 rounded-2xl border bg-card p-5 sm:p-7">
        <div className="space-y-2"><Label htmlFor="battle-title">Battle title</Label><Input id="battle-title" value={title} onChange={e => setTitle(e.target.value)} maxLength={200} required placeholder="Friday anatomy showdown" /></div>
        <div className="space-y-2"><Label htmlFor="battle-source">Questions</Label><select id="battle-source" className={selectStyle} value={source} onChange={e => setSource(e.target.value)}><option value="manual">Write my own questions — no AI credits</option><option value="ai">Generate with AI — uses AI credits</option></select></div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2"><Label htmlFor="battle-course">Course (optional)</Label><select id="battle-course" className={selectStyle} value={subjectId} onChange={e => setSubjectId(e.target.value)}><option value="">General topic</option>{subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>{subjectError && <p className="text-sm text-muted-foreground">Courses could not load. You can still write your questions or enter an AI topic.</p>}</div>
          <div className="space-y-2"><Label htmlFor="battle-seconds">Seconds per question</Label><Input id="battle-seconds" type="number" min={5} max={300} value={timePerQuestion} onChange={e => setTimePerQuestion(Number(e.target.value))} required /></div>
        </div>
        {source === "ai" ? <div className="space-y-5">
          <div className="space-y-2"><Label htmlFor="battle-topic">Topic for AI questions</Label><Input id="battle-topic" value={topic} onChange={e => setTopic(e.target.value)} maxLength={200} placeholder="For example, the brachial plexus" /><p className="text-xs text-muted-foreground">Questions are generated from the chosen topic. Review them before starting the game.</p></div>
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="battle-count">Number of questions</Label><Input id="battle-count" type="number" min={1} max={40} value={numQuestions} onChange={e => setNumQuestions(Number(e.target.value))} required /></div>
            <div className="space-y-2"><Label htmlFor="battle-difficulty">Difficulty</Label><select id="battle-difficulty" className={selectStyle} value={difficulty} onChange={e => setDifficulty(e.target.value)}>{["easy", "medium", "hard", "mixed"].map(value => <option key={value} value={value}>{value}</option>)}</select></div>
          </div>
        </div> : <div className="space-y-5">
          {questions.map((q, index) => <section key={index} className="space-y-4 rounded-xl border p-4" aria-label={`Question ${index + 1}`}>
            <div className="flex items-center justify-between"><h2 className="font-semibold">Question {index + 1}</h2><Button type="button" variant="ghost" size="icon" aria-label={`Remove question ${index + 1}`} disabled={questions.length === 1} onClick={() => setQuestions(all => all.filter((_, i) => i !== index))}><Trash2 className="size-4" /></Button></div>
            <Textarea aria-label={`Question ${index + 1} text`} value={q.question} onChange={e => updateQuestion(index, { question: e.target.value })} maxLength={3000} required placeholder="Enter your question" />
            <div className="space-y-2"><p className="text-sm text-muted-foreground">Select the correct answer.</p>{q.options.map((option, answerIndex) => <label key={answerIndex} className="flex items-center gap-3"><input type="radio" name={`correct-${index}`} checked={q.correct_index === answerIndex} onChange={() => updateQuestion(index, { correct_index: answerIndex })} aria-label={`Question ${index + 1} correct answer ${answerIndex + 1}`} /><Input aria-label={`Question ${index + 1} option ${answerIndex + 1}`} value={option} onChange={e => updateQuestion(index, { options: q.options.map((o, i) => i === answerIndex ? e.target.value : o) })} maxLength={1000} required placeholder={`Option ${answerIndex + 1}`} /></label>)}</div>
            <Textarea aria-label={`Question ${index + 1} explanation`} value={q.explanation} onChange={e => updateQuestion(index, { explanation: e.target.value })} maxLength={5000} placeholder="Explanation (optional)" />
          </section>)}
          <Button type="button" variant="outline" disabled={questions.length >= 40} onClick={() => setQuestions(all => [...all, blankQuestion()])}><Plus className="mr-2 size-4" /> Add question ({questions.length}/40)</Button>
        </div>}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button type="submit" className="w-full" disabled={isSubmitting}>{isSubmitting ? <><Loader2 className="mr-2 size-4 animate-spin" /> {source === "ai" ? "Generating questions…" : "Creating lobby…"}</> : source === "ai" ? "Generate questions and open lobby" : "Create lobby"}</Button>
      </fieldset>
    </form>
  );
}
