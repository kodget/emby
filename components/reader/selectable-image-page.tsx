"use client"

import { useState } from "react"

type TextBlock = {
  text: string
  x: number
  y: number
  width: number
  height: number
  font_size: number
  font: string
  color: number
}

type PageData = {
  page_number: number
  image_url: string
  width: number
  height: number
  text_blocks: TextBlock[]
}

export function SelectableImagePage({ page }: { page: PageData }) {
  const [imageLoaded, setImageLoaded] = useState(false)

  return (
    <figure className="relative overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
      {/* Base image */}
      <div className="relative">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={page.image_url}
          alt={`Page ${page.page_number}`}
          className="w-full"
          loading={page.page_number <= 3 ? "eager" : "lazy"}
          onLoad={() => setImageLoaded(true)}
        />
        
        {/* Invisible text overlay for selection */}
        {imageLoaded && page.text_blocks && page.text_blocks.length > 0 && (
          <div 
            className="absolute inset-0 pointer-events-auto"
            style={{
              width: page.width,
              height: page.height,
            }}
          >
            {page.text_blocks.map((block, idx) => (
              <span
                key={idx}
                className="absolute select-text cursor-text"
                style={{
                  left: `${block.x}px`,
                  top: `${block.y}px`,
                  width: `${block.width}px`,
                  height: `${block.height}px`,
                  fontSize: `${block.font_size}px`,
                  lineHeight: `${block.height}px`,
                  color: 'transparent',
                  userSelect: 'text',
                  WebkitUserSelect: 'text',
                  MozUserSelect: 'text',
                  msUserSelect: 'text',
                }}
              >
                {block.text}
              </span>
            ))}
          </div>
        )}
      </div>
      
      {/* Page caption */}
      <figcaption className="flex items-center justify-between border-t border-border px-4 py-2.5 text-[11px] text-muted-foreground">
        <span>Page {page.page_number}</span>
        <span>{page.text_blocks?.length || 0} text blocks</span>
      </figcaption>
    </figure>
  )
}
