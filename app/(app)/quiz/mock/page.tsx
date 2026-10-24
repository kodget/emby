"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { Button } from "@/components/ui/button";

type Item = { id: string; name: string; subject?: string; block?: string };
type Scope = "course" | "module" | "submodule";
type Counts = { mcq: number; theory: number };
type Availability = { scopeKey: string; available: Record<string, Counts> };
const rows = (data: any): Item[] => Array.isArray(data) ? data : data.results ?? [];

export default function MockExamPage() {
  const router = useRouter();
  const { isPremium } = useFeatureAccess();
  const [subjects, setSubjects] = useState<Item[]>([]);
  const [blocks, setBlocks] = useState<Item[]>([]);
  const [subs, setSubs] = useState<Item[]>([]);
  const [subject, setSubject] = useState("");
  const [block, setBlock] = useState("");
  const [sub, setSub] = useState("");
  const [scope, setScope] = useState<Scope>("course");
  const [difficulty, setDifficulty] = useState("medium");
  const [mcq, setMcq] = useState(20);
  const [theory, setTheory] = useState(2);
  const [timed, setTimed] = useState(true);
  const [minutes, setMinutes] = useState(30);
  const [available, setAvailable] = useState<Availability | null>(null);
  const [checking, setChecking] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [catalogError, setCatalogError] = useState("");
  const [reload, setReload] = useState(0);
  const scopeId = scope === "course" ? subject : scope === "module" ? block : sub;

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setCatalogError("");
      try {
        // Follow API pagination so larger classes retain every selectable scope.
        const all = async (path: string) => {
          let next: string | null = path;
          const items: Item[] = [];
          const visited = new Set<string>();
          while (next) {
            if (cancelled) return [];
            if (visited.has(next)) throw new Error("Repeated catalogue page");
            visited.add(next);
            const response: any = await api.get(next);
            items.push(...rows(response.data));
            next = Array.isArray(response.data) ? null : response.data.next;
          }
          return items;
        };
        const [courses, modules, submodules] = await Promise.all([
          all("/api/subjects/"), all("/api/blocks/"), all("/api/sub-blocks/"),
        ]);
        if (!cancelled) { setSubjects(courses); setBlocks(modules); setSubs(submodules); }
      } catch { if (!cancelled) setCatalogError("Could not load courses and modules. Please retry."); }
    };
    load();
    return () => { cancelled = true; };
  }, [reload]);

  useEffect(() => {
    let cancelled = false;
    setAvailable(null); setError("");
    if (!scopeId) { setChecking(false); return; }
    setChecking(true);
    api.get("/api/quiz-attempts/mock-options/", { params: { scope_type: scope, scope_id: scopeId } })
      .then(res => { if (!cancelled) setAvailable({ ...res.data, scopeKey: `${scope}:${scopeId}` }); })
      .catch(() => { if (!cancelled) setError("Could not check the saved question bank. Please retry."); })
      .finally(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  }, [scope, scopeId, reload]);

  const count = available?.scopeKey === `${scope}:${scopeId}` ? available.available[difficulty] : undefined;
  const valid = Number.isInteger(mcq) && mcq >= 0 && mcq <= 100 &&
    Number.isInteger(theory) && theory >= 0 && theory <= 10 && mcq + theory > 0 &&
    (!timed || (Number.isInteger(minutes) && minutes >= 1 && minutes <= 180));
  const shortage = !!count && (mcq > count.mcq || theory > count.theory);
  const start = async () => {
    if (!valid || shortage || !count || checking || starting) return;
    setStarting(true); setError("");
    try {
      const response = await api.post("/api/quiz-attempts/", {
        exam_type: "mock", scope_type: scope, scope_id: scopeId, is_timed: timed,
        ...(timed ? { duration_minutes: minutes } : {}),
        configuration: { mcq_count: mcq, theory_count: theory, difficulty, question_source: "hierarchy" },
      });
      router.push(`/quiz/attempt/${response.data.id}`);
    } catch (e: any) {
      const detail = e.response?.data;
      setError(detail?.error || "The mock exam could not start. Please retry.");
      if (detail?.code === "insufficient_questions" && detail.available) {
        setAvailable(old => old && ({ ...old, available: { ...old.available, [difficulty]: {
          mcq: Number(detail.available.mcq), theory: Number(detail.available.theory),
        } } }));
      }
      setStarting(false);
    }
  };
  const selectClass = "block w-full rounded border bg-background p-2 mt-1";
  if (!isPremium) return <main className="mx-auto max-w-2xl p-6 space-y-4">
    <h1 className="text-2xl font-semibold">Mock exams</h1>
    <p>Mock exams are included with Premium. Single-deck practice and your class assessments remain available.</p>
    <Link href="/premium">View Premium</Link><br /><Link href="/quiz">Back to practice</Link>
  </main>;
  return <main className="mx-auto max-w-2xl p-6 space-y-5">
    <Link href="/quiz" className="text-sm underline">Back to practice</Link>
    <h1 className="text-2xl font-semibold">Create a mock exam</h1>
    <p>Choose saved questions from one course, module or submodule. Questions are spread across topics and source files at your chosen difficulty.</p>
    {(catalogError || error) && <p role="alert" className="text-destructive">{catalogError || error}</p>}
    <fieldset disabled={starting} className="space-y-4">
      <label className="block">Exam scope<select aria-label="Exam scope" className={selectClass} value={scope} onChange={e => setScope(e.target.value as Scope)}>
        <option value="course">Course</option><option value="module">Module</option><option value="submodule">Submodule</option>
      </select></label>
      <label className="block">Course<select aria-label="Course" className={selectClass} value={subject} onChange={e => { setSubject(e.target.value); setBlock(""); setSub(""); }}>
        <option value="">Choose course</option>{subjects.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select></label>
      {scope !== "course" && <label className="block">Module<select aria-label="Module" className={selectClass} value={block} onChange={e => { setBlock(e.target.value); setSub(""); }}>
        <option value="">Choose module</option>{blocks.filter(row => row.subject === subject).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select></label>}
      {scope === "submodule" && <label className="block">Submodule<select aria-label="Submodule" className={selectClass} value={sub} onChange={e => setSub(e.target.value)}>
        <option value="">Choose submodule</option>{subs.filter(row => row.block === block).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select></label>}
      <label className="block">Difficulty<select aria-label="Difficulty" className={selectClass} value={difficulty} onChange={e => setDifficulty(e.target.value)}>
        <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
      </select></label>
      <p role="status">{checking ? "Checking saved questions…" : count ? `${count.mcq} MCQs and ${count.theory} written questions available at ${difficulty} difficulty.` : "Choose a scope to see available questions."}</p>
      <div className="grid grid-cols-2 gap-4">
        <label>MCQs<input aria-label="MCQs" className={selectClass} type="number" min={0} max={100} value={mcq} onChange={e => setMcq(Number(e.target.value))} /></label>
        <label>Written questions<input aria-label="Written questions" className={selectClass} type="number" min={0} max={10} value={theory} onChange={e => setTheory(Number(e.target.value))} /></label>
      </div>
      {shortage && count && <div className="space-y-2"><p>There are fewer saved questions than requested. Choose a smaller exam or another scope.</p>
        <Button variant="outline" onClick={() => { setMcq(Math.min(mcq, count.mcq)); setTheory(Math.min(theory, count.theory)); }}>Use available questions</Button></div>}
      <label className="flex gap-2"><input type="checkbox" checked={timed} onChange={e => setTimed(e.target.checked)} />Timed exam</label>
      {timed && <label className="block">Minutes<input aria-label="Minutes" className={selectClass} type="number" min={1} max={180} value={minutes} onChange={e => setMinutes(Number(e.target.value))} /></label>}
      {!valid && <p>Choose at least one question, up to 100 MCQs and 10 written questions. Timed exams allow 1–180 whole minutes.</p>}
      <div className="flex gap-3">
        <Button onClick={start} disabled={!valid || shortage || !count || checking || !!catalogError}>Start mock exam</Button>
        <Button variant="outline" onClick={() => setReload(value => value + 1)}>Refresh availability</Button>
      </div>
    </fieldset>
  </main>;
}
