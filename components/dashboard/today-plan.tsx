"use client";

import { useMemo, useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  BookOpenText,
  Check,
  Layers,
  ListChecks,
  Trophy,
  Plus,
  Pencil,
  Trash2,
} from "lucide-react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  openScheduleModal,
} from "@/store/schedule-slice";
import { scheduleApi, type ScheduleItem as ApiScheduleItem } from "@/lib/api";
import { cn } from "@/lib/utils";

const iconFor = {
  read: BookOpenText,
  quiz: ListChecks,
  flashcards: Layers,
  steeplechase: Trophy,
} as const;

const hrefFor = {
  read: "/read",
  quiz: "/quiz/axilla-mcq",
  flashcards: "/flashcards",
  steeplechase: "/steeplechase",
} as const;

export function TodayPlan() {
  const dispatch = useAppDispatch();
  const [items, setItems] = useState<ApiScheduleItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch today's schedule from backend
  useEffect(() => {
    async function fetchSchedule() {
      try {
        const todayItems = await scheduleApi.getTodaySchedule();
        setItems(todayItems);
      } catch (error) {
        console.error('Error fetching schedule:', error);
      } finally {
        setLoading(false);
      }
    }
    
    fetchSchedule();
  }, []);

  const { done, total, minutesLeft } = useMemo(() => {
    const done = items.filter((i) => i.completed).length;
    const minutesLeft = items
      .filter((i) => !i.completed)
      .reduce((s, i) => s + i.estimated_minutes, 0);
    return { done, total: items.length, minutesLeft };
  }, [items]);

  const percent = total > 0 ? Math.round((done / total) * 100) : 0;

  const handleComplete = async (item: ApiScheduleItem) => {
    try {
      if (item.completed) {
        await scheduleApi.uncompleteScheduleItem(item.id);
      } else {
        await scheduleApi.completeScheduleItem(item.id);
      }
      // Refresh schedule
      const todayItems = await scheduleApi.getTodaySchedule();
      setItems(todayItems);
    } catch (error) {
      console.error('Error updating schedule item:', error);
    }
  };

  const handleDelete = async (id: number) => {
    if (confirm("Delete this schedule item?")) {
      try {
        await scheduleApi.deleteScheduleItem(id);
        // Refresh schedule
        const todayItems = await scheduleApi.getTodaySchedule();
        setItems(todayItems);
      } catch (error) {
        console.error('Error deleting schedule item:', error);
      }
    }
  };

  if (loading) {
    return (
      <section
        id="today"
        className="rounded-3xl border border-border bg-card p-6"
        aria-labelledby="today-plan-heading"
      >
        <div className="flex items-center justify-center py-8">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-solid border-primary border-r-transparent"></div>
        </div>
      </section>
    );
  }

  return (
    <section
      id="today"
      className="rounded-3xl border border-border bg-card p-6"
      aria-labelledby="today-plan-heading"
    >
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
            Today ·{" "}
            {new Date().toLocaleDateString("en-US", { weekday: "long" })}
          </p>
          <h2 id="today-plan-heading" className="mt-1 font-serif text-2xl">
            Your{" "}
            {minutesLeft +
              (done > 0
                ? todayItems
                    .filter((i) => i.completed)
                    .reduce((s, i) => s + i.estimatedMinutes, 0)
                : 0)}
            -minute plan
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-[11px] uppercase tracking-widest text-muted-foreground">
              Remaining
            </p>
            <p className="font-serif text-2xl">{minutesLeft} min</p>
          </div>
          <button
            type="button"
            onClick={() => dispatch(openScheduleModal(null))}
            className="flex size-9 items-center justify-center rounded-full bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
            aria-label="Add to schedule"
          >
            <Plus className="size-4" />
          </button>
        </div>
      </header>

      <div className="mt-4 flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${percent}%` }}
            aria-hidden="true"
          />
        </div>
        <span className="text-xs text-muted-foreground">
          {done} / {total}
        </span>
      </div>

      <ul className="mt-5 divide-y divide-border">
        {items.length === 0 ? (
          <li className="py-8 text-center">
            <p className="text-sm text-muted-foreground">
              No activities scheduled for today.
            </p>
            <button
              type="button"
              onClick={() => dispatch(openScheduleModal(null))}
              className="mt-3 inline-flex items-center gap-2 rounded-full border border-dashed border-primary/50 bg-primary/5 px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"
            >
              <Plus className="size-4" />
              Add your first activity
            </button>
          </li>
        ) : (
          items.map((item) => {
            const Icon = iconFor[item.activity_type];
            const href =
              item.activity_type === "read" && item.slide
                ? `/read/${item.topic || item.block}/${item.slide}`
                : hrefFor[item.activity_type];

            return (
              <li key={item.id} className="group flex items-center gap-4 py-3">
                <button
                  type="button"
                  onClick={() => handleComplete(item)}
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full border transition-all duration-200",
                    item.completed
                      ? "border-primary bg-primary text-primary-foreground scale-110 shadow-md shadow-primary/30"
                      : "border-border bg-background hover:border-primary/50 hover:scale-105",
                  )}
                  aria-label={
                    item.completed ? "Mark as incomplete" : "Mark as complete"
                  }
                  aria-pressed={item.completed}
                >
                  <AnimatePresence>
                    {item.completed && (
                      <motion.span
                        key="check"
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0, opacity: 0 }}
                        transition={{
                          type: "spring",
                          stiffness: 500,
                          damping: 25,
                        }}
                      >
                        <Check className="size-3.5" aria-hidden="true" />
                      </motion.span>
                    )}
                  </AnimatePresence>
                </button>

                <span
                  className={cn(
                    "flex size-9 shrink-0 items-center justify-center rounded-lg",
                    item.completed
                      ? "bg-muted text-muted-foreground"
                      : "bg-primary/10 text-primary",
                  )}
                >
                  <Icon className="size-4" aria-hidden="true" />
                </span>

                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      "truncate text-sm font-medium",
                      item.completed &&
                        "text-muted-foreground line-through decoration-muted-foreground/50",
                    )}
                  >
                    {item.title}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {item.topic_name || item.block_name || 'Course'} · {item.estimated_minutes} min
                    {item.scheduled_time && ` · ${item.scheduled_time}`}
                  </p>
                </div>

                {/* Action buttons */}
                <div className="flex shrink-0 items-center gap-2">
                  {!item.completed && (
                    <Link
                      href={href}
                      className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-primary hover:text-primary-foreground hover:border-primary"
                    >
                      Start
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={() => dispatch(openScheduleModal(null))} // TODO: Pass item for editing
                    className="opacity-0 group-hover:opacity-100 flex size-8 items-center justify-center rounded-full border border-border bg-background text-muted-foreground hover:text-foreground transition-opacity"
                    aria-label="Edit"
                  >
                    <Pencil className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(item.id)}
                    className="opacity-0 group-hover:opacity-100 flex size-8 items-center justify-center rounded-full border border-border bg-background text-muted-foreground hover:text-destructive transition-opacity"
                    aria-label="Delete"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </li>
            );
          })
        )}
      </ul>
    </section>
  );
}
