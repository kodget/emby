"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, BookOpen, Loader2 } from "lucide-react";
import { curriculumApi, progressApi } from "@/lib/api";
import type { Subject, UserProgress } from "@/lib/api";

export function CoursesProgress() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [progress, setProgress] = useState<UserProgress[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [subjectsData, progressData] = await Promise.all([
        curriculumApi.getSubjects(),
        progressApi.getProgress().catch(() => []),
      ]);
      setSubjects(subjectsData);
      setProgress(progressData);
    } catch (error) {
      console.error("Failed to load courses:", error);
    } finally {
      setLoading(false);
    }
  };

  // Calculate progress for each subject
  const getSubjectProgress = (subjectId: string) => {
    const subjectProgress = progress.filter((p) => {
      // This would need to be enhanced based on your data structure
      // For now, we'll return a basic calculation
      return true;
    });

    if (subjectProgress.length === 0) return 0;

    const totalProgress = subjectProgress.reduce(
      (sum, p) => sum + p.progress_percentage,
      0
    );
    return Math.round(totalProgress / subjectProgress.length);
  };

  if (loading) {
    return (
      <section
        className="rounded-3xl border border-border bg-card p-6"
        aria-labelledby="courses-heading"
      >
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </section>
    );
  }

  return (
    <section
      className="rounded-3xl border border-border bg-card p-6"
      aria-labelledby="courses-heading"
    >
      <header className="flex items-end justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
            My Courses
          </p>
          <h2 id="courses-heading" className="mt-1 font-serif text-2xl">
            {subjects.length > 0 ? "Pick up where you stopped" : "No courses available yet"}
          </h2>
        </div>
        {subjects.length > 0 && (
          <Link
            href="/courses"
            className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            All courses <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        )}
      </header>

      {subjects.length === 0 ? (
        <div className="mt-6 text-center py-8">
          <BookOpen className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
          <p className="text-sm text-muted-foreground mb-4">
            Course materials will appear here once they're uploaded
          </p>
          <Link
            href="/materials"
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            Browse Materials
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      ) : (
        <ul className="mt-5 grid gap-3 sm:grid-cols-2">
          {subjects.slice(0, 4).map((subject) => {
            const subjectProgress = getSubjectProgress(subject.id);
            return (
              <li key={subject.id}>
                <Link
                  href={`/courses`}
                  className="group flex flex-col gap-3 rounded-2xl border border-border bg-background p-4 transition-colors hover:border-primary/30"
                >
                  <div className="flex items-start gap-3">
                    <span
                      className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
                      aria-hidden="true"
                    >
                      <BookOpen className="size-5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                        {subject.name}
                      </p>
                      <h3 className="mt-0.5 truncate font-serif text-lg leading-tight group-hover:text-primary">
                        {subject.description || subject.name}
                      </h3>
                    </div>
                  </div>
                  <div className="mt-auto">
                    <div className="flex items-baseline justify-between text-xs text-muted-foreground">
                      <span>{subjectProgress}% complete</span>
                      <span>Continue learning</span>
                    </div>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${subjectProgress}%` }}
                        aria-hidden="true"
                      />
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
