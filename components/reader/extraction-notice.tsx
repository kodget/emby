"use client";

import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { BookOpenCheck, Check, Clock3, ScanText } from "lucide-react";
import api from "@/lib/api";

export function ExtractionNotice({ slideId, summary, aiIndex, canReprocess, canPrepare, onContentUpdate }: {
  slideId: string;
  summary?: { status: string; total_pages?: number; processed_pages?: number; missing_pages?: number[]; error_counts?: Record<string, number> };
  canReprocess?: boolean;
  canPrepare?: boolean;
  onDemandAI?: boolean;
  aiIndex?: { status: string; error_code?: string; next_attempt_at?: string | null };
  onContentUpdate?: (content: any) => void;
}) {
  const [state, setState] = useState<"idle" | "pending" | "queued" | "failed">("idle");
  const [error, setError] = useState("");
  const autoRequested = useRef<string | null>(null);
  const missing = summary?.missing_pages ?? [];
  const preparing = ['pending', 'running'].includes(aiIndex?.status ?? '');
  const complete = summary?.status === "complete";
  const waiting = aiIndex?.error_code === "provider_rate_limited";
  const total = summary?.total_pages;
  const processed = summary?.processed_pages ?? (total ? total - missing.length : 0);
  useEffect(() => {
    // Compatibility with an older API during a rolling deployment. New APIs
    // already queue indexing when content is opened, so no extra POST is sent.
    if (complete || preparing || !(canPrepare ?? canReprocess) ||
        (aiIndex?.status && aiIndex.status !== "unverified") || autoRequested.current === slideId) return;
    autoRequested.current = slideId;
    void retry();
  }, [slideId, complete, preparing, canPrepare, canReprocess, aiIndex?.status]);
  useEffect(() => {
    if (complete || (state !== "queued" && !preparing)) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const { data } = await api.get(`/api/slides/${slideId}/content/`);
        if (stopped) return;
        onContentUpdate?.(data);
        setError("");
        if (data.text_extraction?.status === "complete") return;
        if (data.ai_index?.status === "failed" && !data.ai_index?.next_attempt_at) {
          setState("idle");
          return;
        }
      } catch {
        if (!stopped) setError("Could not refresh progress. Your document is still open; checking again automatically.");
      }
      if (!stopped) timer = setTimeout(poll, 5000);
    }
    timer = setTimeout(poll, 5000);
    return () => { stopped = true; clearTimeout(timer); };
  }, [slideId, complete, preparing, state, onContentUpdate]);
  if (complete) return <div role="status" aria-label="Study tools ready" className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-emerald-200/60 bg-emerald-50/70 px-4 py-2 text-xs text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-100">
    <span className="inline-flex items-center gap-1.5 font-semibold"><BookOpenCheck className="size-4" /> Ready for your study session</span>
    <span>{total ? `${total} pages indexed · ` : ""}Ask a question, make flashcards, or explore resources.</span>
  </div>;
  async function refresh() {
    try {
      const { data } = await api.get(`/api/slides/${slideId}/content/`);
      onContentUpdate ? onContentUpdate(data) : window.location.reload();
    } catch { setError("Could not reach the server to refresh progress. Please try again."); }
  }
  async function retry() {
    setState("pending");
    setError("");
    try {
      await api.post(`/api/slides/${slideId}/reprocess/`, { index_only: true });
      setState("queued");
    } catch (failure) {
      const status = axios.isAxiosError(failure) ? failure.response?.status : undefined;
      setError(status === 401 ? "Your session has expired. Sign in again to prepare AI tools."
        : status === 403 ? "Your account does not have permission to prepare this document."
        : status ? `The server could not queue AI preparation (HTTP ${status}). Please retry.`
        : "Could not reach the server. Check your connection and retry; no processing was confirmed.");
      setState("failed");
    }
  }
  return <div role="status" aria-label="Document text status" className="border-b border-border bg-background px-4 py-4 text-sm">
    <div className="flex items-start gap-3">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">{waiting ? <Clock3 className="size-5" /> : <ScanText className="size-5" />}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-semibold tracking-tight">{waiting ? "Your progress is saved" : preparing || state === "pending" || state === "queued" ? "Read now. We’re preparing your study tools." : "Let’s finish preparing this document"}</p>
          {total ? <span className="rounded-full bg-muted px-2.5 py-1 text-xs tabular-nums">{processed} / {total} pages indexed</span> : null}
        </div>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{waiting
      ? `The remaining image pages need the AI provider${aiIndex?.next_attempt_at ? `; the next attempt is scheduled for ${new Date(aiIndex.next_attempt_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ''}. It will resume automatically. You can keep reading.`
      : preparing
      ? "Text recognition and indexing started when you opened this slide. Progress saves page by page while you read."
      : state === "pending" || state === "queued"
      ? "Starting text recognition and indexing automatically. Your document stays open while we prepare it."
      : `${missing.length ? `AI could not fully read pages ${missing.join(', ')}.` : 'AI has not finished reading this document.'} You can keep reading. Retry AI preparation to enable study content from the whole document.`}</p>
        {total ? <div role="progressbar" aria-label="Pages indexed" aria-valuenow={processed} aria-valuemin={0} aria-valuemax={total} className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, processed / total * 100)}%` }} /></div> : null}
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground"><span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-300"><Check className="size-3" /> Read slides</span><span>Recognise text</span><span>Prepare study tools</span></div>
      </div>
    </div>
    {error && <p role="alert" className="mt-2">{error}</p>}
    {state === "queued" ? <p>Request saved. Processing queued; progress updates automatically while you read. <button className="min-h-11 underline" onClick={refresh}>Refresh extraction status</button></p>
      : !preparing && (canPrepare ?? canReprocess) ? <button className="mt-1 underline disabled:opacity-60" disabled={state === "pending"} onClick={retry}>
        {state === "pending" ? "Queuing processing…" : "Retry AI preparation"}
      </button> : !preparing ? <p className="mt-1">Ask the uploader or class head to retry AI preparation.</p> : null}
  </div>;
}
