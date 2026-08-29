"use client";

/**
 * Immersive slide viewing.
 *
 * A rendered slide is a dense A4-shaped image. Inside a phone-width column it is roughly
 * thumbnail-sized and the text on it is unreadable, which made the reader close to
 * useless on a phone. This gives every slide a way to fill the screen.
 *
 * What it does:
 *   - opens the slide over the whole viewport, using the real Fullscreen API where the
 *     browser allows it and a fixed overlay everywhere else (iOS Safari has no
 *     Fullscreen API on iPhone, so the fallback is the normal path there, not an edge case)
 *   - rotates the slide to fill a landscape phone, since turning the device is the
 *     natural thing to do with a wide slide
 *   - pinch-to-zoom and double-tap-to-zoom, with panning once zoomed
 *   - keeps a always-visible exit affordance, and honours the Escape key and the
 *     Android back gesture
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Maximize2, RotateCw, X, ZoomIn } from "lucide-react";

import { cn } from "@/lib/utils";

type Props = {
  src: string;
  alt: string;
  caption?: string;
  className?: string;
};

export function SlideViewer({ src, alt, caption, className }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <figure
        className={cn(
          "group relative overflow-hidden rounded-2xl border border-border bg-card depth-2",
          className,
        )}
      >
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="press block w-full"
          aria-label={`Open ${alt} full screen`}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={alt} className="w-full" loading="lazy" />
        </button>

        {/* Always visible on touch, where hover does not exist. */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-3 flex items-center gap-1.5 rounded-full bg-foreground/75 px-2.5 py-1 text-[11px] font-medium text-background backdrop-blur md:opacity-0 md:transition-opacity md:group-hover:opacity-100"
        >
          <Maximize2 className="size-3" />
          Expand
        </span>

        {caption && (
          <figcaption className="border-t border-border px-4 py-2.5 text-[11px] text-muted-foreground">
            {caption}
          </figcaption>
        )}
      </figure>

      {open && <ImmersiveSlide src={src} alt={alt} onClose={() => setOpen(false)} />}
    </>
  );
}

function ImmersiveSlide({
  src,
  alt,
  onClose,
}: {
  src: string;
  alt: string;
  onClose: () => void;
}) {
  const shellRef = useRef<HTMLDivElement>(null);
  const [rotated, setRotated] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  const pointers = useRef<Map<number, { x: number; y: number }>>(new Map());
  const pinchStart = useRef<{ dist: number; zoom: number } | null>(null);
  const panStart = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const lastTap = useRef(0);

  // Lock the page behind the overlay, and restore it exactly on close.
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);

    // A history entry means the Android back gesture closes the viewer rather than
    // navigating away from the slide entirely.
    window.history.pushState({ slideViewer: true }, "");
    const onPop = () => onClose();
    window.addEventListener("popstate", onPop);

    // Real fullscreen where it exists. iPhone Safari has none, so this quietly
    // no-ops and the fixed overlay does the job.
    const el = shellRef.current;
    if (el?.requestFullscreen) {
      el.requestFullscreen().catch(() => {});
    }

    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("popstate", onPop);
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    };
  }, [onClose]);

  const resetView = useCallback(() => {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }, []);

  const distance = (a: { x: number; y: number }, b: { x: number; y: number }) =>
    Math.hypot(a.x - b.x, a.y - b.y);

  const onPointerDown = (e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinchStart.current = { dist: distance(a, b), zoom };
    } else if (pointers.current.size === 1) {
      panStart.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };

      // Double tap toggles between fit and 2x, centred on the tap.
      const now = Date.now();
      if (now - lastTap.current < 280) {
        if (zoom > 1) resetView();
        else setZoom(2);
      }
      lastTap.current = now;
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (pointers.current.size === 2 && pinchStart.current) {
      const [a, b] = [...pointers.current.values()];
      const scale = distance(a, b) / (pinchStart.current.dist || 1);
      setZoom(Math.max(1, Math.min(5, pinchStart.current.zoom * scale)));
      return;
    }

    // Panning only makes sense once the image is bigger than the screen.
    if (pointers.current.size === 1 && panStart.current && zoom > 1) {
      setOffset({
        x: panStart.current.ox + (e.clientX - panStart.current.x),
        y: panStart.current.oy + (e.clientY - panStart.current.y),
      });
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinchStart.current = null;
    if (pointers.current.size === 0) {
      panStart.current = null;
      if (zoom <= 1) setOffset({ x: 0, y: 0 });
    }
  };

  return (
    <div
      ref={shellRef}
      className="fixed inset-0 z-[100] flex touch-none flex-col bg-black"
      role="dialog"
      aria-modal="true"
      aria-label={alt}
    >
      <div
        className="flex flex-1 items-center justify-center overflow-hidden"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt}
          draggable={false}
          className={cn(
            "select-none will-change-transform",
            // Rotated, the slide's height is bounded by the viewport *width*, which is
            // what lets a landscape slide fill a portrait phone.
            rotated ? "max-h-[100vw] max-w-[100vh]" : "max-h-full max-w-full",
          )}
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom}) rotate(${rotated ? 90 : 0}deg)`,
            transition: pinchStart.current || panStart.current ? "none" : "transform 0.2s ease-out",
          }}
        />
      </div>

      {/* Controls sit above the home indicator and stay reachable at any zoom. */}
      <div className="flex items-center justify-center gap-2 pb-safe pt-2">
        <div className="mb-3 flex items-center gap-1.5 rounded-full bg-white/12 p-1.5 backdrop-blur">
          <ViewerButton onClick={() => setRotated((r) => !r)} label="Rotate">
            <RotateCw className="size-4" />
          </ViewerButton>
          <ViewerButton
            onClick={() => (zoom > 1 ? resetView() : setZoom(2))}
            label={zoom > 1 ? "Fit to screen" : "Zoom in"}
          >
            <ZoomIn className="size-4" />
          </ViewerButton>
          <span className="px-1 font-mono text-[11px] tabular text-white/70">
            {Math.round(zoom * 100)}%
          </span>
          <ViewerButton onClick={onClose} label="Close" emphasis>
            <X className="size-4" />
          </ViewerButton>
        </div>
      </div>

      <p className="pointer-events-none absolute inset-x-0 top-3 text-center text-[11px] text-white/50">
        Pinch or double-tap to zoom · swipe down on the close button to exit
      </p>
    </div>
  );
}

function ViewerButton({
  onClick,
  label,
  children,
  emphasis = false,
}: {
  onClick: () => void;
  label: string;
  children: React.ReactNode;
  emphasis?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={cn(
        "press flex size-10 items-center justify-center rounded-full text-white",
        emphasis ? "bg-white/25" : "hover:bg-white/15",
      )}
    >
      {children}
    </button>
  );
}
