"use client";
import { useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type Props = {
  src: string;
  alt: string;
  caption?: string;
  className?: string;
  onLoad?: () => void;
  onError?: () => void;
};

export function SlideViewer({ src, alt, caption, className, onLoad, onError }: Props) {
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [failedSource, setFailedSource] = useState<string | null>(null);
  return (
    <div
      className={cn(
        "flex-1 flex flex-col min-h-0 w-full relative group",
        className,
      )}
    >
      <button type="button" aria-label={`Expand ${alt.toLowerCase()}`} className="flex-1 min-h-0 w-full cursor-zoom-in"
        onClick={() => { setZoom(100); setOpen(true); }}>
      <img
        src={src} 
        alt={alt} 
        onError={() => { setFailedSource(src); onError?.(); }} onLoad={() => { setFailedSource(null); onLoad?.(); }}
        className="w-full h-full object-contain drop-shadow-sm" 
        loading="lazy" 
      />
      </button>
      {failedSource === src && <p role="alert" className="p-3 text-center text-sm">This page image could not load. Use Try again to refresh the document.</p>}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent aria-describedby={undefined} className="flex h-[90dvh] w-[95vw] max-w-none flex-col p-3 sm:max-w-none">
          <DialogTitle>{alt}</DialogTitle>
          <div className="flex items-center gap-3">
            <button aria-label="Zoom out" disabled={zoom <= 50} onClick={() => setZoom(value => Math.max(50, value - 25))}>−</button>
            <output aria-label="Zoom level">{zoom}%</output>
            <button aria-label="Zoom in" disabled={zoom >= 300} onClick={() => setZoom(value => Math.min(300, value + 25))}>+</button>
            <button onClick={() => setZoom(100)}>Fit page</button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            <img src={src} alt={`Expanded ${alt}`} style={{ width: `${zoom}%`, maxWidth: 'none' }} />
          </div>
        </DialogContent>
      </Dialog>
      {caption && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded-full border border-border text-[11px] text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
          {caption}
        </div>
      )}
    </div>
  );
}
