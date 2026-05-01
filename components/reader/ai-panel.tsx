"use client"

import { useEffect, useRef, useState } from "react"
import { BookOpenText, Play, Send, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

export type YoutubeSuggestion = {
  title: string
  channel: string
  length: string
  isDissection?: boolean
  url?: string
}

export type Message = {
  id: string
  role: "user" | "ai"
  content: string
  sources?: string[]
  youtube?: YoutubeSuggestion
}

export function AiPanel({
  messages,
  onAsk,
  quickActions,
}: {
  messages: Message[]
  onAsk: (text: string) => void
  quickActions: { label: string; prompt: string }[]
}) {
  const [value, setValue] = useState("")
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" })
  }, [messages.length])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!value.trim()) return
    onAsk(value.trim())
    setValue("")
  }

  return (
    <div className="flex h-full flex-col">
      <div ref={listRef} className="flex-1 min-h-0 space-y-3 overflow-y-auto px-4 py-4">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
      </div>

      <div className="border-t border-border p-3">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {quickActions.map((a) => (
            <button
              key={a.label}
              onClick={() => onAsk(a.prompt)}
              className="rounded-full border border-border bg-background px-2.5 py-1 text-[11px] text-muted-foreground hover:border-primary hover:text-foreground"
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
            placeholder="Ask anything about this page…"
            className="h-11 w-full rounded-full border border-border bg-background pl-4 pr-11 text-sm outline-none focus:border-primary"
            aria-label="Ask the Emby tutor"
          />
          <button
            type="submit"
            aria-label="Send"
            className="absolute right-1 top-1 flex size-9 items-center justify-center rounded-full bg-primary text-primary-foreground hover:opacity-90"
          >
            <Send className="size-4" aria-hidden="true" />
          </button>
        </form>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user"
  return (
    <div className={cn("flex gap-2", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Sparkles className="size-3.5" aria-hidden="true" />
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

        {message.youtube && <YoutubeCard video={message.youtube} />}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 border-t border-border pt-2">
            {message.sources.map((s) => (
              <span
                key={s}
                className="inline-flex items-center gap-1 rounded-full bg-background px-2 py-0.5 text-[10.5px] text-muted-foreground"
              >
                <BookOpenText className="size-3" aria-hidden="true" />
                {s}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function YoutubeCard({ video }: { video: YoutubeSuggestion }) {
  const label = video.isDissection ? "Dissection video" : "Recommended video"
  return (
    <a
      href={video.url ?? "#"}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-2.5 flex gap-2.5 rounded-xl border border-border bg-background/70 p-2 transition-colors hover:border-primary/40"
    >
      <div className="relative flex size-14 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        <Play className="size-4" aria-hidden="true" />
        <span className="absolute bottom-0.5 right-0.5 rounded bg-foreground/80 px-1 text-[9px] font-medium text-background">
          {video.length}
        </span>
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
        <p className="mt-0.5 line-clamp-2 text-[12.5px] font-medium leading-tight text-foreground">{video.title}</p>
        <p className="mt-0.5 text-[10.5px] text-muted-foreground">{video.channel}</p>
      </div>
    </a>
  )
}
