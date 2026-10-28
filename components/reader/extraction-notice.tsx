"use client";

import { useState } from "react";
import api from "@/lib/api";

export function ExtractionNotice({ slideId, summary, aiIndex, canReprocess, canPrepare, onDemandAI = false }: {
  slideId: string;
  summary?: { status: string; missing_pages?: number[]; error_counts?: Record<string, number> };
  canReprocess?: boolean;
  canPrepare?: boolean;
  onDemandAI?: boolean;
  aiIndex?: { status: string; error_code?: string };
}) {
  const [state, setState] = useState<"idle" | "pending" | "queued" | "failed">("idle");
  if (summary?.status === "complete") return null;
  const missing = summary?.missing_pages ?? [];
  const preparing = ['pending', 'running'].includes(aiIndex?.status ?? '');
  async function retry() {
    setState("pending");
    try {
      await api.post(`/api/slides/${slideId}/reprocess/`, { index_only: true });
      setState("queued");
    } catch {
      setState("failed");
    }
  }
  return <div role="status" aria-label="Document text status" className="border-b bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
    <p>{preparing
      ? "Ready to read. AI is preparing your study content in the background. You can already ask about the page on screen."
      : onDemandAI && !aiIndex?.error_code
      ? "Ready to read. Prepare AI tools when you need questions or study content from the whole document."
      : `${missing.length ? `AI could not fully read pages ${missing.join(', ')}.` : 'AI has not finished reading this document.'} You can keep reading. Retry AI preparation to enable study content from the whole document.`}</p>
    {state === "failed" && <p role="alert">Processing could not be queued. Please try again.</p>}
    {state === "queued" ? <p>Processing queued. <button className="underline" onClick={() => window.location.reload()}>Refresh extraction status</button></p>
      : !preparing && (canPrepare ?? canReprocess) ? <button className="mt-1 underline disabled:opacity-60" disabled={state === "pending"} onClick={retry}>
        {state === "pending" ? "Queuing processing…" : onDemandAI && !aiIndex?.error_code ? "Prepare AI tools" : "Retry AI preparation"}
      </button> : !preparing ? <p className="mt-1">Ask the uploader or class head to retry AI preparation.</p> : null}
  </div>;
}
