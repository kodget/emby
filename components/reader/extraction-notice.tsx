"use client";

import { useEffect, useState } from "react";
import axios from "axios";
import api from "@/lib/api";

export function ExtractionNotice({ slideId, summary, aiIndex, canReprocess, canPrepare, onDemandAI = false, onContentUpdate }: {
  slideId: string;
  summary?: { status: string; missing_pages?: number[]; error_counts?: Record<string, number> };
  canReprocess?: boolean;
  canPrepare?: boolean;
  onDemandAI?: boolean;
  aiIndex?: { status: string; error_code?: string; next_attempt_at?: string | null };
  onContentUpdate?: (content: any) => void;
}) {
  const [state, setState] = useState<"idle" | "pending" | "queued" | "failed">("idle");
  const [error, setError] = useState("");
  const missing = summary?.missing_pages ?? [];
  const preparing = ['pending', 'running'].includes(aiIndex?.status ?? '');
  const complete = summary?.status === "complete";
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
  if (complete) return null;
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
  return <div role="status" aria-label="Document text status" className="border-b bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
    <p>{aiIndex?.error_code === "provider_rate_limited"
      ? `Your pages are ready to read. AI preparation is waiting for provider capacity${aiIndex.next_attempt_at ? `; the next attempt is scheduled for ${new Date(aiIndex.next_attempt_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ''}. It will resume automatically. Refreshing will not speed up this wait.`
      : preparing
      ? "Ready to read. AI is preparing your study content in the background. You can already ask about the page on screen."
      : onDemandAI && !aiIndex?.error_code
      ? "Ready to read. Prepare AI tools when you need questions or study content from the whole document."
      : `${missing.length ? `AI could not fully read pages ${missing.join(', ')}.` : 'AI has not finished reading this document.'} You can keep reading. Retry AI preparation to enable study content from the whole document.`}</p>
    {error && <p role="alert" className="mt-2">{error}</p>}
    {state === "queued" ? <p>Request saved. Processing queued; progress updates automatically while you read. <button className="min-h-11 underline" onClick={refresh}>Refresh extraction status</button></p>
      : !preparing && (canPrepare ?? canReprocess) ? <button className="mt-1 underline disabled:opacity-60" disabled={state === "pending"} onClick={retry}>
        {state === "pending" ? "Queuing processing…" : onDemandAI && !aiIndex?.error_code ? "Prepare AI tools" : "Retry AI preparation"}
      </button> : !preparing ? <p className="mt-1">Ask the uploader or class head to retry AI preparation.</p> : null}
  </div>;
}
