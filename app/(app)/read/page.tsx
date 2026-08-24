"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpenText, FileText, Sparkles, Loader2, Clock } from "lucide-react";
import {
  curriculumApi,
  progressApi,
  type Subject,
  type UserProgress,
  type Slide,
} from "@/lib/api";

type RecentSlide = {
  slide: Slide;
  progress: UserProgress;
  readUrl: string;
};

export default function ReaderPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [recentSlides, setRecentSlides] = useState<RecentSlide[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        // Fetch subjects and recent progress in parallel
        const [subjectsData, recentProgress] = await Promise.all([
          curriculumApi.getSubjects(),
          progressApi.getRecentProgress().catch(() => [] as UserProgress[]),
        ]);

        setSubjects(subjectsData);

        // Build last 3 opened slides with their full slide data
        if (recentProgress.length > 0) {
          const top3 = recentProgress.slice(0, 3);
          const slideDetails = await Promise.all(
            top3.map((p) => curriculumApi.getSlide(p.slide).catch(() => null)),
          );

          const items: RecentSlide[] = [];
          for (let i = 0; i < top3.length; i++) {
            const slide = slideDetails[i];
            if (!slide) continue;
            const courseId = slide.block || slide.subject || slide.id;
            items.push({
              slide,
              progress: top3[i],
              readUrl: `/read/${courseId}/${slide.id}`,
            });
          }
          setRecentSlides(items);
        }
      } catch (err) {
        console.error("Failed to load read page data:", err);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  // Subject color palette — cycles if more subjects than colors
  const colors = [
    {
      bg: "bg-rose-500/10",
      border: "border-rose-200 dark:border-rose-900",
      icon: "bg-rose-500",
      text: "text-rose-600 dark:text-rose-400",
    },
    {
      bg: "bg-blue-500/10",
      border: "border-blue-200 dark:border-blue-900",
      icon: "bg-blue-500",
      text: "text-blue-600 dark:text-blue-400",
    },
    {
      bg: "bg-emerald-500/10",
      border: "border-emerald-200 dark:border-emerald-900",
      icon: "bg-emerald-500",
      text: "text-emerald-600 dark:text-emerald-400",
    },
    {
      bg: "bg-violet-500/10",
      border: "border-violet-200 dark:border-violet-900",
      icon: "bg-violet-500",
      text: "text-violet-600 dark:text-violet-400",
    },
    {
      bg: "bg-orange-500/10",
      border: "border-orange-200 dark:border-orange-900",
      icon: "bg-orange-500",
      text: "text-orange-600 dark:text-orange-400",
    },
    {
      bg: "bg-cyan-500/10",
      border: "border-cyan-200 dark:border-cyan-900",
      icon: "bg-cyan-500",
      text: "text-cyan-600 dark:text-cyan-400",
    },
  ];

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
      {/* Subject Selection */}
      <section className="rounded-3xl border border-border bg-card p-6 text-center">
        <div className="mx-auto max-w-2xl">
          <h1 className="font-serif text-3xl leading-tight tracking-tight md:text-4xl">
            What do you want to read today?
          </h1>
          <p className="mt-3 text-muted-foreground">
            Choose a subject to explore available slides and materials.
          </p>

          {loading ? (
            <div className="mt-8 flex items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" />
              <span className="text-sm">Loading subjects…</span>
            </div>
          ) : subjects.length === 0 ? (
            <div className="mt-8 rounded-2xl border border-dashed border-border bg-muted/20 p-8 text-center">
              <p className="text-sm text-muted-foreground">
                No subjects available yet. Your class head needs to set up the
                curriculum.
              </p>
            </div>
          ) : (
            <div
              className={`mt-8 grid gap-4 ${subjects.length === 1 ? "sm:grid-cols-1 max-w-xs mx-auto" : subjects.length === 2 ? "sm:grid-cols-2" : "sm:grid-cols-3"}`}
            >
              {subjects.map((subject, i) => {
                const c = colors[i % colors.length];
                return (
                  <Link
                    key={subject.id}
                    href={`/courses?subject=${subject.id}`}
                    className={`group flex flex-col items-center gap-4 rounded-2xl border ${c.border} ${c.bg} p-6 transition-all hover:-translate-y-1 hover:shadow-lg`}
                  >
                    <div
                      className={`flex size-12 items-center justify-center rounded-xl ${c.icon} text-white`}
                    >
                      <BookOpenText className="size-6" aria-hidden="true" />
                    </div>
                    <div>
                      <h3
                        className={`font-serif text-lg font-medium ${c.text}`}
                      >
                        {subject.name}
                      </h3>
                      {subject.description && (
                        <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                          {subject.description}
                        </p>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* Recently Opened Slides */}
      {!loading && recentSlides.length > 0 && (
        <section className="mt-10" aria-labelledby="recent-heading">
          <div className="flex items-center justify-between">
            <h2 id="recent-heading" className="font-serif text-2xl">
              Recently opened
            </h2>
            <Link
              href="/courses"
              className="text-sm text-primary hover:underline"
            >
              View all courses →
            </Link>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            {recentSlides.map(({ slide, progress, readUrl }) => (
              <Link
                key={slide.id}
                href={readUrl}
                className="group flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 transition-all hover:border-primary/40 hover:bg-primary/5 hover:-translate-y-0.5 hover:shadow-md hover:shadow-primary/10"
              >
                <div className="flex items-start gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <FileText className="size-4" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{slide.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {slide.subject_name || slide.block_name || ""}
                    </p>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="size-3" />
                      Page {progress.current_page} of{" "}
                      {progress.total_pages || slide.page_count}
                    </span>
                    <span className="font-medium text-primary">
                      {progress.progress_percentage}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${progress.progress_percentage}%` }}
                    />
                  </div>
                </div>

                <span className="text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                  Continue reading →
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Empty state — no recent slides */}
      {!loading && recentSlides.length === 0 && (
        <section className="mt-10 rounded-3xl border border-dashed border-border bg-muted/10 p-12 text-center">
          <div className="mx-auto max-w-md">
            <div className="flex justify-center">
              <div className="flex size-16 items-center justify-center rounded-full bg-primary/10">
                <Sparkles className="size-8 text-primary" aria-hidden="true" />
              </div>
            </div>
            <h3 className="mt-4 font-serif text-xl">Ready to start reading?</h3>
            <p className="mt-2 text-muted-foreground">
              Pick a subject above to explore slides from your class.
            </p>
            <Link
              href="/courses"
              className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              <BookOpenText className="size-4" aria-hidden="true" />
              Browse all courses
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}
