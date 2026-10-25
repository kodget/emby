"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Send } from "lucide-react";

type Source = { citation: number; title: string; page: number | null };
type Message = { role: "user" | "assistant"; content: string; sources?: Source[] };

export function LibraryTutor({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    api.get("/api/ai/chat/history/", { params: { scope: "library" } }).then(({ data }) => {
      if (!cancelled) { setMessages(data.messages); setError(""); }
    }).catch(() => { if (!cancelled) setError("Could not load your conversation. Close and reopen to retry."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open]);
  useEffect(() => { list.current?.scrollTo({ top: list.current.scrollHeight }); }, [messages, busy]);
  async function send(event: FormEvent) {
    event.preventDefault();
    const message = value.trim();
    if (!message || busy || loading) return;
    setBusy(true); setError("");
    try {
      const { data } = await api.post("/api/ai/chat/", { scope: "library", message }, { timeout: 120000 });
      setMessages(current => [...current, { role: "user", content: message },
        { role: "assistant", content: data.response, sources: data.sources }]);
      setValue("");
      window.dispatchEvent(new Event("credits-updated"));
    } catch (err: any) {
      setError(err?.response?.data?.error || "The tutor could not answer. Please try again.");
    } finally { setBusy(false); }
  }
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="flex h-[min(85dvh,720px)] flex-col sm:max-w-2xl">
      <DialogHeader><DialogTitle>Ask AI tutor</DialogTitle><DialogDescription>Ask about your class’s uploaded slides. Answers use relevant excerpts and your available AI credits.</DialogDescription></DialogHeader>
      <div ref={list} className="min-h-0 flex-1 space-y-4 overflow-y-auto" aria-live="polite">
        {loading ? <p role="status">Loading conversation…</p> : messages.length === 0 ? <p className="text-sm text-muted-foreground">Try “Explain the brachial plexus from our slides.” Newly uploaded slides become available after processing.</p> : messages.map((message, index) => <div key={index} className={`rounded-xl p-3 text-sm ${message.role === "user" ? "ml-8 bg-primary/10" : "mr-4 bg-muted"}`}>
          <p className="mb-1 font-semibold">{message.role === "user" ? "You" : "Emby"}</p><p className="whitespace-pre-wrap">{message.content}</p>
          {message.sources?.length ? <details className="mt-3"><summary className="cursor-pointer">Slide sources</summary><ul className="mt-2 space-y-1">{message.sources.map(source => <li key={source.citation}>[{source.citation}] {source.title}{source.page ? ` · Page ${source.page}` : ""}</li>)}</ul></details> : null}
        </div>)}
        {busy && <p role="status" className="flex items-center gap-2 text-sm"><Loader2 className="size-4 animate-spin" />Reading your slides…</p>}
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <form onSubmit={send} className="flex gap-2"><Input aria-label="Question for AI tutor" value={value} onChange={e => setValue(e.target.value)} maxLength={6000} placeholder="Ask about your slides…" disabled={busy || loading} /><Button type="submit" disabled={busy || loading || !value.trim()} aria-label="Send question"><Send className="size-4" /></Button></form>
      <p className="text-xs text-muted-foreground">For learning purposes; verify important details against your slides.</p>
    </DialogContent>
  </Dialog>;
}
