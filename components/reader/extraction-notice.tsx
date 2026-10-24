"use client";

import { useState } from "react";
import api from "@/lib/api";

export function ExtractionNotice({ slideId, summary, canReprocess }: {
  slideId: string;
  summary?: { status: string; missing_pages?: number[]; error_counts?: Record<string, number> };
  canReprocess?: boolean;
}) {
  const [state, setState] = useState<"idle" | "pending" | "queued" | "failed">("idle");
  if (summary?.status === "complete") return null;
  const missing = summary?.missing_pages ?? [];
  const errors = summary?.error_counts ?? {};
  async function retry() {
    setState("pending");
    try {
      await api.post(`/api/slides/${slideId}/reprocess/`);
      setState("queued");
    } catch {
      setState("failed");
    }
  }
  return <div role="status" aria-label="Document text status" className="border-b bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
    <p>{missing.length ? `Text could not be fully read on pages ${missing.join(", ")}.` : "Document text has not been fully checked yet."} You can keep reading the pages. Whole-document question generation needs complete text.</p>
    {errors.ocr_unavailable ? <p role="alert">The processing worker is missing OCR language data ({errors.ocr_unavailable} page{errors.ocr_unavailable === 1 ? "" : "s"}). Ask the class head to install or configure OCR language data before retrying.</p>
      : errors.ocr_failed ? <p role="alert">Text recognition failed on {errors.ocr_failed} page{errors.ocr_failed === 1 ? "" : "s"}. Ask the class head to check the worker&apos;s OCR installation before retrying.</p> : null}
    {state === "failed" && <p role="alert">Processing could not be queued. Please try again.</p>}
    {state === "queued" ? <p>Processing queued. <button className="underline" onClick={() => window.location.reload()}>Refresh extraction status</button></p>
      : canReprocess ? <button className="mt-1 underline disabled:opacity-60" disabled={state === "pending"} onClick={retry}>
        {state === "pending" ? "Queuing processing…" : "Retry text processing"}
      </button> : <p className="mt-1">Ask the uploader or class head to retry text processing.</p>}
  </div>;
}
