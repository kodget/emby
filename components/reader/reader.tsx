"use client";

/**
 * Reader — Three-panel IDE layout
 *
 * ┌──────────────────┬──────────────────────────────┐
 * │  SLIDE PANEL  │  AI CHAT / RESOURCES  │
 * └──────────────────┴──────────────────────────────┘
 *
 * ARCHITECTURE RULES (from system design spec):
 * 1. currentSlideIndex is the SINGLE SOURCE OF TRUTH
 * 2. AI is STATELESS — send context (text + image) in EVERY request
 * 3. Per-slide data stored in Maps: chatHistory, resources, mcqAnswers
 * 4. API key lives ONLY on the backend — never in frontend code
 * 5. Resources cached per-slide — check before re-generating
 */

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  BookOpenText,
  ChevronLeft,
  ChevronRight,
  ListChecks,
  PanelRightClose,
  PanelRightOpen,
  Play,
  Sparkles,
  X,
  Highlighter,
  Layers,
} from "lucide-react";

import type { Slide } from "@/lib/api";
import { aiApi, progressApi } from "@/lib/api";
import { useReadingProgress } from "@/hooks/use-reading-progress";
import { UnavailableReadingSave } from "./unavailable-reading-save";
import { cn } from "@/lib/utils";
import { ReaderContent, type SelectionPayload } from "./reader-content";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { incrementUsage } from "@/store/user-slice";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { UpgradePrompt } from "@/components/upgrade-prompt";
import {
  useSlideStore,
  type ChatMessage,
  type SlideData,
} from "@/store/slide-store";
import { prefetchSlideImages } from "@/lib/slide-image-utils";
import { AiChatPanel } from "./ai-chat-panel";
import { ResourcePanel } from "./resource-panel";
import { ExtractionNotice } from "./extraction-notice";
import { QuestionBankNotice } from "./question-bank-notice";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type Tab = "ai" | "textbook" | "videos" | "quiz" | "flashcards";

// ─────────────────────────────────────────────────────────────────────────────
// Reader
// ─────────────────────────────────────────────────────────────────────────────

export function Reader({
  courseId,
  slide,
  slideContent,
  suggestedVideos,
  courseBreadcrumb,
  onAccessDenied,
}: {
  courseId: string;
  slide: Slide;
  slideContent: any;
  suggestedVideos?: any[];
  courseBreadcrumb: string;
  onAccessDenied: () => void;
}) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("ai");
  const [selection, setSelection] = useState<SelectionPayload | null>(null);
  const requestVersion = useRef(0);
  const [loadedPage, setLoadedPage] = useState<string | null>(null);
  const accessRevoked = useRef(false);
  const searchParams = useSearchParams();
  const isSession = searchParams?.get("session") === "true";

  useEffect(() => {
    if (window.innerWidth >= 1024) {
      setPanelOpen(true);
    }
  }, []);

  const dispatch = useAppDispatch();
  const user = useAppSelector((s) => s.user);
  useEffect(() => {
    requestVersion.current++;
    useSlideStore.getState().reset();
    return () => { requestVersion.current++; useSlideStore.getState().reset(); };
  }, [slide.id, user.id, user.school, user.setName, user.isSignedIn]);


  // ── Slide store ─────────────────────────────────────────────────────────
  const {
    slides,
    currentSlideIndex,
    setSlides,
    setCurrentSlideIndex,
    addChatMessage,
    getChatHistory,
    setLoading,
    isLoading,
  } = useSlideStore();

  // ── Build slides array from slideContent ─────────────────────────────────
  useEffect(() => {
    if (!slideContent?.pages?.length) return;

    const builtSlides: SlideData[] = slideContent.pages.map(
      (page: any, i: number) => ({
        index: i,
        pageNumber: page.page_number ?? i + 1,
        imageUrl: page.image_url ?? "",
        text: page.text ?? slideContent.text ?? "",
        title: `${slide.title} — Page ${page.page_number ?? i + 1}`,
        slideId: slide.id,
      }),
    );
    setSlides(builtSlides);
  }, [slideContent, slide.id, slide.title, setSlides]);

  // ── Prefetch next slide images ────────────────────────────────────────────
  useEffect(() => {
    if (!slides.length) return;
    const urls = slides.map((s) => s.imageUrl);
    prefetchSlideImages(urls, currentSlideIndex, 2);
  }, [currentSlideIndex, slides]);

  const pageKey = `${currentSlideIndex}:${slideContent?.pages?.[currentSlideIndex]?.image_url ?? ''}`;
  const reading = useReadingProgress({ sourceId: slide.id, namespace: 'course-reading',
    initialPage: Number(searchParams.get('page')) || undefined,
    ready: slides.length > 0, page: currentSlideIndex + 1, maxPage: slides.length, loaded: loadedPage === pageKey,
    setPage: page => {
      const index = Math.max(0, Math.min(slides.length - 1, page - 1));
      if (index !== useSlideStore.getState().currentSlideIndex) setLoadedPage(null);
      setCurrentSlideIndex(index);
    },
    load: async () => {
      const rows = await progressApi.getProgress(slide.id);
      const saved = rows.find(row => row.slide === slide.id);
      return { current_page: Math.max(1, Math.min(slides.length, saved?.current_page ?? 1)) };
    },
    save: data => progressApi.updateProgress({ slide_id: slide.id, ...data }),
    authorized: () => !accessRevoked.current,
    denied: () => { accessRevoked.current = true; onAccessDenied(); },
  });

  // ── AI chat ───────────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      const version = requestVersion.current;
      const session = sessionStorage.getItem('user');
      const active = () => version === requestVersion.current && session === sessionStorage.getItem('user');
      const idx = currentSlideIndex;
      const currentSlide = slides[idx];

      // Add user message immediately
      const userMsg: ChatMessage = {
        id: `u-${Date.now()}`,
        role: "user",
        content: text,
      };
      addChatMessage(idx, userMsg);
      dispatch(incrementUsage("aiQuestions"));
      setLoading("chat", true);

      try {
        if (!active()) return;
        // Build conversation history for THIS slide only
        const history = getChatHistory(idx).map((m) => ({
          role: m.role === "ai" ? "assistant" : "user",
          content: m.content,
        }));

        // Call backend proxy — API key is NEVER in frontend
        const result = await aiApi.chatWithSlide({
          slide_id: slide.id,
          message: text,
          page_number: idx + 1,
          conversation_history: history,
        });

        if (!active()) return;
        const aiMsg: ChatMessage = {
          id: `a-${Date.now()}`,
          role: "ai",
          content: result.response,
          sources: result.sources,
          youtube: result.youtube
            ? {
                title: result.youtube.title,
                channel: result.youtube.channel,
                query: result.youtube.title,
                isDissection: result.youtube.isDissection,
              }
            : undefined,
        };
        addChatMessage(idx, aiMsg);
      } catch (err) {
        if (!active()) return;
        addChatMessage(idx, {
          id: `err-${Date.now()}`,
          role: "ai",
          content:
            "Sorry, I had trouble answering that. Please try again in a moment.",
        });
      } finally {
        if (active()) setLoading("chat", false);
      }
    },
    [
      currentSlideIndex,
      slides,
      slide.id,
      addChatMessage,
      getChatHistory,
      dispatch,
      setLoading,
    ],
  );

  const askAboutSelection = useCallback(
    (text: string) => {
      setTab("ai");
      setPanelOpen(true);
      sendMessage(
        `Explain: "${text.length > 140 ? text.slice(0, 140) + "…" : text}"`,
      );
    },
    [sendMessage],
  );

  // ── Navigation ────────────────────────────────────────────────────────────
  const goToPage = (newIndex: number) => {
    const clampedIndex = Math.max(0, Math.min(newIndex, slides.length - 1));
    reading.changePage(clampedIndex + 1);
    setSelection(null);
  };

  const totalPages = slides.length || slide.page_count || 1;
  const canPrev = currentSlideIndex > 0;
  const canNext = currentSlideIndex < totalPages - 1;

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col">
      <ExtractionNotice key={slide.id} slideId={slide.id} summary={slideContent?.text_extraction} aiIndex={slideContent?.ai_index} canReprocess={slideContent?.can_reprocess} />
      <QuestionBankNotice key={`${slide.id}:${user.id}:${user.school}:${user.setName}`} slideId={slide.id} canGenerate={!!slideContent?.can_reprocess} textReady={slideContent?.text_extraction?.status === "complete"} />
      {reading.loadError && <div role="status" className="p-2 text-center text-sm">
        Your saved reading position could not be loaded. Reading time is paused until you retry. <button className="underline" onClick={reading.retry}>Retry saved position</button>
      </div>}
      {reading.unavailableSave && <UnavailableReadingSave checkpoint={reading.unavailableSave}
        retry={reading.retry} discard={reading.discardUnavailable} />}
      {reading.saveError && !reading.unavailableSave && <div role="status" className="p-2 text-center text-sm">
        Your reading position and time have not synced. Keep this tab open and retry. <button className="underline" onClick={reading.retry}>Retry saving</button>
      </div>}
      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <ReaderToolbar
        courseId={courseId}
        courseBreadcrumb={courseBreadcrumb}
        slideTitle={slide.title}
        panelOpen={panelOpen}
        onTogglePanel={() => setPanelOpen((v) => !v)}
      />

      <div className="flex flex-1 min-h-0 relative">
        {/* ── Center: Slide Viewer ────────────────────────────────────────── */}
        <div
          className={cn(
            "flex-1 min-w-0 border-r border-border transition-[margin] flex flex-col",
            slideContent && slideContent.pages && slideContent.pages.length > 0 ? "overflow-hidden bg-muted/20" : "overflow-y-auto"
          )}
        >
          <div className={cn("mx-auto w-full flex-1 flex flex-col min-h-0", slideContent && slideContent.pages && slideContent.pages.length > 0 ? "px-0 py-0" : "px-4 sm:px-8 py-6")}>
            <ReaderContent
              blocks={[]}
              slideContent={slideContent}
              currentPageIndex={currentSlideIndex}
              onPageLoad={() => setLoadedPage(pageKey)}
              onPageError={() => setLoadedPage(null)}
              onSelect={setSelection}
              onExplain={askAboutSelection}
              fallbackTitle={slide.title}
            />

            {/* ── Page navigation ─────────────────────────────────────── */}
            <nav
              className={cn(
                "shrink-0 flex items-center justify-between border-t border-border text-sm",
                slideContent && slideContent.pages && slideContent.pages.length > 0 ? "px-6 py-3 bg-card" : "mt-10 pt-6"
              )}
              aria-label="Page navigation"
            >
              <button
                type="button"
                disabled={!canPrev}
                onClick={() => goToPage(currentSlideIndex - 1)}
                className="inline-flex h-10 items-center gap-1.5 rounded-full border border-border bg-card px-4 text-muted-foreground hover:text-foreground disabled:opacity-40"
              >
                <ChevronLeft className="size-4" />
                Previous
              </button>

              <p className="text-muted-foreground">
                Page{" "}
                <span className="font-medium text-foreground">
                  {currentSlideIndex + 1}
                </span>{" "}
                of {totalPages}
              </p>

              <button
                type="button"
                disabled={!canNext}
                onClick={() => goToPage(currentSlideIndex + 1)}
                className="inline-flex h-10 items-center gap-1.5 rounded-full bg-primary px-4 text-primary-foreground hover:opacity-90 disabled:opacity-40"
              >
                Next
                <ChevronRight className="size-4" />
              </button>
            </nav>
          </div>
        </div>

        {/* ── Right: AI + Resource Panel ───────────────────────────────── */}
        {panelOpen && (
          <aside className={cn(
            "absolute inset-0 z-40 flex flex-col border-l border-border bg-card lg:static lg:h-[calc(100vh-4rem-3.5rem)] lg:w-[420px] lg:z-auto shadow-2xl lg:shadow-none",
            isSession ? "pb-28" : ""
          )}>
            <PanelTabs tab={tab} onChange={setTab} onClose={() => setPanelOpen(false)} />
            <div className="flex-1 min-h-0 overflow-y-auto">
              {/* AI Chat */}
              {tab === "ai" && (
                  <AiChatPanel
                    slideIndex={currentSlideIndex}
                    isLoading={isLoading.chat}
                    onSend={sendMessage}
                  />
                )}

              {/* Resources: textbook + videos + MCQs + Flashcards */}
              {(tab === "textbook" || tab === "videos" || tab === "quiz" || tab === "flashcards") && (
                  <ResourcePanel
                    slideId={slide.id}
                    slideIndex={currentSlideIndex}
                    activeTab={tab}
                    onTabChange={(t) => setTab(t as Tab)}
                    selection={selection?.text ?? null}
                  />
                )}
            </div>
          </aside>
        )}
      </div>

      {/* ── Floating selection toolbar ──────────────────────────────────── */}
      {selection && (
        <SelectionFab
          selection={selection}
          onExplain={() => askAboutSelection(selection.text)}
          onVideo={() => {
            setTab("videos");
            setPanelOpen(true);
          }}
          onQuiz={() => {
            setTab("quiz");
            setPanelOpen(true);
          }}
          onClose={() => setSelection(null)}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Toolbar
// ─────────────────────────────────────────────────────────────────────────────

function ReaderToolbar({
  courseId,
  courseBreadcrumb,
  slideTitle,
  panelOpen,
  onTogglePanel,
}: {
  courseId: string;
  courseBreadcrumb: string;
  slideTitle: string;
  panelOpen: boolean;
  onTogglePanel: () => void;
}) {
  return (
    <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-border bg-background/90 px-4 py-2.5 backdrop-blur-md sm:px-6">
      <Link
        href={`/courses/${courseId}`}
        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground ml-1"
      >
        <ArrowLeft className="size-4" />
        <span className="hidden sm:inline">Back</span>
      </Link>
      <span className="hidden text-xs text-muted-foreground sm:inline">/</span>
      <p className="truncate flex-1 min-w-0 text-xs text-muted-foreground">
        <span className="text-foreground">{courseBreadcrumb}</span> ·{" "}
        {slideTitle}
      </p>
      <div className="ml-auto flex shrink-0 items-center gap-2">
        <span className="hidden items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-medium text-primary md:inline-flex">
          <Sparkles className="size-3.5" />
          Emby tutor
        </span>
        <button
          type="button"
          onClick={onTogglePanel}
          aria-pressed={panelOpen}
          aria-label={panelOpen ? "Hide Emby panel" : "Show Emby panel"}
          className="flex size-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground"
        >
          {panelOpen ? (
            <PanelRightClose className="size-4" />
          ) : (
            <PanelRightOpen className="size-4" />
          )}
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Panel Tabs
// ─────────────────────────────────────────────────────────────────────────────

function PanelTabs({
  tab,
  onChange,
  onClose,
}: {
  tab: Tab;
  onChange: (t: Tab) => void;
  onClose: () => void;
}) {
  const tabs: {
    id: Tab;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
  }[] = [
    { id: "ai", label: "Emby", icon: Sparkles },
    { id: "textbook", label: "Books", icon: BookOpenText },
    { id: "videos", label: "Videos", icon: Play },
    { id: "quiz", label: "Quiz", icon: ListChecks },
    { id: "flashcards", label: "Cards", icon: Layers },
  ];
  return (
    <div className="flex items-center justify-between border-b border-border px-3 py-2 gap-2">
      <div className="flex flex-1 min-w-0 items-center gap-1 overflow-x-auto no-scrollbar">
        {tabs.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => onChange(t.id)}
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted",
              )}
              aria-pressed={active}
            >
              <t.icon className="size-3.5" />
              {t.label}
            </button>
          );
        })}
      </div>
      <button
        onClick={onClose}
        aria-label="Close panel"
        className="ml-2 flex shrink-0 size-8 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"
      >
        <PanelRightClose className="size-4" />
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Selection FAB
// ─────────────────────────────────────────────────────────────────────────────

function SelectionFab({
  selection,
  onExplain,
  onVideo,
  onQuiz,
  onClose,
}: {
  selection: SelectionPayload;
  onExplain: () => void;
  onVideo: () => void;
  onQuiz: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const style: React.CSSProperties = selection.rect
    ? {
        position: "fixed",
        top: Math.max(12, selection.rect.top - 52),
        left: selection.rect.left + selection.rect.width / 2,
        transform: "translateX(-50%)",
      }
    : {
        position: "fixed",
        bottom: 24,
        left: "50%",
        transform: "translateX(-50%)",
      };

  return (
    <div
      ref={ref}
      style={style}
      role="toolbar"
      aria-label="Highlight actions"
      className="z-40 flex items-center gap-1 rounded-full border border-border bg-card p-1 shadow-xl shadow-foreground/10"
    >
      <button
        onClick={onExplain}
        className="inline-flex items-center gap-1.5 rounded-full bg-primary px-3 py-1.5 text-[12px] font-medium text-primary-foreground hover:opacity-90"
      >
        <Sparkles className="size-3.5" />
        Explain
      </button>
      <button
        onClick={onVideo}
        className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium text-foreground hover:bg-muted"
      >
        <Play className="size-3.5" />
        Find video
      </button>
      <button
        onClick={onQuiz}
        className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium text-foreground hover:bg-muted"
      >
        <ListChecks className="size-3.5" />
        Quiz me
      </button>
      <button
        onClick={() => {
          onClose();
          window.getSelection()?.removeAllRanges();
        }}
        aria-label="Dismiss"
        className="ml-0.5 inline-flex size-7 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}
