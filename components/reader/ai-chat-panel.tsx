"use client";

/**
 * AiChatPanel
 *
 * Renders the AI chat for the CURRENT slide only.
 * History is keyed by slideIndex from the global store — switching slides
 * loads that slide's conversation, not a shared one.
 */

import { useEffect, useRef, useState } from "react";
import { BookOpenText, Loader2, Play, Send, Sparkles } from "lucide-react";
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
  const { getChatHistory } = useSlideStore();

  // Load messages for THIS slide
  const messages = getChatHistory(slideIndex);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
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
      label: "Summarise this slide",
      prompt: "Summarise this slide in 5 bullet points.",
    },
    {
      label: "Generate 3 MCQs",
      prompt: "Generate 3 MCQs with answers from this slide.",
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
      {/* ── Message list ────────────────────────────────────────────── */}
      <div
        ref={listRef}
        className="flex-1 min-h-0 space-y-3 overflow-y-auto px-4 py-4"
      >
        {displayMessages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}

        {isLoading && (
          <div className="flex gap-2 justify-start">
            <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Sparkles className="size-3.5" />
            </span>
            <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-muted px-3.5 py-2.5">
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            </div>
          </div>
        )}
      </div>

      {/* ── Quick actions + input ────────────────────────────────────── */}
      <div className="border-t border-border p-3">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {quickActions.map((a) => (
            <button
              key={a.label}
              onClick={() => onSend(a.prompt)}
              disabled={isLoading}
              className="rounded-full border border-border bg-background px-2.5 py-1 text-[11px] text-muted-foreground hover:border-primary hover:text-foreground disabled:opacity-50"
            >
              {a.label}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="relative">
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Ask about this slide…"
            disabled={isLoading}
            className="h-11 w-full rounded-full border border-border bg-background pl-4 pr-11 text-sm outline-none focus:border-primary disabled:opacity-60"
            aria-label="Ask the Emby tutor"
          />
          <button
            type="submit"
            disabled={!value.trim() || isLoading}
            aria-label="Send"
            className="absolute right-1 top-1 flex size-9 items-center justify-center rounded-full bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            <Send className="size-4" />
          </button>
        </form>
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
