"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { CalendarClock, ArrowRight } from "lucide-react"
import { testsApi, type UpcomingTest } from "@/lib/api"

function readinessTone(pct: number) {
  if (pct >= 70) return { text: "text-mastery", bar: "bg-mastery", label: "Ready" }
  if (pct >= 45) return { text: "text-review", bar: "bg-review", label: "Needs work" }
  return { text: "text-weakness", bar: "bg-weakness", label: "At risk" }
}

function urgencyTone(days: number) {
  if (days <= 3) return "text-weakness"
  if (days <= 10) return "text-review"
  return "text-muted-foreground"
}

function calculateDaysAway(dateString: string): number {
  const testDate = new Date(dateString)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  testDate.setHours(0, 0, 0, 0)
  const diffMs = testDate.getTime() - today.getTime()
  return Math.ceil(diffMs / 86400000)
}

export function UpcomingTests() {
  const [tests, setTests] = useState<UpcomingTest[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchTests() {
      try {
        const data = await testsApi.getUpcomingTests()
        setTests(data.slice(0, 3)) // Show top 3
      } catch (error) {
        console.error('Error fetching tests:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchTests()
  }, [])

  if (loading) {
    return (
      <section
        aria-labelledby="upcoming-tests-heading"
        className="rounded-2xl border border-border bg-card p-5"
      >
        <header className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span
              className="flex size-7 items-center justify-center rounded-lg bg-learning/15 text-learning"
              aria-hidden="true"
            >
              <CalendarClock className="size-4" />
            </span>
            <h2
              id="upcoming-tests-heading"
              className="font-serif text-base font-semibold tracking-tight"
            >
              Upcoming tests
            </h2>
          </div>
        </header>
        <div className="flex items-center justify-center py-8">
          <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-solid border-primary border-r-transparent"></div>
        </div>
      </section>
    )
  }
  return (
    <section
      aria-labelledby="upcoming-tests-heading"
      className="rounded-2xl border border-border bg-card p-5"
    >
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className="flex size-7 items-center justify-center rounded-lg bg-learning/15 text-learning"
            aria-hidden="true"
          >
            <CalendarClock className="size-4" />
          </span>
          <h2
            id="upcoming-tests-heading"
            className="font-serif text-base font-semibold tracking-tight"
          >
            Upcoming tests
          </h2>
        </div>
      </header>

      {tests.length === 0 ? (
        <div className="mt-4 py-8 text-center">
          <p className="text-sm text-muted-foreground">No upcoming tests scheduled</p>
        </div>
      ) : (
        <ul className="mt-4 space-y-2">
          {tests.map((t) => {
            const daysAway = calculateDaysAway(t.test_date)
            const readinessPct = 50 // TODO: Calculate from user progress
            const tone = readinessTone(readinessPct)
            const href = `/quiz/${t.id}`
            
            return (
              <li key={t.id}>
                <Link
                  href={href}
                  className="group flex items-start gap-3 rounded-xl border border-border bg-background/40 p-3 transition-colors hover:border-primary/40"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium text-foreground">
                        {t.title}
                      </p>
                    </div>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {t.subject_name} ·{" "}
                      <span className={`font-medium ${urgencyTone(daysAway)}`}>
                        in {daysAway} {daysAway === 1 ? "day" : "days"}
                      </span>
                    </p>
                    <div className="mt-2 flex items-center gap-2">
                      <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
                        <div
                          className={`h-full rounded-full ${tone.bar}`}
                          style={{ width: `${readinessPct}%` }}
                          aria-hidden="true"
                        />
                      </div>
                      <span className={`font-mono text-[11px] tabular-nums ${tone.text}`}>
                        {tone.label}
                      </span>
                    </div>
                  </div>
                  <ArrowRight className="size-4 shrink-0 translate-y-0.5 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
