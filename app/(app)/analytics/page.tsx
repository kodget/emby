"use client";

/**
 * Analytics.
 *
 * The previous version drew hardcoded charts: a fixed Mon–Sun study bar chart, invented
 * subject progress, a made-up four-week streak history, and a green "trending up" arrow
 * on every card regardless of what had actually happened. All of it is gone.
 *
 * Every number here comes from `/api/learning/analytics/`, computed from recorded
 * activity. Where the evidence is too thin to answer a question — fewer than ten
 * answered items in a period, no tracked topics yet — the page says so instead of
 * drawing a confident-looking zero.
 *
 * The page is organised around the questions a student actually asks:
 * am I improving, what am I weak at, how consistent am I, and where did it happen.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Crown } from "lucide-react";

import AuthGuard from "@/components/auth/auth-guard";
import { Axo, AxoEmpty, AxoLoader } from "@/components/brand/axo";
import { Icon3D } from "@/components/brand/icon-3d";
import { StatTile, SurfaceSkeleton } from "@/components/ui/surface";
import { analyticsApi, type AnalyticsReport } from "@/lib/api";
import { cn } from "@/lib/utils";

const WINDOWS = [7, 30, 90] as const;

export default function AnalyticsPage() {
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [days, setDays] = useState<number>(30);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    analyticsApi.getReport(days).then(data => { if (!cancelled) setReport(data); })
      .catch(() => { if (!cancelled) setFailed(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, reload]);

  return (
    <AuthGuard>
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
        <header className="flex items-start gap-4">
          <Icon3D name="analytics" size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">
              Your progress
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Built from what you have actually studied — nothing here is illustrative.
            </p>
          </div>
          <Axo pose="teaching" size="md" float className="hidden sm:block" />
        </header>

        {/* Period */}
        <div className="mt-5 flex gap-2" role="group" aria-label="Time period">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              onClick={() => setDays(w)}
              aria-pressed={days === w}
              className={cn(
                "press rounded-full border px-4 py-1.5 text-sm transition-colors",
                days === w
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-border bg-card hover:border-primary/40",
              )}
            >
              {w} days
            </button>
          ))}
        </div>

        {loading ? (
          <div className="mt-6 space-y-4">
            <SurfaceSkeleton lines={2} />
            <SurfaceSkeleton lines={4} />
          </div>
        ) : failed || !report ? (
          <AxoEmpty
            title="Couldn't load your analytics"
            description="Check your connection and try again."
            pose="oops"
            action={
              <button
                type="button"
                onClick={() => setReload(value => value + 1)}
                className="press rounded-full bg-primary px-5 py-2 text-sm font-medium text-primary-foreground"
              >
                Retry
              </button>
            }
          />
        ) : (
          <>
            {!report.overview.has_data && <AxoEmpty className="mt-4" title="Not enough activity yet"
              description="Your recorded study time and scored answers will appear here as you study."
              pose="sleeping" />}
            <Report report={report} />
          </>
        )}
      </div>
    </AuthGuard>
  );
}

function Report({ report }: { report: AnalyticsReport }) {
  const { overview, improvement, consistency } = report;
  const pct = (v: number | null | undefined) =>
    v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`;

  return (
    <div className="mt-6 space-y-6">
      {report.evidence && <div className="rounded border p-3 text-sm text-muted-foreground">
        <p>{report.evidence.note}</p>
        <p>{report.evidence.historical_assessments_excluded} historical assessments excluded; {report.evidence.assessments_awaiting_written_grades} assessments awaiting written grades.</p>
        {!!report.evidence.historical_image_rounds_excluded_from_accuracy && <p>
          {report.evidence.historical_image_rounds_excluded_from_accuracy} historical image-practice rounds count toward activity, but their scores cannot be verified against saved questions.
        </p>}
      </div>}
      {/* Headline */}
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <StatTile
          label="Accuracy"
          value={pct(overview.accuracy)}
          hint={`${overview.correct} of ${overview.attempted}`}
          tone="primary"
          icon={<Icon3D name="target" size="sm" />}
        />
        <StatTile
          label="Scored items"
          value={overview.attempted.toLocaleString()}
          hint={`${overview.sessions} sessions`}
          icon={<Icon3D name="quiz" size="sm" />}
        />
        <StatTile
          label="Study time"
          value={`${Math.round(overview.study_minutes)} min`}
          icon={<Icon3D name="planner" size="sm" />}
        />
        <StatTile
          label="Active days"
          value={`${consistency.active_days}/${consistency.window_days}`}
          hint={`${consistency.current_streak}-day streak`}
          tone={consistency.active_rate >= 0.5 ? "mastery" : "review"}
          icon={<Icon3D name="streak" size="sm" />}
        />
      </div>

      {/* Am I improving? — the honest version */}
      <section className="card-3d p-5">
        <h2 className="font-display text-base font-semibold">Am I improving?</h2>
        {improvement.direction === "insufficient_data" ? (
          <p className="mt-2 text-pretty text-sm text-muted-foreground">
            {improvement.note}
          </p>
        ) : (
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-semibold",
                improvement.direction === "up"
                  ? "bg-mastery/15 text-mastery"
                  : improvement.direction === "down"
                    ? "bg-weakness/15 text-weakness"
                    : "bg-secondary text-muted-foreground",
              )}
            >
              {improvement.direction === "up" ? (
                <ArrowUpRight className="size-4" />
              ) : improvement.direction === "down" ? (
                <ArrowDownRight className="size-4" />
              ) : (
                <ArrowRight className="size-4" />
              )}
              {improvement.change !== null
                ? `${improvement.change > 0 ? "+" : ""}${Math.round(improvement.change * 100)} points`
                : "No change"}
            </span>
            <p className="text-sm text-muted-foreground">
              {pct(improvement.earlier_accuracy)} earlier in this period →{" "}
              <span className="font-medium text-foreground">
                {pct(improvement.recent_accuracy)}
              </span>{" "}
              recently
            </p>
          </div>
        )}
      </section>

      {/* Consistency — real per-day minutes, gaps included */}
      <section className="card-3d p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-display text-base font-semibold">How consistent am I?</h2>
          <span className="text-xs text-muted-foreground tabular">
            {consistency.average_minutes_per_active_day} min per active day
          </span>
        </div>
        <ActivityChart data={report.daily_activity} />
      </section>

      {/* Where the work happened */}
      {report.by_assessment.length > 0 && (
        <section className="card-3d p-5">
          <h2 className="font-display text-base font-semibold">Where did it happen?</h2>
          <ul className="mt-3 space-y-2.5">
            {report.by_assessment.map((row) => (
              <li key={row.activity}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium">{row.label}</span>
                  <span className="text-muted-foreground tabular">
                    {row.accuracy === null
                      ? `${row.sessions} sessions`
                      : `${Math.round(row.accuracy * 100)}% · ${row.correct}/${row.attempted}`}
                  </span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-secondary">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      (row.accuracy ?? 0) >= 0.7
                        ? "bg-mastery"
                        : (row.accuracy ?? 0) >= 0.4
                          ? "bg-review"
                          : "bg-weakness",
                    )}
                    style={{ width: `${(row.accuracy ?? 0) * 100}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <BankCoverage bank={report.question_bank} />

      {/* Topic detail — premium */}
      {report.topics ? (
        <TopicPerformance topics={report.topics} />
      ) : (
        <section className="flex items-start gap-3 rounded-2xl border border-primary/20 plinth p-5">
          <Axo pose="rocket" size="sm" />
          <div className="min-w-0 flex-1">
            <h2 className="flex items-center gap-1.5 font-display text-base font-semibold">
              <Crown className="size-4 text-primary" />
              Topic-level analysis
            </h2>
            <p className="mt-1 text-pretty text-sm text-muted-foreground">
              Premium shows observed topic accuracy and areas to revise within the selected period.
            </p>
            <Link
              href="/premium"
              className="press mt-3 inline-flex h-9 items-center rounded-full bg-primary px-4 text-xs font-semibold text-primary-foreground"
            >
              See Premium
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}

/** Per-day study minutes. Days with nothing are drawn as gaps, because that is the signal. */
function ActivityChart({
  data,
}: {
  data: Array<{ date: string; minutes: number; sessions: number }>;
}) {
  const peak = Math.max(1, ...data.map((d) => d.minutes));

  return (
    <div className="mt-4">
      <div className="flex h-28 items-end gap-[3px]" role="img" aria-label="Daily study minutes">
        {data.map((day) => {
          const height = day.minutes ? Math.max(6, (day.minutes / peak) * 100) : 3;
          return (
            <div
              key={day.date}
              className="group relative flex-1"
              style={{ height: `${height}%` }}
              title={`${day.date}: ${day.minutes} min`}
            >
              <div
                className={cn(
                  "h-full w-full rounded-sm transition-colors",
                  day.minutes ? "bg-primary/70 group-hover:bg-primary" : "bg-border",
                )}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground">
        <span>{data[0]?.date.slice(5)}</span>
        <span className="tabular">peak {peak} min</span>
        <span>{data[data.length - 1]?.date.slice(5)}</span>
      </div>
    </div>
  );
}

function TopicPerformance({
  topics,
}: {
  topics: NonNullable<AnalyticsReport["topics"]>;
}) {
  if (topics.tracked_nodes === 0) {
    return (
      <section className="card-3d p-5">
        <h2 className="font-display text-base font-semibold">What am I weak at?</h2>
        <p className="mt-2 text-pretty text-sm text-muted-foreground">
          Nothing tracked yet. Once you have answered questions across a few topics, the
          weakest ones will be ranked here by how urgently they need revision.
        </p>
      </section>
    );
  }

  return (
    <>
      <section className="card-3d p-5">
        <h2 className="font-display text-base font-semibold">What should I revise?</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Observed accuracy in this period, using at least three scored items per area. This is not a prediction of mastery.
        </p>
        <ul className="mt-3 space-y-2">
          {topics.weakest.map((topic) => (
            <li key={topic.id || topic.label} className="flex items-center gap-3 rounded-xl bg-secondary/40 px-3 py-2.5">
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{topic.label}</span>
              <span className="text-xs text-muted-foreground tabular">
                {topic.correct}/{topic.attempted}
              </span>
              <span
                className={cn(
                  "w-12 rounded-full px-2 py-0.5 text-center text-xs font-semibold tabular",
                  topic.mastery < 0.4
                    ? "bg-weakness/15 text-weakness"
                    : topic.mastery < 0.7
                      ? "bg-review/15 text-review"
                      : "bg-mastery/15 text-mastery",
                )}
              >
                {Math.round(topic.mastery * 100)}%
              </span>
            </li>
          ))}
        </ul>

        {topics.strongest.length > 0 && (
          <>
            <h3 className="mt-5 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
              Strongest
            </h3>
            <ul className="mt-2 flex flex-wrap gap-2">
              {topics.strongest.slice(0, 5).map((topic) => (
                <li
                  key={topic.id || topic.label}
                  className="rounded-full bg-mastery/10 px-3 py-1 text-xs font-medium text-mastery"
                >
                  {topic.label} · {Math.round(topic.mastery * 100)}%
                </li>
              ))}
            </ul>
          </>
        )}
      </section>


    </>
  );
}


function BankCoverage({ bank }: { bank?: AnalyticsReport["question_bank"] }) {
  if (!bank) return null;
  return <section className="card-3d p-5" aria-label="Question bank coverage">
    <div className="flex items-baseline justify-between gap-3">
      <h2 className="font-display text-base font-semibold">Question bank</h2>
      <span className="text-sm text-muted-foreground tabular">{bank.percent_seen}% seen</span>
    </div>
    <p className="mt-1 text-xs text-muted-foreground">Currently available MCQs across your class. Coverage is all-time, independent of the selected activity period.</p>
    {bank.total ? <>
      <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-secondary">
        <div className="h-full rounded-full bg-primary" style={{ width: `${bank.percent_seen}%` }} />
      </div>
      <p className="mt-2 text-sm text-muted-foreground tabular">
        {bank.seen} of {bank.total} seen · {bank.answered} answered · {bank.missed} missed at least once
      </p>
    </> : <p className="mt-2 text-sm text-muted-foreground">No ready MCQs are available in your class yet.</p>}
  </section>;
}
