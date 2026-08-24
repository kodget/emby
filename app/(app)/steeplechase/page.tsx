"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { quizzes } from "@/lib/data"
import { curriculumApi, SteeplechaseQuestion } from "@/lib/api"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ArrowRight, Trophy, Clock, Target, ListChecks } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"

export default function SteeplechaseIndex() {
  const [sessions, setSessions] = useState<{ id: string; title: string; items: SteeplechaseQuestion[]; durationSec: number }[]>([])
  const [loading, setLoading] = useState(true)
  const quizList = Object.values(quizzes)

  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const questions = await curriculumApi.getSteeplechaseQuestions()
        
        // Group by source_file
        const groups: Record<string, SteeplechaseQuestion[]> = {}
        questions.forEach(q => {
          const key = q.source_file || "Other"
          if (!groups[key]) groups[key] = []
          groups[key].push(q)
        })

        const fetchedSessions = Object.entries(groups).map(([source, items], index) => {
          // Format title
          let title = source.replace('.pdf', '')
          if (title === "Other") title = "General Practice Set"
          
          return {
            id: encodeURIComponent(source),
            title,
            items,
            durationSec: 30 // standard 30s per station
          }
        })
        
        setSessions(fetchedSessions)
      } catch (error) {
        console.error("Failed to fetch steeplechase questions:", error)
      } finally {
        setLoading(false)
      }
    }

    fetchQuestions()
  }, [])

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:py-12">
      <header className="mb-8 max-w-2xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
          <Trophy className="h-3.5 w-3.5 text-accent" />
          Exam-style practice
        </div>
        <h1 className="mt-3 font-serif text-4xl font-semibold tracking-tight text-balance md:text-5xl">
          Steeplechase & timed quizzes
        </h1>
        <p className="mt-3 text-muted-foreground text-pretty">
          Practice like the real thing. Labeled specimens with a ticking clock, and MCQs that mimic your CAs and end-of-term exams.
        </p>
      </header>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-serif text-xl font-semibold">Steeplechase sessions</h2>
          <p className="text-sm text-muted-foreground">{sessions.length} available</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {loading ? (
             Array.from({ length: 4 }).map((_, i) => (
                <Card key={i} className="flex flex-col overflow-hidden border-border/60 p-0">
                  <Skeleton className="h-40 w-full" />
                  <div className="p-6">
                    <Skeleton className="h-6 w-3/4 mb-2" />
                    <Skeleton className="h-4 w-1/2 mb-4" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                </Card>
             ))
          ) : sessions.map((s) => (
            <Card key={s.id} className="flex flex-col overflow-hidden border-border/60 p-0">
              <div className="relative aspect-[16/8] bg-muted">
                <img
                  src={s.items[0]?.image_url || `/placeholder.svg?height=360&width=720&query=${encodeURIComponent(
                    "cadaveric dissection upper limb anatomy teaching lab, neutral tones",
                  )}`}
                  alt="Steeplechase specimen preview"
                  className="h-full w-full object-cover"
                />
                <Badge className="absolute left-4 top-4 bg-foreground/85 text-background hover:bg-foreground/85">
                  {s.items.length} stations
                </Badge>
              </div>
              <div className="flex flex-1 flex-col p-6">
                <h3 className="font-serif text-lg font-semibold">{s.title}</h3>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {s.durationSec}s / station
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Target className="h-3 w-3" />
                    Type-in answers
                  </span>
                </div>
                <div className="mt-auto pt-5">
                  <Button asChild className="w-full">
                    <Link href={`/steeplechase/${s.id}`}>
                      Start session
                      <ArrowRight className="ml-1 h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </section>

      <section className="mt-12">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-serif text-xl font-semibold">Timed quizzes</h2>
          <p className="text-sm text-muted-foreground">{quizList.length} available</p>
        </div>
        <div className="grid gap-3">
          {quizList.map((q) => (
            <Link
              key={q.id}
              href={`/quiz/${q.id}`}
              className="group flex items-center gap-4 rounded-2xl border border-border bg-card p-4 transition-colors hover:border-primary/40"
            >
              <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary">
                <ListChecks className="h-5 w-5" />
              </div>
              <div className="flex-1">
                <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">{q.topic}</p>
                <h3 className="font-serif text-lg font-semibold">{q.title}</h3>
                <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
                  <span>{q.questions.length} questions</span>
                  <span>·</span>
                  <span>{Math.round(q.durationSec / 60)} min</span>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-foreground" />
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
