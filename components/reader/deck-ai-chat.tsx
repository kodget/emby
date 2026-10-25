"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Loader2, Send, Sparkles } from "lucide-react";
import { aiApi } from "@/lib/api";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export function DeckAiChat({ deckId, title, pageNumber }: { deckId: string; title: string; pageNumber: number }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [value, setValue] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  const loadHistory = async () => {
    setLoadingHistory(true);
    setError("");
    try {
      const result = await aiApi.getChatHistory({ deck_id: deckId });
      setMessages(result.messages.map((message, index) => ({
        id: `${message.created_at}-${index}`,
        role: message.role,
        content: message.content,
      })));
    } catch (err: any) {
      setError(err?.response?.data?.error || "Could not load this deck's chat history.");
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    void loadHistory();
  }, [deckId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, sending]);

  const send = async (event: FormEvent) => {
    event.preventDefault();
    const message = value.trim();
    if (!message || sending) return;

    setSending(true);
    setError("");
    try {
      const result = await aiApi.chatWithSlide({ deck_id: deckId, message, page_number: pageNumber });
      const timestamp = Date.now();
      setMessages(current => [
        ...current,
        { id: `user-${timestamp}`, role: "user", content: message },
        { id: `assistant-${timestamp}`, role: "assistant", content: result.response },
      ]);
      setValue("");
    } catch (err: any) {
      setError(err?.response?.data?.error || "The AI tutor could not answer. Please try again.");
    } finally {
      setSending(false);
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col border-l border-gray-700 bg-gray-800 text-white" aria-label="Ask AI about this document">
      <header className="border-b border-gray-700 px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles className="size-4 text-blue-400" />
          Ask Emby about this whole document
        </h2>
        <p className="mt-1 truncate text-xs text-gray-400">{title}</p>
      </header>

      <div ref={listRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
        {loadingHistory ? (
          <div role="status" className="flex items-center gap-2 text-sm text-gray-400">
            <Loader2 className="size-4 animate-spin" /> Loading conversation…
          </div>
        ) : messages.length === 0 ? (
          <p className="text-sm text-gray-300">
            Ask a question about any page. Emby uses the extracted text for this document and cites page numbers.
          </p>
        ) : messages.map(message => (
          <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <p className={`max-w-[90%] whitespace-pre-line rounded-2xl px-3 py-2 text-sm ${
              message.role === "user" ? "bg-blue-700" : "bg-gray-700"
            }`}>
              {message.content}
            </p>
          </div>
        ))}
        {sending && (
          <div role="status" className="flex items-center gap-2 text-sm text-gray-400">
            <Loader2 className="size-4 animate-spin" /> Emby is reading the document…
          </div>
        )}
      </div>

      {error && (
        <div className="border-t border-red-900 bg-red-950/70 p-3 text-sm text-red-100">
          <p role="alert">{error}</p>
          {!sending && !loadingHistory && messages.length === 0 && (
            <button type="button" className="mt-1 underline" onClick={() => void loadHistory()}>
              Retry loading chat
            </button>
          )}
        </div>
      )}

      <form onSubmit={send} className="flex gap-2 border-t border-gray-700 p-3">
        <input
          aria-label="Ask about this document"
          value={value}
          onChange={event => setValue(event.target.value)}
          disabled={sending || loadingHistory}
          placeholder="Ask about any page…"
          className="min-w-0 flex-1 rounded-full border border-gray-600 bg-gray-900 px-4 text-sm text-white outline-none focus:border-blue-500 disabled:opacity-60"
        />
        <button
          type="submit"
          aria-label="Send question"
          disabled={!value.trim() || sending || loadingHistory}
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50"
        >
          <Send className="size-4" />
        </button>
      </form>
      <p className="px-4 pb-3 text-[11px] text-gray-400">
        For educational purposes only; not a substitute for clinical judgment.
      </p>
    </section>
  );
}
