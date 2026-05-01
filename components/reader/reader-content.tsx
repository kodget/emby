"use client"

import { useEffect, useRef } from "react"
import { AlertTriangle, Highlighter, Sparkles } from "lucide-react"
import type { ReaderBlock } from "@/lib/data"
import { SelectableImagePage } from "./selectable-image-page"

export type SelectionPayload = {
  text: string
  rect: DOMRect | null
}

export function ReaderContent({
  blocks,
  slideContent,
  onSelect,
  onExplain,
  fallbackTitle,
  slidePages,
}: {
  blocks: ReaderBlock[]
  slideContent?: any
  onSelect: (s: SelectionPayload | null) => void
  onExplain: (text: string) => void
  fallbackTitle: string
  slidePages?: string[] | null
}) {
  const articleRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = articleRef.current
    if (!el) return
    function handleMouseUp() {
      const sel = window.getSelection()
      const text = sel?.toString().trim() ?? ""
      if (!text || text.length < 4) { onSelect(null); return }
      if (!sel || sel.rangeCount === 0) return
      const range = sel.getRangeAt(0)
      if (!el!.contains(range.commonAncestorContainer)) return
      onSelect({ text, rect: range.getBoundingClientRect() })
    }
    document.addEventListener("mouseup", handleMouseUp)
    document.addEventListener("touchend", handleMouseUp)
    return () => {
      document.removeEventListener("mouseup", handleMouseUp)
      document.removeEventListener("touchend", handleMouseUp)
    }
  }, [onSelect])

  // If slideContent from API is available with rendered pages, use selectable image pages
  if (slideContent && slideContent.pages && slideContent.pages.length > 0) {
    const hasImageUrls = slideContent.pages.some((p: any) => p.image_url)
    
    if (hasImageUrls) {
      // New format: rendered images with text coordinates
      return (
        <article ref={articleRef} aria-label="Study material">
          <HintBar />
          <div className="space-y-4">
            {slideContent.pages.map((page: any, i: number) => (
              <SelectableImagePage key={i} page={page} />
            ))}
          </div>
        </article>
      )
    } else {
      // Old format: extracted text and images
      return (
        <article ref={articleRef} aria-label="Study material">
          <HintBar />
          <div className="space-y-8">
            {slideContent.pages.map((page: any, i: number) => (
              <ExtractedPageBlock key={i} page={page} />
            ))}
          </div>
        </article>
      )
    }
  }

  // If slide pages were uploaded, render them as the primary content
  if (slidePages && slidePages.length > 0) {
    return (
      <article ref={articleRef} aria-label="Study material">
        <HintBar />
        <div className="space-y-4">
          {slidePages.map((src, i) => (
            <SlideBlock key={i} src={src} pageNumber={i + 1} total={slidePages.length} />
          ))}
        </div>
      </article>
    )
  }

  if (!blocks.length) {
    return <FallbackContent title={fallbackTitle} onExplain={onExplain} articleRef={articleRef} />
  }

  return (
    <article ref={articleRef} className="prose-reader" aria-label="Study material">
      <HintBar />
      {blocks.map((b, i) => (
        <Block key={i} block={b} />
      ))}
    </article>
  )
}

function HintBar() {
  return (
    <div className="mb-8 flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-2 text-[12px] text-primary">
      <Highlighter className="size-3.5" aria-hidden="true" />
      <span>Highlight any text or right-click a slide to ask the AI tutor.</span>
    </div>
  )
}

function SlideBlock({ src, pageNumber, total }: { src: string; pageNumber: number; total: number }) {
  return (
    <figure className="overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={`Slide ${pageNumber}`}
        className="w-full"
        loading={pageNumber <= 3 ? "eager" : "lazy"}
      />
      <figcaption className="flex items-center justify-between border-t border-border px-4 py-2.5 text-[11px] text-muted-foreground">
        <span>Slide {pageNumber}</span>
        <span>{pageNumber} / {total}</span>
      </figcaption>
    </figure>
  )
}

function ExtractedPageBlock({ page }: { page: any }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
        <span className="text-sm font-medium text-muted-foreground">
          Page {page.page_number}
        </span>
      </div>
      
      {page.content && (
        <div className="prose prose-sm max-w-none">
          <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-foreground/90">
            {page.content}
          </p>
        </div>
      )}
      
      {page.images && page.images.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium text-muted-foreground">
            {page.images.length} image{page.images.length > 1 ? 's' : ''} on this page
          </p>
        </div>
      )}
    </div>
  )
}

function Block({ block }: { block: ReaderBlock }) {
  switch (block.type) {
    case "h1":
      return (
        <h1 className="mb-4 font-serif text-4xl leading-tight tracking-tight text-balance md:text-5xl">
          {block.text}
        </h1>
      )
    case "h2":
      return <h2 className="mt-10 mb-3 font-serif text-2xl leading-tight">{block.text}</h2>
    case "p":
      return <p className="mb-4 text-[15.5px] leading-[1.75] text-foreground/90">{block.text}</p>
    case "list":
      return (
        <ul className="mb-4 space-y-2 text-[15.5px] leading-[1.75] text-foreground/90">
          {block.items.map((it, i) => (
            <li key={i} className="flex gap-3">
              <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
              <span>{it}</span>
            </li>
          ))}
        </ul>
      )
    case "figure":
      return (
        <figure className="my-6 overflow-hidden rounded-2xl border border-border bg-card">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={block.src || "/placeholder.svg"} alt={block.caption} className="w-full" />
          <figcaption className="border-t border-border px-4 py-3 text-sm text-muted-foreground">
            {block.caption}
          </figcaption>
        </figure>
      )
    case "slide":
      return <SlideBlock src={block.src} pageNumber={block.pageNumber} total={0} />
    case "callout": {
      const variants = {
        clinical: {
          label: "Clinical",
          Icon: AlertTriangle,
          className: "border-destructive/30 bg-destructive/5 text-foreground",
          labelClass: "text-destructive",
        },
        highyield: {
          label: "High yield",
          Icon: Sparkles,
          className: "border-primary/30 bg-primary/5 text-foreground",
          labelClass: "text-primary",
        },
        mnemonic: {
          label: "Mnemonic",
          Icon: Highlighter,
          className: "border-accent/30 bg-accent/10 text-foreground",
          labelClass: "text-accent",
        },
      }[block.variant]
      return (
        <aside className={`my-6 rounded-2xl border p-4 ${variants.className}`}>
          <div className={`flex items-center gap-2 text-[11px] font-medium uppercase tracking-widest ${variants.labelClass}`}>
            <variants.Icon className="size-3.5" aria-hidden="true" />
            {variants.label}
          </div>
          <p className="mt-1 font-serif text-lg">{block.title}</p>
          <p className="mt-1 text-[14.5px] leading-relaxed text-foreground/90">{block.body}</p>
        </aside>
      )
    }
  }
}

function FallbackContent({
  title,
  onExplain,
  articleRef,
}: {
  title: string
  onExplain: (t: string) => void
  articleRef: React.RefObject<HTMLElement | null>
}) {
  return (
    <article ref={articleRef} className="space-y-4">
      <HintBar />
      <h1 className="font-serif text-4xl leading-tight md:text-5xl">{title}</h1>
      <p className="text-muted-foreground">
        Slides for this material haven&apos;t been uploaded yet. Your class rep can upload a PDF or
        PowerPoint and it will appear here instantly.
      </p>
      <button
        onClick={() => onExplain("What is this page about?")}
        className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
      >
        Ask the AI tutor to summarise
      </button>
    </article>
  )
}
