"use client";

import { useEffect, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileText,
  Loader2,
  X,
  Zoom,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { SlideDeck, SlidePage } from "@/lib/api";
import { deckApi } from "@/lib/api";
import { cn } from "@/lib/utils";

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
  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Load deck
  useEffect(() => {
    const loadDeck = async () => {
      try {
        setLoading(true);
        const deckData = await deckApi.getDeck(deckId);
        setDeck(deckData);

        // If still processing, show spinner
        if (deckData.processing_status === "processing") {
          setProcessing(true);
          // Poll for completion every 2 seconds
          const interval = setInterval(async () => {
            const updated = await deckApi.checkStatus(deckId);
            if (updated.processing_status === "completed") {
              setDeck(updated);
              setProcessing(false);
              clearInterval(interval);
              // Reload pages
              const pageData = await deckApi.getPages(deckId);
              setPages(pageData);
            } else if (updated.processing_status === "failed") {
              setError(updated.processing_error || "Processing failed");
              setProcessing(false);
              clearInterval(interval);
            }
          }, 2000);

          return;
        }

        // Load pages
        if (deckData.pages && deckData.pages.length > 0) {
          setPages(deckData.pages);
        } else {
          const pageData = await deckApi.getPages(deckId);
          setPages(pageData);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load deck");
      } finally {
        setLoading(false);
      }
    };

    loadDeck();
  }, [deckId]);

  const currentPageData = pages[currentPage - 1];

  const handlePrevious = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < pages.length) {
      setCurrentPage(currentPage + 1);
    }
  };

  const handleZoom = (delta: number) => {
    setZoom(Math.max(50, Math.min(200, zoom + delta)));
  };

  const handleDownload = async () => {
    if (!currentPageData) return;
    try {
      const response = await fetch(currentPageData.image_url);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title}_page_${currentPage}.png`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Download failed:", err);
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
        <div className="rounded-lg bg-white p-8 text-center shadow-lg">
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
        <div className="rounded-lg bg-white p-8 text-center shadow-lg">
          <X className="mx-auto mb-4 h-8 w-8 text-red-600" />
          <h3 className="mb-2 text-lg font-semibold text-red-600">Error</h3>
          <p className="text-gray-600">{error}</p>
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
        <p className="text-gray-600">No pages available</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-gray-900">
      {/* Header */}
      <div className="border-b border-gray-700 bg-gray-800 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <FileText className="h-6 w-6 text-blue-400" />
            <div>
              <h1 className="text-lg font-semibold text-white">{title}</h1>
              <p className="text-sm text-gray-400">
                {deck.file_type.toUpperCase()} • {pages.length} pages
              </p>
            </div>
          </div>
          <div className="text-sm text-gray-400">
            Page {currentPage} of {pages.length}
          </div>
        </div>
      </div>

      {/* Viewer */}
      <div className="flex flex-1 overflow-hidden">
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
                ref={imageRef}
                src={currentPageData.image_url}
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
      </div>

      {/* Toolbar */}
      <div className="border-t border-gray-700 bg-gray-800 px-4 py-3">
        <div className="flex items-center justify-between">
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
                type="number"
                min="1"
                max={pages.length}
                value={currentPage}
                onChange={(e) => {
                  const page = Math.min(
                    pages.length,
                    Math.max(1, parseInt(e.target.value) || 1),
                  );
                  setCurrentPage(page);
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
