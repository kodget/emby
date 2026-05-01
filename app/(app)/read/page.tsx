"use client";

import Link from "next/link";
import { BookOpenText, FileText, Sparkles } from "lucide-react";
import { useAppSelector } from "@/store/hooks";
import { curriculum } from "@/lib/curriculum";
import { getSlidesForCourse } from "@/lib/slides";
import { breadcrumb } from "@/lib/curriculum";

export default function ReaderPage() {
  const recentCourses = useAppSelector((state) => state.progress.recentCourses);

  // Get recent slides from recent courses
  const recentSlides = recentCourses
    .map((courseId) => {
      const slides = getSlidesForCourse(courseId);
      return slides.map((slide) => ({
        ...slide,
        courseId,
        courseBreadcrumb: breadcrumb(courseId),
      }));
    })
    .flat()
    .slice(0, 6); // Show up to 6 recent slides

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
      {/* Subject Selection */}
      <section className="rounded-3xl border border-border bg-card p-6 text-center">
        <div className="mx-auto max-w-2xl">
          <h1 className="font-serif text-3xl leading-tight tracking-tight md:text-4xl">
            What do you want to read today?
          </h1>
          <p className="mt-4 text-muted-foreground">
            Choose a subject to explore available slides and materials.
          </p>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {curriculum.map((subject) => (
              <Link
                key={subject.id}
                href="/courses"
                className="group flex flex-col items-center gap-4 rounded-2xl border border-border bg-background p-6 transition-all hover:border-primary/40 hover:bg-primary/5 hover:-translate-y-1 hover:shadow-lg hover:shadow-primary/10"
              >
                <div
                  className="flex size-12 items-center justify-center rounded-xl text-white"
                  style={{ backgroundColor: subject.color }}
                >
                  <BookOpenText className="size-6" aria-hidden="true" />
                </div>
                <div>
                  <h3 className="font-serif text-lg font-medium">
                    {subject.title}
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {subject.blocks.length} block
                    {subject.blocks.length !== 1 ? "s" : ""}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Recent Slides */}
      {recentSlides.length > 0 && (
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

          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recentSlides.map((slide) => (
              <Link
                key={slide.id}
                href={`/read/${slide.courseId}/${slide.id}`}
                className="group flex items-center gap-4 rounded-2xl border border-border bg-card p-4 transition-all hover:border-primary/40 hover:bg-primary/5 hover:-translate-y-0.5 hover:shadow-md hover:shadow-primary/10"
              >
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary">
                  <FileText className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{slide.title}</p>
                  <p className="truncate text-sm text-muted-foreground">
                    {slide.courseBreadcrumb} · {slide.pages} pages
                  </p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Empty State */}
      {recentSlides.length === 0 && (
        <section className="mt-10 rounded-3xl border border-dashed border-border bg-muted/10 p-12 text-center">
          <div className="mx-auto max-w-md">
            <div className="flex justify-center">
              <div className="flex size-16 items-center justify-center rounded-full bg-primary/10">
                <Sparkles className="size-8 text-primary" aria-hidden="true" />
              </div>
            </div>
            <h3 className="mt-4 font-serif text-xl">Ready to start reading?</h3>
            <p className="mt-2 text-muted-foreground">
              Choose a subject above to explore available slides and materials.
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
