"use client";

/**
 * AiChatPanel
 *
 * Renders the AI chat for the CURRENT slide only.
 * History is keyed by slideIndex from the global store — switching slides
 * loads that slide's conversation, not a shared one.
 */

import { useEffect, useRef, useState } from "react";
import { BookOpenText, Brain, Lightbulb, Loader2, Play, Send, Sparkles, Stethoscope } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSlideStore, type ChatMessage } from "@/store/slide-store";

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export function AiChatPanel({
  slideIndex,
  isLoading,
  onSend,
}: {
  slideIndex: number;
  isLoading: boolean;
  onSend: (message: string) => void;
}) {
  const [value, setValue] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const { getChatHistory, slides } = useSlideStore();
  const currentSlide = slides[slideIndex];

  // Load messages for THIS slide
  const messages = getChatHistory(slideIndex);
  const failedQuestion = messages.at(-1)?.id.startsWith("err-")
    ? [...messages].reverse().find(message => message.role === "user")?.content
    : undefined;

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? "instant" : "smooth",
    });
  }, [messages.length]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim() || isLoading) return;
    onSend(value.trim());
    setValue("");
  };

  const quickActions = [
    {
      label: "Summarise",
      prompt: "Summarise this slide in 5 bullet points.",
    },
    {
      label: "Explain simply",
      prompt:
        "Explain this slide in very simple terms for a first-year medical student.",
    },
    {
      label: "Clinical relevance",
      prompt: "What is the clinical relevance of this slide's content?",
    },
    {
      label: "Test me",
      prompt: "Test my understanding of this slide by asking me a challenging question.",
    },
    {
      label: "Mnemonic",
      prompt: "Give me a mnemonic to remember the key facts on this slide.",
    }
  ];

  // Show a welcome message if no history yet
  const displayMessages: ChatMessage[] =
    messages.length === 0
      ? [
          {
            id: "welcome",
            role: "ai",
            content:
              "Hi! I'm reading along with you. Ask me anything about this slide, highlight text to get an explanation, or use one of the quick actions below.",
          },
        ]
      : messages;

  return (
    <div className="flex h-full flex-col">
      {/* Contextual Header */}
      {currentSlide && (
        <div className="border-b border-border bg-background px-4 py-3 flex items-center justify-between text-xs text-muted-foreground shrink-0">
          <span className="flex items-center gap-1.5 truncate">
            <BookOpenText className="size-4 shrink-0 text-primary" />
            Page {slideIndex + 1} <span aria-hidden="true">/</span> <strong className="text-foreground truncate font-medium">{currentSlide.title}</strong>
          </span>
        </div>
      )}

      {/* ── Message list ────────────────────────────────────────────── */}
      <div
        ref={listRef}
        className="flex-1 min-h-0 space-y-3 overflow-y-auto px-4 py-4"
      >
        {messages.length === 0 ? <div className="py-3">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 text-[11px] font-medium text-primary"><Sparkles className="size-3" /> Your reading companion</span>
          <h3 className="mt-4 max-w-64 font-serif text-3xl leading-tight tracking-tight">Make this page<br />make sense.</h3>
          <p className="mt-3 max-w-72 text-sm leading-relaxed text-muted-foreground">Start with what feels unclear. Your tutor uses this document to explain, connect, and help you recall.</p>
          <div className="mt-5 grid grid-cols-2 gap-2">
            {[
              { icon: Lightbulb, title: "Explain simply", detail: "Break it into small steps", prompt: quickActions[1].prompt },
              { icon: Brain, title: "Test me", detail: "One question at a time", prompt: quickActions[3].prompt },
              { icon: BookOpenText, title: "Summarise", detail: "Find the key ideas", prompt: quickActions[0].prompt },
              { icon: Stethoscope, title: "Clinical relevance", detail: "Make useful connections", prompt: quickActions[2].prompt },
            ].map(action => <button key={action.title} type="button" aria-label={action.title} disabled={isLoading} onClick={() => onSend(action.prompt)} className="group rounded-2xl border border-border bg-background p-3 text-left transition-colors hover:border-primary/40 hover:bg-primary/5 focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-50">
              <action.icon className="mb-3 size-5 text-primary" /><span className="block text-xs font-semibold">{action.title}</span><span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground">{action.detail}</span>
            </button>)}
          </div>
        </div> : displayMessages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}

        {isLoading && (
          <div role="status" aria-label="Tutor is responding" className="flex gap-2 justify-start">
            <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Sparkles className="size-3.5" />
            </span>
            <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-muted px-3.5 py-2.5">
              <span className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="size-4 motion-safe:animate-spin" /> Working on your question…</span>
            </div>
          </div>
        )}
      </div>

      {/* ── Quick actions + input ────────────────────────────────────── */}
      {failedQuestion && !isLoading && <div className="border-t border-border bg-muted/30 px-3 py-2">
        <p className="text-xs text-muted-foreground">Your question is still here.</p>
        <button type="button" onClick={() => onSend(failedQuestion)} className="min-h-11 text-sm font-medium text-primary underline underline-offset-4">Retry this question</button>
      </div>}
      <div className="border-t border-border p-3">
        {messages.length > 0 && <div className="mb-2 flex flex-wrap gap-1.5">
          {quickActions.map((a) => (
            <button
              key={a.label}
              onClick={() => onSend(a.prompt)}
              disabled={isLoading}
              className="min-h-11 rounded-full border border-border bg-background px-3 py-2 text-xs text-muted-foreground hover:border-primary hover:text-foreground focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-50"
            >
              {a.label}
            </button>
          ))}
        </div>}

        <form onSubmit={submit} className="relative">
          <textarea
            rows={2}
            maxLength={4000}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(e); } }}
            placeholder="Ask about this slide…"
            disabled={isLoading}
            className="min-h-24 w-full resize-none rounded-2xl border border-border bg-background p-3 pr-14 text-sm leading-relaxed outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 disabled:opacity-60"
            aria-label="Ask the Emby tutor"
          />
          <button
            type="submit"
            disabled={!value.trim() || isLoading}
            aria-label="Send"
            className="absolute bottom-3 right-2 flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-50"
          >
            <Send className="size-4" />
          </button>
        </form>
        <p className="mt-1 text-center text-[10px] text-muted-foreground">Enter to send · Shift + Enter for a new line</p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Message bubble
// ─────────────────────────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-2", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Sparkles className="size-3.5" />
        </span>
      )}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed",
          isUser
            ? "rounded-br-md bg-primary text-primary-foreground"
            : "rounded-bl-md bg-muted text-foreground",
        )}
      >
        <p className="whitespace-pre-line">{message.content}</p>

        {message.youtube && <YouTubeCard video={message.youtube} />}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 border-t border-border pt-2">
            {message.sources.map((s) => (
              <span
                key={s}
                className="inline-flex items-center gap-1 rounded-full bg-background px-2 py-0.5 text-[10.5px] text-muted-foreground"
              >
                <BookOpenText className="size-3" />
                {s}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function YouTubeCard({
  video,
}: {
  video: NonNullable<ChatMessage["youtube"]>;
}) {
  const searchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(video.query)}`;
  const label = video.isDissection ? "Dissection video" : "Recommended video";

  return (
    <a
      href={searchUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-2.5 flex gap-2.5 rounded-xl border border-border bg-background/70 p-2 transition-colors hover:border-primary/40"
    >
      <div className="relative flex size-14 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        <Play className="size-4" />
      </div>
      <div className="min-w-0">
        <p
          className={cn(
            "text-[10px] font-medium uppercase tracking-widest",
            video.isDissection ? "text-accent" : "text-primary",
          )}
        >
          {label}
        </p>
        <p className="mt-0.5 line-clamp-2 text-[12.5px] font-medium leading-tight text-foreground">
          {video.title}
        </p>
        {video.channel && (
          <p className="mt-0.5 text-[10.5px] text-muted-foreground">
            {video.channel}
          </p>
        )}
      </div>
    </a>
  );
}
