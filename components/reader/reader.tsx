"use client";

/**
 * Reader — Three-panel IDE layout
 *
 * ┌──────────────────┬──────────────────────────────┐
 * │  📄 SLIDE PANEL  │  🤖 AI CHAT / 📚 RESOURCES  │
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
} from "lucide-react";

import type { Slide } from "@/lib/api";
import { aiApi, progressApi, statsApi } from "@/lib/api";
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
import { imageUrlToBase64, prefetchSlideImages } from "@/lib/slide-image-utils";
import { AiChatPanel } from "./ai-chat-panel";
import { ResourcePanel } from "./resource-panel";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type Tab = "ai" | "textbook" | "videos" | "quiz";

// ─────────────────────────────────────────────────────────────────────────────
// Reader
// ─────────────────────────────────────────────────────────────────────────────

export function Reader({
  courseId,
  slide,
  slideContent,
  suggestedVideos,
  courseBreadcrumb,
}: {
  courseId: string;
  slide: Slide;
  slideContent: any;
  suggestedVideos?: any[];
  courseBreadcrumb: string;
}) {
  const [panelOpen, setPanelOpen] = useState(true);
  const [tab, setTab] = useState<Tab>("ai");
  const [selection, setSelection] = useState<SelectionPayload | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [timeSpent, setTimeSpent] = useState(0);
  const startTimeRef = useRef<number>(Date.now());

  const dispatch = useAppDispatch();
  const { hasAccess, isPremium, isTrial } = useFeatureAccess();
  const usage = useAppSelector((s) => s.user.usage);
  const user = useAppSelector((s) => s.user);

  const isClassHead = user.role === "class-rep" || user.isClassRep;
  const hasPremiumAccess = isPremium || isTrial || isClassHead;
  const hasUnlimitedAI =
    hasAccess("unlimited_ai_explanations") || hasPremiumAccess;

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

  // ── Time tracking ─────────────────────────────────────────────────────────
  useEffect(() => {
    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTimeRef.current) / 60000);
      if (elapsed > 0) {
        setTimeSpent((p) => p + elapsed);
        startTimeRef.current = Date.now();
      }
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    return () => {
      const total =
        timeSpent + Math.floor((Date.now() - startTimeRef.current) / 60000);
      if (total > 0) {
        progressApi
          .updateProgress({
            slide_id: slide.id,
            current_page: currentPage,
            total_pages: slide.page_count,
            time_spent_minutes: total,
          })
          .catch(() => {});
        statsApi.awardPoints(5, "Reading slide").catch(() => {});
        statsApi.updateStreak().catch(() => {});
      }
    };
  }, [slide.id, currentPage, timeSpent, slide.page_count]);

  // ── AI chat ───────────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      if (!hasUnlimitedAI && usage.aiQuestionsUsed >= 5) {
        alert("Daily AI limit reached. Upgrade for unlimited access.");
        return;
      }

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
        // Convert current slide image to base64 for vision API
        // Guard: slides may not be populated yet on first render
        const slideImageBase64 = currentSlide?.imageUrl
          ? await imageUrlToBase64(currentSlide.imageUrl).catch(() => undefined)
          : undefined;

        // Build conversation history for THIS slide only
        const history = getChatHistory(idx).map((m) => ({
          role: m.role === "ai" ? "assistant" : "user",
          content: m.content,
        }));

        // Call backend proxy — API key is NEVER in frontend
        const result = await aiApi.chatWithSlide({
          slide_id: slide.id,
          message: text,
          slide_image_base64: slideImageBase64,
          conversation_history: history,
        });

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
        addChatMessage(idx, {
          id: `err-${Date.now()}`,
          role: "ai",
          content:
            "Sorry, I had trouble answering that. Please try again in a moment.",
        });
      } finally {
        setLoading("chat", false);
      }
    },
    [
      currentSlideIndex,
      slides,
      slide.id,
      addChatMessage,
      getChatHistory,
      dispatch,
      hasUnlimitedAI,
      usage.aiQuestionsUsed,
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
  const goToPage = async (newIndex: number) => {
    const clampedIndex = Math.max(0, Math.min(newIndex, slides.length - 1));
    setCurrentSlideIndex(clampedIndex);
    setCurrentPage(clampedIndex + 1);

    const totalTime =
      timeSpent + Math.floor((Date.now() - startTimeRef.current) / 60000);
    if (totalTime > 0) {
      progressApi
        .updateProgress({
          slide_id: slide.id,
          current_page: clampedIndex + 1,
          total_pages: slides.length || slide.page_count,
          time_spent_minutes: totalTime,
        })
        .catch(() => {});
    }
    startTimeRef.current = Date.now();
  };

  const totalPages = slides.length || slide.page_count || 1;
  const canPrev = currentSlideIndex > 0;
  const canNext = currentSlideIndex < totalPages - 1;

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col">
      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <ReaderToolbar
        courseId={courseId}
        courseBreadcrumb={courseBreadcrumb}
        slideTitle={slide.title}
        panelOpen={panelOpen}
        onTogglePanel={() => setPanelOpen((v) => !v)}
      />

      <div className="flex flex-1 min-h-0">
        {/* ── Left: Slide Viewer ────────────────────────────────────────── */}
        <div
          className={cn(
            "flex-1 min-w-0 overflow-y-auto border-r border-border transition-[margin]",
            panelOpen ? "lg:mr-[420px]" : "",
          )}
        >
          <div className="mx-auto max-w-4xl px-6 py-10">
            <ReaderContent
              blocks={[]}
              slideContent={slideContent}
              currentPageIndex={currentSlideIndex}
              onSelect={setSelection}
              onExplain={askAboutSelection}
              fallbackTitle={slide.title}
            />

            {/* ── Page navigation ─────────────────────────────────────── */}
            <nav
              className="mt-10 flex items-center justify-between border-t border-border pt-6 text-sm"
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
          <aside className="hidden w-[420px] shrink-0 flex-col border-l border-border bg-card lg:flex h-[calc(100vh-4rem)] fixed right-0 top-[4rem]">
            <PanelTabs tab={tab} onChange={setTab} />
            <div className="flex-1 min-h-0 overflow-y-auto">
              {/* AI Chat */}
              {tab === "ai" &&
                (hasUnlimitedAI ? (
                  <AiChatPanel
                    slideIndex={currentSlideIndex}
                    isLoading={isLoading.chat}
                    onSend={sendMessage}
                  />
                ) : (
                  <div className="p-4">
                    <UpgradePrompt
                      feature="AI Tutor"
                      description="Get unlimited AI explanations, guided quizzes, and video recommendations"
                    />
                  </div>
                ))}

              {/* Resources: textbook + videos + MCQs */}
              {(tab === "textbook" || tab === "videos" || tab === "quiz") &&
                (hasPremiumAccess ? (
                  <ResourcePanel
                    slideId={slide.id}
                    slideIndex={currentSlideIndex}
                    activeTab={tab}
                    onTabChange={(t) => setTab(t as Tab)}
                    selection={selection?.text ?? null}
                  />
                ) : (
                  <div className="p-4">
                    <UpgradePrompt
                      feature="Study Resources"
                      description="Get AI-curated videos, textbook chapters, and auto-generated MCQs"
                    />
                  </div>
                ))}
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
        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        <span className="hidden sm:inline">Back</span>
      </Link>
      <span className="hidden text-xs text-muted-foreground sm:inline">/</span>
      <p className="truncate text-xs text-muted-foreground">
        <span className="text-foreground">{courseBreadcrumb}</span> ·{" "}
        {slideTitle}
      </p>
      <div className="ml-auto flex items-center gap-2">
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
}: {
  tab: Tab;
  onChange: (t: Tab) => void;
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
  ];
  return (
    <div className="flex items-center gap-1 border-b border-border px-3 py-2">
      {tabs.map((t) => {
        const active = tab === t.id;
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors",
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
