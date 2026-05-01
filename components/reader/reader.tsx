"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  BookOpenText,
  ChevronLeft,
  ChevronRight,
  Highlighter,
  ListChecks,
  PanelRightClose,
  PanelRightOpen,
  Play,
  Sparkles,
  X,
} from "lucide-react";
import type { Slide } from "@/lib/api";
import { progressApi, statsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ReaderContent, type SelectionPayload } from "./reader-content";
import { AiPanel, type Message, type YoutubeSuggestion } from "./ai-panel";
import {
  useSlidePages,
  useCanUpload,
  useAppDispatch,
  useAppSelector,
} from "@/store/hooks";
import { openUploadModal } from "@/store/uploads-slice";
import { incrementUsage } from "@/store/user-slice";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { UpgradePrompt } from "@/components/upgrade-prompt";

type Tab = "ai" | "textbook" | "videos" | "quiz";

export function Reader({
  courseId,
  slide,
  slideContent,
  courseBreadcrumb,
}: {
  courseId: string;
  slide: Slide;
  slideContent: any;
  courseBreadcrumb: string;
}) {
  const [panelOpen, setPanelOpen] = useState(true);
  const [tab, setTab] = useState<Tab>("ai");
  const [selection, setSelection] = useState<SelectionPayload | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [timeSpent, setTimeSpent] = useState(0);
  const startTimeRef = useRef<number>(Date.now());
  
  const safeBreadcrumb = courseBreadcrumb ?? "";
  const isAnatomy = safeBreadcrumb.toLowerCase().includes("anatomy");
  const slidePages = useSlidePages(slide.id);
  const { hasAccess, isPremium, isTrial } = useFeatureAccess();
  const usage = useAppSelector((s) => s.user.usage);
  const dispatch = useAppDispatch();
  const hasUnlimitedAI = hasAccess("unlimited_ai_explanations");
  
  // Track time spent and update progress
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = Math.floor((now - startTimeRef.current) / 60000); // minutes
      if (elapsed > 0) {
        setTimeSpent(prev => prev + elapsed);
        startTimeRef.current = now;
      }
    }, 60000); // Check every minute
    
    return () => clearInterval(interval);
  }, []);
  
  // Update progress when page changes or component unmounts
  useEffect(() => {
    return () => {
      // Save progress on unmount
      const totalTime = timeSpent + Math.floor((Date.now() - startTimeRef.current) / 60000);
      if (totalTime > 0) {
        progressApi.updateProgress({
          slide_id: slide.id,
          current_page: currentPage,
          total_pages: slide.page_count,
          time_spent_minutes: totalTime,
        }).catch(err => console.log('Progress save failed:', err));
        
        // Award points for reading
        statsApi.awardPoints(5, 'Reading slide').catch(err => console.log('Points award failed:', err));
        
        // Update streak
        statsApi.updateStreak().catch(err => console.log('Streak update failed:', err));
      }
    };
  }, [slide.id, currentPage, timeSpent]);
  
  const handlePageChange = async (newPage: number) => {
    // Save current progress
    const totalTime = timeSpent + Math.floor((Date.now() - startTimeRef.current) / 60000);
    if (totalTime > 0) {
      try {
        await progressApi.updateProgress({
          slide_id: slide.id,
          current_page: newPage,
          total_pages: slide.page_count,
          time_spent_minutes: totalTime,
        });
      } catch (error) {
        console.log('Progress update failed:', error);
      }
    }
    setCurrentPage(newPage);
    startTimeRef.current = Date.now();
  };
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "seed",
      role: "ai",
      content: isAnatomy
        ? "Hi Chioma, I&apos;m reading along with you. Whenever something feels confusing, just highlight it. I&apos;ll explain it gently using your recommended textbook, and I&apos;ll suggest a real dissection video for every anatomy topic so you can actually see it."
        : "Hi Chioma, I&apos;m reading along with you. Whenever something feels confusing, just highlight it. I&apos;ll explain it gently using your recommended textbook, and I&apos;ll point you to the single best YouTube video for what you&apos;re stuck on.",
    },
  ]);

  // Mock AI response generator keyed off highlighted phrases
  const askAboutSelection = (text: string) => {
    if (!hasUnlimitedAI && usage.aiQuestionsUsed >= 5) {
      alert(
        "You've reached your daily limit of 5 AI questions. Upgrade to premium for unlimited access!",
      );
      return;
    }
    setTab("ai");
    setPanelOpen(true);
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: `Explain: “${text.length > 140 ? text.slice(0, 140) + "…" : text}”`,
    };
    setMessages((m) => [...m, userMsg]);
    const lower = text.toLowerCase();
    const ai = generateAiAnswer(lower, isAnatomy);
    dispatch(incrementUsage("aiQuestions"));
    setTimeout(() => {
      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: "ai",
          content: ai.content,
          sources: ai.sources,
          youtube: ai.youtube,
        },
      ]);
    }, 600);
  };

  const askFreeform = (text: string) => {
    if (!hasUnlimitedAI && usage.aiQuestionsUsed >= 5) {
      alert(
        "You've reached your daily limit of 5 AI questions. Upgrade to premium for unlimited access!",
      );
      return;
    }
    if (!text.trim()) return;
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
    };
    setMessages((m) => [...m, userMsg]);
    const ai = generateAiAnswer(text.toLowerCase(), isAnatomy);
    dispatch(incrementUsage("aiQuestions"));
    setTimeout(() => {
      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: "ai",
          content: ai.content,
          sources: ai.sources,
          youtube: ai.youtube,
        },
      ]);
    }, 500);
  };

  return (
    <div className="flex min-h-[calc(100vh-4rem)] flex-col">
      <ReaderToolbar
        courseId={courseId}
        courseBreadcrumb={courseBreadcrumb}
        slideTitle={slide.title}
        panelOpen={panelOpen}
        onTogglePanel={() => setPanelOpen((v) => !v)}
      />

      <div className="flex flex-1 min-h-0">
        <div
          className={cn(
            "flex-1 min-w-0 overflow-y-auto border-r border-border transition-[padding]",
            panelOpen ? "lg:pr-0" : "",
          )}
        >
          <div className="mx-auto max-w-3xl px-6 py-10">
            <ReaderContent
              blocks={[]}
              slideContent={slideContent}
              onSelect={setSelection}
              onExplain={askAboutSelection}
              fallbackTitle={slide.title}
              slidePages={slidePages}
            />

            <ReaderPager pages={slide.pages} current={1} />
          </div>
        </div>

        {panelOpen && (
          <aside className="hidden w-[400px] shrink-0 flex-col border-l border-border bg-card lg:flex">
            <PanelTabs tab={tab} onChange={setTab} />
            <div className="flex-1 min-h-0 overflow-y-auto">
              {tab === "ai" &&
                (hasUnlimitedAI ? (
                  <AiPanel
                    messages={messages}
                    onAsk={askFreeform}
                    quickActions={[
                      {
                        label: "Summarise this page",
                        prompt: "Summarise this page in 5 bullets.",
                      },
                      {
                        label: "Generate 3 MCQs",
                        prompt: "Generate 3 MCQs with answers from this page.",
                      },
                      {
                        label: "Explain like I'm a 1st year",
                        prompt: "Explain this page in very simple terms.",
                      },
                    ]}
                  />
                ) : (
                  <div className="p-4">
                    <UpgradePrompt
                      feature="AI Tutor"
                      description="Get unlimited AI explanations, guided quizzes, and video recommendations"
                    />
                  </div>
                ))}
              {tab === "textbook" && <TextbookPanel />}
              {tab === "videos" && (
                <VideosPanel
                  selection={selection?.text ?? null}
                  isAnatomy={isAnatomy}
                />
              )}
              {tab === "quiz" && <QuizPanel />}
            </div>
          </aside>
        )}
      </div>

      {/* Floating selection popover */}
      {selection && (
        <SelectionFab
          selection={selection}
          onExplain={() => askAboutSelection(selection.text)}
          onClose={() => setSelection(null)}
          onVideo={() => {
            setTab("videos");
            setPanelOpen(true);
          }}
          onQuiz={() => {
            // Trigger past questions quiz for current topic
            // TODO: fetch from /pastquestions/questions/{block_id}/{topic}
            setTab("quiz");
            setPanelOpen(true);
          }}
        />
      )}
    </div>
  );
}

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
  const canUpload = useCanUpload();
  const dispatch = useAppDispatch();
  return (
    <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-border bg-background/90 px-4 py-2.5 backdrop-blur-md sm:px-6">
      <Link
        href={`/courses/${courseId}`}
        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        <span className="hidden sm:inline">Back</span>
      </Link>
      <span className="hidden text-xs text-muted-foreground sm:inline">/</span>
      <p className="truncate text-xs text-muted-foreground">
        <span className="text-foreground">{courseBreadcrumb}</span> ·{" "}
        {slideTitle}
      </p>
      <div className="ml-auto flex items-center gap-2">
        {canUpload && (
          <button
            type="button"
            onClick={() =>
              dispatch(openUploadModal({ courseId, moduleId: courseId }))
            }
            className="hidden items-center gap-1.5 rounded-full border border-dashed border-primary/50 bg-primary/5 px-3 py-1.5 text-[11px] font-medium text-primary hover:bg-primary/10 transition-colors md:inline-flex"
          >
            <BookOpenText className="size-3.5" aria-hidden="true" />
            Upload slides / past questions
          </button>
        )}
        <span className="hidden items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-medium text-primary md:inline-flex">
          <Sparkles className="size-3.5" aria-hidden="true" />
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
            <PanelRightClose className="size-4" aria-hidden="true" />
          ) : (
            <PanelRightOpen className="size-4" aria-hidden="true" />
          )}
        </button>
      </div>
    </div>
  );
}

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
    { id: "textbook", label: "Textbook", icon: BookOpenText },
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
            <t.icon className="size-3.5" aria-hidden="true" />
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

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
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Position near selection rect
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
        <Sparkles className="size-3.5" aria-hidden="true" />
        Explain
      </button>
      <button
        onClick={onVideo}
        className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium text-foreground hover:bg-muted"
      >
        <Play className="size-3.5" aria-hidden="true" />
        Find video
      </button>
      <button
        onClick={onQuiz}
        className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium text-foreground hover:bg-muted"
      >
        <ListChecks className="size-3.5" aria-hidden="true" />
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
        <X className="size-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

function ReaderPager({ pages, current }: { pages: number; current: number }) {
  return (
    <nav
      className="mt-16 flex items-center justify-between border-t border-border pt-6 text-sm"
      aria-label="Page"
    >
      <button
        type="button"
        className="inline-flex h-10 items-center gap-1.5 rounded-full border border-border bg-card px-4 text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" aria-hidden="true" />
        Previous
      </button>
      <p className="text-muted-foreground">
        Page <span className="font-medium text-foreground">{current}</span> of{" "}
        {pages}
      </p>
      <button
        type="button"
        className="inline-flex h-10 items-center gap-1.5 rounded-full bg-primary px-4 text-primary-foreground hover:opacity-90"
      >
        Next
        <ChevronRight className="size-4" aria-hidden="true" />
      </button>
    </nav>
  );
}

function PremiumPromo() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-primary/10 text-primary">
        <Sparkles className="size-6" aria-hidden="true" />
      </div>
      <div>
        <h2 className="text-xl font-semibold">Premium tutor locked</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The Emby AI tutor, guided quizzes, and video recommendations are
          included with Emby Premium. Upgrade to get instant explanations, study
          prompts, and deeper slide support.
        </p>
      </div>
      <Link
        href="/premium"
        className="inline-flex items-center justify-center rounded-2xl bg-primary px-5 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        View premium plans
      </Link>
    </div>
  );
}

function TextbookPanel() {
  return (
    <div className="p-5">
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-background p-3">
        <div className="flex size-14 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <BookOpenText className="size-5" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
            Recommended textbook
          </p>
          <p className="font-serif text-base leading-tight">
            Moore&apos;s Clinically Oriented Anatomy, 9e
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            Chapter 3, Upper Limb
          </p>
        </div>
      </div>

      <article className="mt-5 space-y-3 text-sm leading-relaxed">
        <h3 className="font-serif text-lg">Axilla (Armpit)</h3>
        <p className="text-muted-foreground">
          The axilla is the pyramidal space between the thoracic wall and upper
          limb. Its shape and size vary with the position of the limb. It has an
          apex, a base, and four walls, three of which are muscular.
        </p>
        <p className="text-muted-foreground">
          The axilla provides passage for structures serving the upper limb. The
          axillary sheath is a tubular sleeve of areolar tissue that encloses
          the axillary vessels and brachial plexus…
        </p>
        <p className="italic text-muted-foreground">Page 726, Figure 3.40</p>
      </article>
    </div>
  );
}

function VideosPanel({
  selection,
  isAnatomy,
}: {
  selection: string | null;
  isAnatomy: boolean;
}) {
  const anatomyVideos = [
    {
      title: "Axilla: Boundaries & Contents (Acland's Video Atlas)",
      channel: "Acland's Anatomy",
      length: "6:42",
      dissection: true,
    },
    {
      title: "Long Thoracic Nerve, Real Cadaver Dissection",
      channel: "Kenhub",
      length: "4:12",
      dissection: true,
    },
    {
      title: "Brachial Plexus in 10 Minutes",
      channel: "Armando Hasudungan",
      length: "10:15",
      dissection: false,
    },
  ];

  const generalVideos = [
    {
      title: "Glycolysis, Step by Step with Enzymes",
      channel: "Ninja Nerd",
      length: "18:24",
      dissection: false,
    },
    {
      title: "PFK-1 Regulation in 5 Minutes",
      channel: "Osmosis",
      length: "5:02",
      dissection: false,
    },
    {
      title: "Net ATP Yield, Glycolysis vs Krebs",
      channel: "Armando Hasudungan",
      length: "7:48",
      dissection: false,
    },
  ];

  const videos = isAnatomy ? anatomyVideos : generalVideos;

  return (
    <div className="p-5">
      <p className="text-[11px] font-medium uppercase tracking-widest text-accent">
        Tailored videos
      </p>
      <h3 className="mt-1 font-serif text-xl">
        {selection ? "Based on your highlight" : "For this page"}
      </h3>
      {selection && (
        <p className="mt-1 line-clamp-2 text-[12px] italic text-muted-foreground">
          “{selection}”
        </p>
      )}

      <ul className="mt-4 space-y-3">
        {videos.map((v) => (
          <li key={v.title}>
            <button
              type="button"
              className="flex w-full gap-3 rounded-2xl border border-border bg-background p-3 text-left hover:border-primary/40"
            >
              <div className="relative flex size-20 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <Play className="size-5" aria-hidden="true" />
                <span className="absolute bottom-1 right-1 rounded bg-foreground/80 px-1 py-0.5 text-[10px] font-medium text-background">
                  {v.length}
                </span>
              </div>
              <div className="min-w-0">
                <p className="line-clamp-2 text-sm font-medium">{v.title}</p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  {v.channel}
                </p>
                {v.dissection && (
                  <span className="mt-1.5 inline-flex rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-medium text-accent">
                    Real dissection
                  </span>
                )}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function QuizPanel() {
  return (
    <div className="p-5">
      <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
        Generated from this page
      </p>
      <h3 className="mt-1 font-serif text-xl">Quiz yourself in 60 seconds</h3>

      <ol className="mt-4 space-y-4 text-sm">
        <li className="rounded-2xl border border-border bg-background p-4">
          <p className="font-medium">
            1. Which structure forms the lateral wall of the axilla?
          </p>
          <ul className="mt-2 space-y-1.5 text-muted-foreground">
            {[
              "Pectoralis major",
              "Serratus anterior",
              "Intertubercular groove of humerus",
              "Latissimus dorsi",
            ].map((opt, i) => (
              <li
                key={i}
                className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 hover:border-primary"
              >
                <span className="size-5 shrink-0 rounded-full border border-border text-[10px] leading-[1.2rem] text-center font-semibold text-foreground">
                  {String.fromCharCode(65 + i)}
                </span>
                {opt}
              </li>
            ))}
          </ul>
        </li>
        <li className="rounded-2xl border border-border bg-background p-4">
          <p className="font-medium">
            2. Injury to the long thoracic nerve causes:
          </p>
          <ul className="mt-2 space-y-1.5 text-muted-foreground">
            {["Wrist drop", "Claw hand", "Winged scapula", "Erb's palsy"].map(
              (opt, i) => (
                <li
                  key={i}
                  className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 hover:border-primary"
                >
                  <span className="size-5 shrink-0 rounded-full border border-border text-[10px] leading-[1.2rem] text-center font-semibold text-foreground">
                    {String.fromCharCode(65 + i)}
                  </span>
                  {opt}
                </li>
              ),
            )}
          </ul>
        </li>
      </ol>

      <Link
        href="/quiz/axilla-mcq"
        className="mt-5 inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-full bg-primary text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        <Highlighter className="size-4" aria-hidden="true" />
        Take the full 5-question quiz
      </Link>
    </div>
  );
}

// ---------------- Mock AI ----------------

function generateAiAnswer(
  input: string,
  isAnatomy: boolean,
): { content: string; sources?: string[]; youtube?: YoutubeSuggestion } {
  if (/long thoracic|serratus|winged scapula|winging/.test(input)) {
    return {
      content:
        "Totally normal to get tangled up here, this one catches almost everyone the first time.\n\nThe long thoracic nerve (C5, C6, C7) runs down on the medial wall of the axilla, lying superficially on serratus anterior, which it supplies. Because it sits so superficially, it&apos;s vulnerable in axillary surgery (classically radical mastectomy) and can even be stretched by a heavy backpack. When it&apos;s injured, serratus anterior is paralysed, so the scapula can&apos;t be held against the chest wall. The medial border lifts off when the patient pushes against a wall, and that&apos;s what we call winging of the scapula.",
      sources: [
        "Moore's Clinically Oriented Anatomy, 9e · p. 748",
        "Gray's Anatomy for Students, 4e · p. 692",
      ],
      youtube: {
        title:
          "Long Thoracic Nerve and Winged Scapula, Real Cadaver Dissection",
        channel: "Kenhub",
        length: "4:12",
        isDissection: true,
      },
    };
  }
  if (/axilla|axillary|boundaries|wall/.test(input)) {
    return {
      content:
        "Take a breath, this one looks messy but it&apos;s actually quite organised once you see it.\n\nThe axilla is a pyramidal space with four walls:\n• Anterior: pec major, pec minor, subclavius\n• Posterior: subscapularis, teres major, latissimus dorsi\n• Medial: serratus anterior plus the upper ribs\n• Lateral: the intertubercular (bicipital) groove of the humerus\n\nApex is the cervico-axillary canal. Base is the axillary fascia and skin. Contents: axillary artery and vein, brachial plexus cords and branches, lymph nodes, and fat.",
      sources: ["Moore's Clinically Oriented Anatomy, 9e · p. 726"],
      youtube: {
        title: "Axilla: Boundaries & Contents (Acland's Video Atlas)",
        channel: "Acland's Anatomy",
        length: "6:42",
        isDissection: true,
      },
    };
  }
  if (/brachial plexus|cord|trunk|root/.test(input)) {
    return {
      content:
        "Don&apos;t worry, everyone finds the plexus scary at first. It clicks once you see it drawn the same way a few times.\n\nIt&apos;s formed from the ventral rami of C5 to T1. The little mnemonic that most of your seniors used is: Randy Travis Drinks Cold Beer, for Roots, Trunks, Divisions, Cords, Branches. In the axilla, the cords (lateral, medial, posterior) are named by how they sit around the axillary artery, and they give rise to the terminal branches: musculocutaneous, median, ulnar, radial, and axillary.",
      sources: ["Moore's 9e · p. 744"],
      youtube: {
        title: "Brachial Plexus, Real Cadaver Dissection (Step by Step)",
        channel: "Acland's Anatomy",
        length: "8:05",
        isDissection: true,
      },
    };
  }
  if (/hand|thenar|hypothenar|intrinsic/.test(input)) {
    return {
      content:
        "You&apos;re not alone in finding the hand tricky, it has a lot of small muscles in a tiny space.\n\nThe thenar eminence (the bump at the base of your thumb) is made of abductor pollicis brevis, flexor pollicis brevis, and opponens pollicis, all supplied by the recurrent branch of the median nerve. The hypothenar eminence mirrors this on the little-finger side, supplied by the ulnar nerve. Almost every other intrinsic muscle of the hand is ulnar, which is why ulnar nerve injury gives the classic claw hand appearance.",
      sources: ["Moore's 9e · p. 780"],
      youtube: {
        title: "Intrinsic Muscles of the Hand, Cadaveric Dissection",
        channel: "Kenhub",
        length: "7:20",
        isDissection: true,
      },
    };
  }
  if (/glycolysis|pfk|phosphofructokinase|hexokinase/.test(input)) {
    return {
      content:
        "This is one of those topics that feels huge until you pin down the three regulated enzymes, then it gets a lot friendlier.\n\nPFK-1 is the rate-limiting enzyme of glycolysis. It&apos;s switched on by AMP and fructose-2,6-bisphosphate (think: the cell is low on energy, run glycolysis), and switched off by ATP and citrate (think: the cell already has plenty of energy). Net yield per glucose is 2 ATP and 2 NADH. The other regulated enzymes to remember are hexokinase/glucokinase at the start, and pyruvate kinase at the end.",
      sources: ["Lippincott Illustrated Reviews: Biochemistry, 8e · Ch. 8"],
      youtube: {
        title: "Glycolysis Explained Simply (with PFK-1 Regulation)",
        channel: "Ninja Nerd",
        length: "18:24",
        isDissection: false,
      },
    };
  }
  if (/cardiac cycle|wiggers|isovolumetric|ventricle/.test(input)) {
    return {
      content:
        "Cardiac cycle is honestly one of the prettier topics once the Wiggers diagram clicks. Let&apos;s ease into it.\n\nDuring isovolumetric contraction, every valve is closed. The ventricles squeeze harder and harder without changing volume, so only the pressure rises. The moment ventricular pressure exceeds aortic (or pulmonary) pressure, the semilunar valves open and ejection begins. That little closed-valve phase is why the pressure curve shoots up almost vertically on the Wiggers diagram.",
      sources: ["Guyton & Hall Physiology, 14e · Ch. 9"],
      youtube: {
        title: "Cardiac Cycle and Wiggers Diagram Explained Clearly",
        channel: "Armando Hasudungan",
        length: "12:08",
        isDissection: false,
      },
    };
  }

  // Default, warm fallback
  return {
    content:
      "Good question, and honestly a very fair one to ask. Based on this page, here&apos;s the short version: focus first on the spatial relationships (what sits where), then on the clinical correlations (what breaks when something is damaged). Want me to quiz you on this exact concept, or explain it in even simpler words?",
    sources: ["This page · Module 1"],
    youtube: isAnatomy
      ? {
          title: "Upper Limb Overview, Cadaveric Walkthrough",
          channel: "Acland's Anatomy",
          length: "9:30",
          isDissection: true,
        }
      : {
          title: "How to Study Medical Concepts That Feel Overwhelming",
          channel: "Ninja Nerd",
          length: "6:45",
          isDissection: false,
        },
  };
}
