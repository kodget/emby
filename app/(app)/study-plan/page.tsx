"use client";

import { useMemo } from "react";
import { Plus, Check, Pencil, Trash2 } from "lucide-react";
import { TodayPlan } from "@/components/dashboard/today-plan";
import { ScheduleModal } from "@/components/dashboard/schedule-modal";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  openScheduleModal,
  completeScheduleItem,
  uncompleteScheduleItem,
  deleteScheduleItem,
} from "@/store/schedule-slice";
import { cn } from "@/lib/utils";

export default function StudyPlanPage() {
  const dispatch = useAppDispatch();
  const items = useAppSelector((state) => state.schedule.items);

  const groupedItems = useMemo(() => {
    return items
      .slice()
      .sort(
        (a, b) =>
          a.scheduledDate.localeCompare(b.scheduledDate) ||
          (a.scheduledTime || "").localeCompare(b.scheduledTime || ""),
      )
      .reduce<Record<string, typeof items>>((groups, item) => {
        const date = item.scheduledDate;
        if (!groups[date]) groups[date] = [];
        groups[date].push(item);
        return groups;
      }, {});
  }, [items]);

  const totalMinutes = items.reduce(
    (sum, item) => sum + item.estimatedMinutes,
    0,
  );
  const completedCount = items.filter((item) => item.completed).length;
  const today = new Date().toISOString().split("T")[0];
  const todayCount = items.filter(
    (item) => item.scheduledDate === today,
  ).length;
  const upcomingCount = items.length;

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
      <section className="rounded-3xl border border-border bg-card p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
              Study Plan
            </p>
            <h1 className="mt-2 font-serif text-3xl">
              Organize your full study schedule
            </h1>
            <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
              Build a complete plan for reading, quizzes, flashcards and
              steeplechase practice. Add activity-specific details, track
              completion and keep your day on schedule.
            </p>
          </div>
          <button
            type="button"
            onClick={() => dispatch(openScheduleModal(null))}
            className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
          >
            <Plus className="size-4" />
            Add activity
          </button>
        </div>
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
        <div className="space-y-6">
          <TodayPlan />

          <section className="rounded-3xl border border-border bg-card p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                  Full schedule
                </p>
                <h2 className="mt-2 font-serif text-2xl">
                  Upcoming activities
                </h2>
              </div>
              <p className="text-sm text-muted-foreground">
                {upcomingCount} activities · {totalMinutes} min planned ·{" "}
                {completedCount} completed
              </p>
            </div>

            <div className="mt-6 space-y-6">
              {upcomingCount === 0 ? (
                <div className="rounded-3xl border border-dashed border-border bg-muted/10 p-8 text-center text-sm text-muted-foreground">
                  No study activities have been scheduled yet. Use the button
                  above to add your first activity.
                </div>
              ) : (
                Object.entries(groupedItems).map(([date, dateItems]) => (
                  <div key={date}>
                    <h3 className="text-sm font-semibold text-foreground">
                      {new Date(date).toLocaleDateString("en-US", {
                        weekday: "long",
                        month: "short",
                        day: "numeric",
                      })}
                    </h3>
                    <ul className="mt-3 space-y-3">
                      {dateItems.map((item) => (
                        <li
                          key={item.id}
                          className="rounded-3xl border border-border bg-background p-4"
                        >
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                              <p
                                className={cn(
                                  "text-sm font-medium",
                                  item.completed
                                    ? "text-muted-foreground line-through"
                                    : "text-foreground",
                                )}
                              >
                                {item.title}
                              </p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {item.courseName}
                                {item.details ? ` · ${item.details}` : ""}
                                {item.scheduledTime
                                  ? ` · ${item.scheduledTime}`
                                  : ""}
                              </p>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <button
                                type="button"
                                onClick={() =>
                                  item.completed
                                    ? dispatch(uncompleteScheduleItem(item.id))
                                    : dispatch(completeScheduleItem(item.id))
                                }
                                className={cn(
                                  "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium transition-colors",
                                  item.completed
                                    ? "border-primary bg-primary/10 text-primary"
                                    : "border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground",
                                )}
                              >
                                <Check className="size-4" />
                                {item.completed
                                  ? "Mark incomplete"
                                  : "Mark complete"}
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  dispatch(openScheduleModal(item))
                                }
                                className="inline-flex items-center justify-center rounded-full border border-border bg-background p-2 text-muted-foreground hover:text-foreground"
                                aria-label="Edit"
                              >
                                <Pencil className="size-4" />
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  if (confirm("Delete this schedule item?")) {
                                    dispatch(deleteScheduleItem(item.id));
                                  }
                                }}
                                className="inline-flex items-center justify-center rounded-full border border-border bg-background p-2 text-muted-foreground hover:text-destructive"
                                aria-label="Delete"
                              >
                                <Trash2 className="size-4" />
                              </button>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>

        <aside className="space-y-6">
          <section className="rounded-3xl border border-border bg-card p-6">
            <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
              Quick stats
            </p>
            <div className="mt-5 space-y-4 text-sm text-foreground">
              <div className="flex items-center justify-between">
                <span>Today&apos;s activities</span>
                <strong>{todayCount}</strong>
              </div>
              <div className="flex items-center justify-between">
                <span>Total planned minutes</span>
                <strong>{totalMinutes}</strong>
              </div>
              <div className="flex items-center justify-between">
                <span>Completed</span>
                <strong>{completedCount}</strong>
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-border bg-card p-6">
            <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
              Plan tips
            </p>
            <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
              <li>
                Use activity-specific details to keep each session focused.
              </li>
              <li>
                Schedule your next quiz and flashcards review after a reading
                session.
              </li>
              <li>Open the modal to edit any activity with a single click.</li>
            </ul>
          </section>
        </aside>
      </div>

      <ScheduleModal />
    </div>
  );
}
