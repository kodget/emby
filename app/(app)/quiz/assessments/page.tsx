"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AssessmentDraftGenerator, DraftGeneration } from "@/components/quiz/assessment-draft-generator";

type Question = {
  question_type: "mcq" | "theory"; question_text: string; difficulty: string;
  option_a?: string; option_b?: string; option_c?: string; option_d?: string;
  correct_option?: string; explanation?: string; ideal_answer?: string;
  maximum_marks: number; marking_rubric?: { criterion: string; marks: number }[];
};
type Paper = {
  id?: string; title: string; duration_minutes: number; mcq_count: number; theory_count: number;
  revision?: number; published_at?: string | null; closed_at?: string | null;
  answers_released_at?: string | null; questions?: Question[];
  has_ai_questions?: boolean; generation?: DraftGeneration | null;
  attempt?: { id: string; status: string } | null;
};
const emptyPaper = (): Paper => ({ title: "", duration_minutes: 30, mcq_count: 1, theory_count: 0, questions: [] });
const inputClass = "mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm";
const editable = (paper: Paper | null) => JSON.stringify(paper && [paper.title, paper.duration_minutes,
  paper.mcq_count, paper.theory_count, paper.questions]);

function message(error: unknown) {
  const data = (error as { response?: { data?: { error?: unknown; detail?: unknown } } }).response?.data;
  return String(data?.error || data?.detail || "The request failed. Your draft is still on this page; please retry.");
}

export default function AssessmentsPage() {
  const router = useRouter();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [canManage, setCanManage] = useState(false);
  const [draft, setDraft] = useState<Paper | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saved, setSaved] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const dirty = editable(draft) !== saved;
  const acceptDraft = (paper: Paper) => { setDraft(paper); setSaved(editable(paper)); setReviewed(false); };
  const updateGeneration = useCallback((value: DraftGeneration | null) => {
    setDraft(old => old && ({ ...old, generation: value }));
  }, []);
  useEffect(() => { setReviewed(false); }, [saved, draft?.title, draft?.duration_minutes,
    draft?.mcq_count, draft?.theory_count, draft?.questions]);

  const load = async () => {
    const { data } = await api.get("/api/formal-assessments/");
    setPapers(data.assessments); setCanManage(data.can_manage);
  };
  useEffect(() => { load().catch((e) => setError(message(e))).finally(() => setLoading(false)); }, []);

  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  };
  const editQuestion = (index: number, changes: Partial<Question>) => {
    setDraft((value) => value && ({ ...value, questions: value.questions?.map((q, i) => i === index ? { ...q, ...changes } : q) }));
  };
  const addQuestion = (type: "mcq" | "theory") => {
    const question: Question = { question_type: type, question_text: "", difficulty: "medium", maximum_marks: type === "mcq" ? 1 : 5 };
    if (type === "mcq") Object.assign(question, { option_a: "", option_b: "", option_c: "", option_d: "", correct_option: "A", explanation: "" });
    else Object.assign(question, { ideal_answer: "", marking_rubric: [{ criterion: "", marks: 5 }] });
    setDraft((value) => value && ({ ...value, questions: [...(value.questions || []), question] }));
  };
  const save = async () => {
    if (!draft) throw new Error("No draft selected");
    const body = { title: draft.title, duration_minutes: draft.duration_minutes, mcq_count: draft.mcq_count,
      theory_count: draft.theory_count, questions: draft.questions, ...(draft.id ? { revision: draft.revision } : {}) };
    const { data } = draft.id ? await api.patch(`/api/formal-assessments/${draft.id}/`, body)
      : await api.post("/api/formal-assessments/", body);
    acceptDraft(data); return data as Paper;
  };
  const publish = () => run(async () => {
    const paper = await save();
    const { data } = await api.post(`/api/formal-assessments/${paper.id}/publish/`, {
      revision: paper.revision, ...(paper.has_ai_questions ? { review_confirmed: reviewed } : {}),
    });
    setDraft(data); await load(); setNotice("Published. Students in your class can now start their one attempt.");
  });
  const generate = (operation: string, options: Record<string, unknown> = {}) => run(async () => {
    if (!draft) return;
    const paper = operation === "generate" && (dirty || !draft.id) ? await save() : draft;
    const { data } = await api.post(`/api/formal-assessments/${paper.id}/generation/`, {
      revision: paper.revision, job_id: paper.generation?.id, operation, ...options,
    });
    // Discarding must preserve unsaved manual edits.
    if (operation === "discard" && dirty) updateGeneration(data.generation);
    else acceptDraft(data);
    await load();
  });
  const start = (paper: Paper) => run(async () => {
    const { data } = await api.post(`/api/formal-assessments/${paper.id}/start/`, {});
    router.push(`/quiz/attempt/${data.id}${data.status === "in_progress" ? "" : "/results"}`);
  });
  const manage = (paper: Paper, action: string) => run(async () => {
    await api.post(`/api/formal-assessments/${paper.id}/${action}/`, {});
    await load(); setNotice(action === "close" ? "New entries are closed. Existing attempts keep their deadlines." : "Submitted students can now review the answers.");
  });

  return <main className="mx-auto max-w-4xl space-y-6 p-4 py-8">
    <Link href="/quiz" className="text-sm text-primary">Back to practice</Link>
    <div><h1 className="text-3xl font-bold">Class assessments</h1>
      <p className="mt-2 text-muted-foreground">Your class head sets each paper and time limit. You get one attempt; returning resumes the same timer.</p></div>
    {error && <div role="alert" className="rounded-md border border-destructive p-3 text-destructive">{error}</div>}
    {notice && <p role="status" className="rounded-md border p-3">{notice}</p>}
    {loading ? <p>Loading assessments…</p> : <>
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" disabled={busy} onClick={() => run(load)}>Refresh assessments</Button>
        {canManage && <Button disabled={busy} onClick={() => { setDraft(emptyPaper()); setError(""); setNotice(""); }}>Create assessment</Button>}
      </div>
      {!papers.length && <p className="text-muted-foreground">No assessments have been published for your class yet.</p>}
      <div className="space-y-3">{papers.map((paper) => <Card key={paper.id}>
        <CardHeader><CardTitle>{paper.title}</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p>{paper.mcq_count} MCQs · {paper.theory_count} theory questions · {paper.duration_minutes} minutes</p>
          <p className="text-sm text-muted-foreground">{!paper.published_at ? "Private draft" : paper.closed_at ? "Closed to new attempts" : "Published — one attempt per student"}
            {paper.answers_released_at ? " · Answers released" : " · Answers withheld until the class head releases them"}</p>
          <div className="flex flex-wrap gap-2">
            {canManage && <Button variant="outline" disabled={busy} onClick={() => run(async () => {
              const { data } = await api.get(`/api/formal-assessments/${paper.id}/`); acceptDraft(data);
            })}>{paper.published_at ? "View paper" : "Edit draft"}</Button>}
            {paper.published_at && (!paper.closed_at || paper.attempt) && <Button disabled={busy} onClick={() => start(paper)}>
              {paper.attempt ? paper.attempt.status === "in_progress" ? "Resume attempt" : "View result" : "Start timed assessment"}</Button>}
            {canManage && paper.published_at && !paper.closed_at && <Button variant="outline" disabled={busy} onClick={() => manage(paper, "close")}>Close new entries</Button>}
            {canManage && paper.closed_at && !paper.answers_released_at && <Button variant="outline" disabled={busy} onClick={() => manage(paper, "release-answers")}>Release answers</Button>}
          </div>
        </CardContent>
      </Card>)}</div>
    </>}
    {canManage && draft && <Card><CardHeader><CardTitle>{draft.published_at ? "Published paper" : "Assessment draft"}</CardTitle></CardHeader>
      <CardContent className="space-y-5">
        <p className="text-sm text-muted-foreground">Up to 50 MCQs, 5 theory questions and 150 minutes. Review every question and answer before publishing. Published papers cannot be edited.</p>
        <fieldset disabled={busy || !!draft.published_at} className="space-y-5 disabled:opacity-70">
          <label className="block text-sm">Assessment title<input className={inputClass} maxLength={200} value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></label>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">{([
            ["mcq_count", "MCQ count", 0, 50], ["theory_count", "Theory count", 0, 5], ["duration_minutes", "Time limit (minutes)", 1, 150],
          ] as const).map(([key, label, min, max]) => <label key={key} className="text-sm">{label}<input type="number" className={inputClass} min={min} max={max} value={draft[key]}
            onChange={(e) => setDraft({ ...draft, [key]: Number(e.target.value) })} /></label>)}</div>
          {(draft.questions || []).map((q, index) => <div key={index} className="space-y-3 rounded-lg border p-4">
            <div className="flex items-center justify-between gap-2"><h3 className="font-medium">Question {index + 1} · {q.question_type === "mcq" ? "MCQ" : "Theory"}</h3>
              <Button type="button" variant="ghost" onClick={() => setDraft({ ...draft, questions: draft.questions?.filter((_, i) => i !== index) })}>Remove question {index + 1}</Button></div>
            <label className="block text-sm">Question {index + 1} text<textarea className={inputClass} maxLength={20000} value={q.question_text} onChange={(e) => editQuestion(index, { question_text: e.target.value })} /></label>
            {q.question_type === "mcq" ? <>
              <div className="grid gap-3 sm:grid-cols-2">{(["a", "b", "c", "d"] as const).map((option) => <label key={option} className="text-sm">Question {index + 1} option {option.toUpperCase()}
                <input className={inputClass} maxLength={2000} value={q[`option_${option}`] || ""} onChange={(e) => editQuestion(index, { [`option_${option}`]: e.target.value })} /></label>)}</div>
              <label className="block text-sm">Question {index + 1} correct option<select className={inputClass} value={q.correct_option} onChange={(e) => editQuestion(index, { correct_option: e.target.value })}>{["A", "B", "C", "D"].map((option) => <option key={option}>{option}</option>)}</select></label>
              <label className="block text-sm">Question {index + 1} explanation<textarea className={inputClass} maxLength={20000} value={q.explanation || ""} onChange={(e) => editQuestion(index, { explanation: e.target.value })} /></label>
            </> : <>
              <label className="block text-sm">Question {index + 1} model answer<textarea className={inputClass} maxLength={20000} value={q.ideal_answer || ""} onChange={(e) => editQuestion(index, { ideal_answer: e.target.value })} /></label>
              <label className="block text-sm">Question {index + 1} maximum marks<input type="number" min={1} max={100} className={inputClass} value={q.maximum_marks} onChange={(e) => editQuestion(index, { maximum_marks: Number(e.target.value) })} /></label>
              {(q.marking_rubric || []).map((rubric, ri) => <div key={ri} className="grid gap-2 sm:grid-cols-3">
                <label className="text-sm sm:col-span-2">Criterion {ri + 1}<input className={inputClass} maxLength={2000} value={rubric.criterion} onChange={(e) => editQuestion(index, { marking_rubric: q.marking_rubric?.map((r, i) => i === ri ? { ...r, criterion: e.target.value } : r) })} /></label>
                <label className="text-sm">Criterion {ri + 1} marks<input type="number" min={1} max={100} className={inputClass} value={rubric.marks} onChange={(e) => editQuestion(index, { marking_rubric: q.marking_rubric?.map((r, i) => i === ri ? { ...r, marks: Number(e.target.value) } : r) })} /></label>
                <Button type="button" variant="ghost" onClick={() => editQuestion(index, { marking_rubric: q.marking_rubric?.filter((_, i) => i !== ri) })}>Remove criterion {ri + 1}</Button>
              </div>)}
              <Button type="button" variant="outline" onClick={() => editQuestion(index, { marking_rubric: [...(q.marking_rubric || []), { criterion: "", marks: 1 }] })}>Add marking criterion</Button>
              <p className="text-xs text-muted-foreground">Criterion marks must add up to the maximum. Written results remain pending until grading is completed.</p>
            </>}
          </div>)}
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" disabled={(draft.questions || []).filter((q) => q.question_type === "mcq").length >= draft.mcq_count} onClick={() => addQuestion("mcq")}>Add MCQ</Button>
            <Button type="button" variant="outline" disabled={(draft.questions || []).filter((q) => q.question_type === "theory").length >= draft.theory_count} onClick={() => addQuestion("theory")}>Add theory question</Button>
          </div>
        </fieldset>
        {!draft.published_at && <AssessmentDraftGenerator key={draft.id || "new"} paperId={draft.id}
          generation={draft.generation} busy={busy} dirty={dirty} onGeneration={updateGeneration} onAction={generate} />}
        {!draft.published_at && draft.has_ai_questions && <label className="flex gap-2 text-sm">
          <input type="checkbox" checked={reviewed} disabled={busy} onChange={e => setReviewed(e.target.checked)} />
          I have reviewed every generated question, correct answer, explanation and marking rubric in this paper.
        </label>}
        {!draft.published_at && <div className="flex flex-wrap gap-3">
          <Button disabled={busy} variant="outline" onClick={() => run(async () => { await save(); await load(); setNotice("Private draft saved."); })}>Save draft</Button>
          <Button disabled={busy || (!!draft.has_ai_questions && !reviewed)} onClick={publish}>Save and publish reviewed paper</Button>
        </div>}
      </CardContent>
    </Card>}
  </main>;
}
