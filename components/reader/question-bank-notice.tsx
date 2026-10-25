"use client";

import { useEffect, useState } from "react";
import axios from "axios";
import api from "@/lib/api";
import Link from "next/link";

type Bank = {
  status: "not_requested" | "pending" | "running" | "completed" | "partial" | "failed";
  mcq_target: number;
  mcq_by_difficulty: Record<string, number>;
  theory_target: number;
  theory_by_difficulty: Record<string, number>;
  needs_review?: number;
  represented_pages?: number[];
  source_pages?: number;
  error?: string;
};

export function QuestionBankNotice({ slideId, canGenerate, textReady, deckId }: {
  slideId: string;
  deckId?: string;
  canGenerate: boolean;
  textReady: boolean;
}) {
  const statusUrl = deckId ? `/api/decks/${deckId}/question-bank/` : `/api/slides/${slideId}/status/`;
  const generateUrl = deckId ? statusUrl : `/api/slides/${slideId}/generate-questions/`;
  const [bank, setBank] = useState<Bank | null>(null);
  const [statusError, setStatusError] = useState("");
  const [generationError, setGenerationError] = useState("");
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const { data } = await api.get(statusUrl, { signal: controller.signal });
        if (controller.signal.aborted) return;
        if (!data.question_bank) throw new Error("Missing bank status");
        setBank(data.question_bank);
        setStatusError("");
        if (["pending", "running"].includes(data.question_bank.status)) timer = setTimeout(load, 5000);
      } catch (error) {
        if (controller.signal.aborted) return;
        const detail = axios.isAxiosError(error)
          ? error.response ? `HTTP ${error.response.status}` : error.message
          : "Unexpected status response";
        setStatusError(detail);
        timer = setTimeout(load, 5000);
      }
    }
    void load();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [statusUrl, revision, textReady]);

  async function generate() {
    const session = sessionStorage.getItem("user");
    setBusy(true);
    setGenerationError("");
    try {
      await api.post(generateUrl, { force: true });
      if (session === sessionStorage.getItem("user")) setRevision(value => value + 1);
    } catch (error) {
      if (session === sessionStorage.getItem("user")) {
        const detail = axios.isAxiosError(error)
          ? error.response ? `HTTP ${error.response.status}` : error.message
          : "Unexpected request error";
        setGenerationError(detail);
      }
    } finally { setBusy(false); }
  }

  const pending = bank && ["pending", "running"].includes(bank.status);
  return <div role="status" aria-label="Saved question bank" className="border-b bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
    {!bank ? <p>{statusError ? `Question-bank status is unavailable (${statusError}).` : "Checking saved questions…"}</p> : <>
      <p>Saved MCQs: {bank.mcq_by_difficulty.easy ?? 0} easy, {bank.mcq_by_difficulty.medium ?? 0} medium, {bank.mcq_by_difficulty.hard ?? 0} hard. Target: {bank.mcq_target} (5 each).</p>
      <p>Theory questions: {Object.values(bank.theory_by_difficulty).reduce((sum, count) => sum + count, 0)}/{bank.theory_target}.
        {pending ? " Questions are being prepared; you can keep reading." : bank.status === "completed" ? " Bank ready." : " Bank is not complete yet."}</p>
      {!!bank.needs_review && <p>{bank.needs_review} question(s) awaiting review are excluded from practice.</p>}
      {!!bank.source_pages && <p>Saved questions cite {bank.represented_pages?.length ?? 0} of {bank.source_pages} source pages. This does not mean every topic has been assessed.</p>}
      {bank.error && <p>{bank.error}</p>}
      {Object.values(bank.mcq_by_difficulty).some(count => count > 0) && <Link className="inline-block mt-2 underline" href={`/quiz?slide=${encodeURIComponent(slideId)}`}>Practise this deck</Link>}
    </>}
    {statusError && <p role="alert">Could not refresh question-bank status ({statusError}). Retrying automatically.
      <button className="ml-1 underline" onClick={() => setRevision(value => value + 1)}>Refresh now</button></p>}
    {generationError && <p role="alert">Could not queue question generation ({generationError}).</p>}
    {bank && !pending && bank.status !== "completed" && (canGenerate && textReady
      ? <button disabled={busy} className="mt-1 underline disabled:opacity-60" onClick={generate}>{busy ? "Queuing questions…" : bank.status === "not_requested" ? "Prepare saved questions" : "Retry question generation"}</button>
      : <p>{!textReady && "AI is still preparing the document. "}The uploader or class head can prepare or retry these questions.</p>)}
  </div>;
}
