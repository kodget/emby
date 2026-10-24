"use client";

import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { QuestionBankNotice } from "./question-bank-notice";

type Choice = { id: string; name: string; subject?: string };
type Link = { slide_id: string | null; can_generate: boolean; needs_assignment: boolean };
const rows = (data: Choice[] | { results: Choice[] }): Choice[] => Array.isArray(data) ? data : data.results;

export function DeckQuestionBank({ deckId }: { deckId: string }) {
  const [link, setLink] = useState<Link | null>(null);
  const [subjects, setSubjects] = useState<Choice[]>([]);
  const [blocks, setBlocks] = useState<Choice[]>([]);
  const [subject, setSubject] = useState("");
  const [block, setBlock] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const version = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const current = ++version.current;
    const session = sessionStorage.getItem("user");
    setLink(null); setSubjects([]); setBlocks([]); setError(""); setSubject(""); setBlock("");
    async function load() {
      try {
        const { data } = await api.get(`/api/decks/${deckId}/question-bank/`, { signal: controller.signal });
        if (controller.signal.aborted || session !== sessionStorage.getItem("user")) return;
        if (typeof data.can_generate !== "boolean") throw new Error("Invalid status");
        setLink(data);
        if (data.needs_assignment && data.can_generate) {
          const [courses, modules] = await Promise.all([
            api.get("/api/subjects/", { signal: controller.signal }),
            api.get("/api/blocks/", { signal: controller.signal }),
          ]);
          if (current !== version.current || session !== sessionStorage.getItem("user")) return;
          setSubjects(rows(courses.data)); setBlocks(rows(modules.data));
        }
      } catch {
        if (!controller.signal.aborted) setError("Could not load question-bank setup. You can keep reading.");
      }
    }
    void load();
    return () => { version.current++; controller.abort(); };
  }, [deckId, attempt]);

  async function prepare() {
    const current = version.current;
    const session = sessionStorage.getItem("user");
    setBusy(true); setError("");
    try {
      const { data } = await api.post(`/api/decks/${deckId}/question-bank/`, { subject, block });
      if (current === version.current && session === sessionStorage.getItem("user")) setLink(data);
    } catch {
      if (current === version.current) setError("Could not prepare questions. Check the selected course and module, then retry.");
    } finally { if (current === version.current) setBusy(false); }
  }

  if (link?.slide_id) return <QuestionBankNotice key={link.slide_id} slideId={link.slide_id} deckId={deckId} canGenerate={link.can_generate} textReady />;
  return <div aria-label="Standalone question setup" className="border-b bg-background p-3 text-sm text-foreground">
    <p>Prepare a saved bank of 15 MCQs: 5 easy, 5 medium and 5 hard.</p>
    {error && <p role="alert">{error} <button className="underline" onClick={() => setAttempt(n => n + 1)}>Reload question setup</button></p>}
    {!link && !error && <p>Loading question-bank setup…</p>}
    {link?.needs_assignment && (link.can_generate ? <form className="mt-2 flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); void prepare(); }}>
      <label>Course <select required value={subject} onChange={event => { setSubject(event.target.value); setBlock(""); }} className="rounded border bg-background p-1">
        <option value="">Select course</option>{subjects.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select></label>
      <label>Module <select required disabled={!subject} value={block} onChange={event => setBlock(event.target.value)} className="rounded border bg-background p-1">
        <option value="">Select module</option>{blocks.filter(row => row.subject === subject).map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select></label>
      <button disabled={busy || !subject || !block} className="underline disabled:opacity-50">{busy ? "Preparing…" : "Prepare saved questions"}</button>
      {!error && subjects.length === 0 && <p>A class head must create a course and module before this document can be assigned.</p>}
    </form> : <p>Ask the uploader or class head to assign this document to a course and prepare its questions.</p>)}
  </div>;
}
