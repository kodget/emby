"use client";

import { useEffect, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileText,
  Loader2,
  MessageCircle,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { SlideDeck, SlidePage } from "@/lib/api";
import { deckApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { usePrivateMediaRefresh } from "@/hooks/use-private-media-refresh";
import { DeckQuestionBank } from "./deck-question-bank";
import { DeckAiChat } from "./deck-ai-chat";
import { useDeckReading } from "@/hooks/use-deck-reading";
import { UnavailableReadingSave } from "./unavailable-reading-save";

type ViewMode = "fit" | "fill" | "100";

export function DeckReader({
  deckId,
  title,
}: {
  deckId: string;
  title: string;
}) {
  const [deck, setDeck] = useState<SlideDeck | null>(null);
  const [pages, setPages] = useState<SlidePage[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [viewMode, setViewMode] = useState<ViewMode>("fit");
  const [attempt, setAttempt] = useState(0);
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [loadedPage, setLoadedPage] = useState<number | null>(null);
  const requestVersion = useRef(0);
  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const accessRevoked = useRef(false);
  const denyAccess = () => {
    accessRevoked.current = true;
    setPages([]); setDeck(null); setLoading(false); setProcessing(false);
    setError("This document is no longer available to your class.");
  };
  const refreshMedia = usePrivateMediaRefresh(deckId, () => deckApi.getPages(deckId),
    (freshPages) => { if (!accessRevoked.current) {
      setPages(freshPages); setCurrentPage(page => Math.min(page, Math.max(1, freshPages.length)));
    } }, denyAccess);
  const reading = useDeckReading({ deckId,
    ready: !!deck && pages.length > 0 && !loading && !processing && !error,
    page: currentPage, maxPage: pages.length, loaded: loadedPage === currentPage && !imageError,
    setPage: value => setCurrentPage(Math.max(1, Math.min(value, pages.length))),
    denied: denyAccess, authorized: () => !accessRevoked.current,
  });

  // Load deck
  useEffect(() => {
    requestVersion.current++;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const session = sessionStorage.getItem("user");
    accessRevoked.current = false;
    const active = () => !cancelled && !accessRevoked.current && session === sessionStorage.getItem("user");
    setDeck(null); setPages([]); setCurrentPage(1); setError(null); setProcessing(false);
    setDownloadError(""); setDownloading(false); setImageError(false); setLoadedPage(null);

    const poll = async () => {
      if (!active()) return;
      try {
        const updated = await deckApi.checkStatus(deckId);
        if (!active()) return;
        if (updated.processing_status === "completed") {
          const pageData = await deckApi.getPages(deckId);
          if (!active()) return;
          setDeck(updated); setPages(pageData); setProcessing(false);
          return;
        }
        if (updated.processing_status === "failed") {
          setError(updated.processing_error || "Processing failed");
          setProcessing(false);
          return;
        }
      } catch (err: any) {
        if (!active()) return;
        if ([401, 403, 404].includes(err?.response?.status)) { denyAccess(); return; }
        setError("Could not check document processing. Please try again.");
        setProcessing(false);
        return;
      }
      if (active()) timer = setTimeout(poll, 2000);
    };

    const loadDeck = async () => {
      try {
        setLoading(true);
        const deckData = await deckApi.getDeck(deckId);
        if (!active()) return;
        setDeck(deckData);

        // If still processing, show spinner
        if (["pending", "processing"].includes(deckData.processing_status)) {
          setProcessing(true);
          timer = setTimeout(poll, 2000);
          return;
        }

        if (deckData.processing_status === "failed") {
          setError(deckData.processing_error || "Processing failed");
          return;
        }

        // Load pages
        if (deckData.pages && deckData.pages.length > 0) {
          setPages(deckData.pages);
        } else {
          const pageData = await deckApi.getPages(deckId);
          if (active()) setPages(pageData);
        }
      } catch (err: any) {
        if (!active()) return;
        if ([401, 403, 404].includes(err?.response?.status)) denyAccess();
        else setError("Could not load this document. Please try again.");
      } finally {
        if (active()) setLoading(false);
      }
    };

    loadDeck();
    return () => { cancelled = true; requestVersion.current++; if (timer) clearTimeout(timer); };
  }, [deckId, attempt]);

  const currentPageData = pages[currentPage - 1];

  const handlePrevious = () => {
    if (currentPage > 1) {
      reading.changePage(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < pages.length) {
      reading.changePage(currentPage + 1);
    }
  };

  const handleZoom = (delta: number) => {
    setZoom(Math.max(50, Math.min(200, zoom + delta)));
  };

  const handleDownload = async () => {
    if (!currentPageData) return;
    const session = sessionStorage.getItem("user");
    const version = requestVersion.current;
    const active = () => version === requestVersion.current && !accessRevoked.current && session === sessionStorage.getItem("user");
    setDownloadError(""); setDownloading(true);
    try {
      const freshPages = await deckApi.getPages(deckId);
      if (!active()) return;
      setPages(freshPages);
      setCurrentPage(page => Math.min(page, Math.max(1, freshPages.length)));
      const freshPage = freshPages.find((page) => page.slide_number === currentPageData.slide_number);
      if (!freshPage) throw new Error("Page is no longer available");
      const response = await fetch(freshPage.image_url);
      if (!response.ok) throw new Error("Download failed");
      const blob = await response.blob();
      if (!active()) return;
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${deck?.title || title}_page_${currentPage}.${blob.type === 'image/png' ? 'png' : 'jpg'}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      if (!active()) return;
      if ([401, 403, 404].includes(err?.response?.status)) denyAccess();
      else setDownloadError("Could not download this page. Please try again.");
    } finally {
      if (active()) setDownloading(false);
    }
  };

  if (loading && !processing) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-100">
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin" />
          <p className="text-gray-600">Loading deck...</p>
        </div>
      </div>
    );
  }

  if (processing) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-100">
        <div role="status" className="rounded-lg bg-white p-8 text-center shadow-lg">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-blue-600" />
          <h3 className="mb-2 text-lg font-semibold">Converting Document</h3>
          <p className="text-gray-600">
            Processing {deck?.file_type || "file"}... This may take a moment
          </p>
          {deck && (
            <p className="mt-4 text-sm text-gray-500">
              File size: {(deck.file_size / 1024 / 1024).toFixed(2)} MB
            </p>
          )}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-100">
        <div role="alert" className="rounded-lg bg-white p-8 text-center shadow-lg">
          <X className="mx-auto mb-4 h-8 w-8 text-red-600" />
          <h3 className="mb-2 text-lg font-semibold text-red-600">Error</h3>
          <p className="text-gray-600">{error}</p>
          <button className="mt-4 underline" onClick={() => setAttempt(value => value + 1)}>Try again</button>
          <a className="m-4 underline" href="/decks">Back to documents</a>
          {deck?.processing_error && (
            <p className="mt-2 text-sm text-gray-500">
              {deck.processing_error}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (!deck || pages.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-100">
        <div role="status" className="text-center text-gray-600"><p>No pages available yet.</p>
          <button className="m-4 underline" onClick={() => setAttempt(value => value + 1)}>Try again</button>
          <a className="m-4 underline" href="/decks">Back to documents</a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100dvh-4rem)] min-h-0 flex-col bg-gray-900">
      {reading.unavailableSave && <UnavailableReadingSave checkpoint={reading.unavailableSave}
        retry={reading.retry} discard={reading.discardUnavailable} />}
      {(reading.loadError || (reading.saveError && !reading.unavailableSave)) && <p role="alert" className="bg-amber-950 p-3 text-sm text-amber-100">
        {reading.loadError ? 'Could not load your saved reading position. Reading time is paused until this is retried.'
          : 'Your reading progress has not synced. Keep this tab open and retry.'}{' '}
        <button className="underline" onClick={reading.retry}>Retry reading progress</button>
      </p>}
      <DeckQuestionBank key={deckId} deckId={deckId} />
      {deck.text_extraction?.status !== "complete" && <p role="status" aria-label="Document text status" className="bg-amber-950 p-3 text-sm text-amber-100">
        {deck.text_extraction?.missing_pages?.length
          ? `Text could not be fully read on pages ${deck.text_extraction.missing_pages.join(", ")}.`
          : "Document text has not been fully checked yet."} The original pages are still available to read.
      </p>}
      {downloadError && <p role="alert" className="bg-red-950 p-2 text-center text-white">{downloadError}</p>}
      {imageError && <div role="alert" className="bg-red-950 p-2 text-center text-white">
        This page could not be displayed. <button className="underline" onClick={() => setAttempt(value => value + 1)}>Try again</button>
      </div>}
      {/* Header */}
      <div className="border-b border-gray-700 bg-gray-800 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <FileText className="h-6 w-6 text-blue-400" />
            <div>
              <h1 className="text-lg font-semibold text-white">{deck.title || title}</h1>
              <p className="text-sm text-gray-400">
                {deck.file_type.toUpperCase()} • {pages.length} pages
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-sm text-gray-400">
              Page {currentPage} of {pages.length}
            </div>
            <button
              type="button"
              onClick={() => setChatOpen(open => !open)}
              aria-expanded={chatOpen}
              aria-label={chatOpen ? "Close document AI chat" : "Ask AI about this document"}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-500"
            >
              <MessageCircle className="size-4" />
              <span>{chatOpen ? "Close Emby" : "Ask Emby"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Viewer */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* Main image area */}
        <div className="flex-1 flex items-center justify-center overflow-auto bg-gray-900">
          {currentPageData && (
            <div
              ref={containerRef}
              className="flex items-center justify-center"
              style={{
                width: "100%",
                height: "100%",
              }}
            >
              <img
                key={`${currentPage}:${currentPageData?.image_url}`}
                ref={imageRef}
                src={currentPageData.image_url}
                onError={() => { setImageError(true); void refreshMedia(); }}
                onLoad={() => { setImageError(false); setLoadedPage(currentPage); }}
                alt={`Page ${currentPage}`}
                className="max-h-full max-w-full object-contain"
                style={{
                  zoom: viewMode === "100" ? `${zoom}%` : "auto",
                  width: viewMode === "fill" ? "100%" : "auto",
                  height: viewMode === "fill" ? "100%" : "auto",
                }}
              />
            </div>
          )}
        </div>
        {chatOpen && (
          <aside className="absolute inset-0 z-10 bg-gray-900 lg:static lg:w-[390px] lg:shrink-0">
            <DeckAiChat key={deckId} deckId={deckId} title={deck.title || title} />
          </aside>
        )}
      </div>

      {/* Toolbar */}
      <div className="border-t border-gray-700 bg-gray-800 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          {/* Navigation */}
          <div className="flex items-center space-x-2">
            <button
              onClick={handlePrevious}
              disabled={currentPage === 1}
              className="rounded p-2 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Previous page"
            >
              <ChevronLeft className="h-5 w-5 text-white" />
            </button>

            <div className="px-3 py-1 text-sm text-gray-300">
              <input
                aria-label="Page number"
                type="number"
                min="1"
                max={pages.length}
                value={currentPage}
                onChange={(e) => {
                  const page = Math.min(
                    pages.length,
                    Math.max(1, parseInt(e.target.value) || 1),
                  );
                  reading.changePage(page);
                }}
                className="w-12 rounded bg-gray-700 px-2 py-1 text-center text-white"
              />
              <span className="ml-1">/ {pages.length}</span>
            </div>

            <button
              onClick={handleNext}
              disabled={currentPage === pages.length}
              className="rounded p-2 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Next page"
            >
              <ChevronRight className="h-5 w-5 text-white" />
            </button>
          </div>

          {/* View controls */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setViewMode("fit")}
              className={cn(
                "rounded px-3 py-2 text-sm font-medium",
                viewMode === "fit"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600",
              )}
              title="Fit to window"
            >
              Fit
            </button>

            <button
              onClick={() => setViewMode("fill")}
              className={cn(
                "rounded px-3 py-2 text-sm font-medium",
                viewMode === "fill"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600",
              )}
              title="Fill window"
            >
              Fill
            </button>

            <button
              onClick={() => setViewMode("100")}
              className={cn(
                "rounded px-3 py-2 text-sm font-medium",
                viewMode === "100"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600",
              )}
              title="100% zoom"
            >
              100%
            </button>

            {viewMode === "100" && (
              <>
                <div className="w-px h-6 bg-gray-600" />

                <button
                  onClick={() => handleZoom(-10)}
                  className="rounded p-2 hover:bg-gray-700"
                  title="Zoom out"
                >
                  <ZoomOut className="h-5 w-5 text-white" />
                </button>

                <span className="px-2 text-sm text-gray-300 w-12 text-center">
                  {zoom}%
                </span>

                <button
                  onClick={() => handleZoom(10)}
                  className="rounded p-2 hover:bg-gray-700"
                  title="Zoom in"
                >
                  <ZoomIn className="h-5 w-5 text-white" />
                </button>
              </>
            )}

            <div className="w-px h-6 bg-gray-600" />

            <button
              onClick={handleDownload}
              disabled={downloading}
              className="rounded p-2 hover:bg-gray-700"
              title="Download page"
            >
              <Download className="h-5 w-5 text-white" />
            </button>
          </div>

          {/* File info */}
          <div className="text-sm text-gray-400">
            {currentPageData && (
              <span>
                {currentPageData.width} × {currentPageData.height}px
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
