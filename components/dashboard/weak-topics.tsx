"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { AlertCircle, ArrowRight, Loader2 } from "lucide-react"
import { curriculumApi, progressApi } from "@/lib/api"

type WeakTopic = {
  id: string
  name: string
  block_name: string
  progress_percentage: number
  slides_count: number
}

export function WeakTopics() {
  const [topics, setTopics] = useState<WeakTopic[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchWeakTopics = async () => {
      try {
        // Get all blocks with topics
        const blocks = await curriculumApi.getBlocks()
        const userProgress = await progressApi.getProgress()
        
        // Create a map of slide progress by topic
        const topicProgressMap = new Map<string, { total: number; completed: number; slides: number }>()
        
        // Calculate progress per topic
        blocks.forEach(block => {
          block.topics.forEach(topic => {
            if (!topicProgressMap.has(topic.id)) {
              topicProgressMap.set(topic.id, { total: 0, completed: 0, slides: 0 })
            }
          })
        })
        
        // Count slides per topic from progress
        userProgress.forEach(progress => {
          // Find which topic this slide belongs to
          blocks.forEach(block => {
            block.topics.forEach(topic => {
              // Assuming slide belongs to topic if it matches (you may need to adjust this logic)
              const topicData = topicProgressMap.get(topic.id)
              if (topicData) {
                topicData.slides++
                topicData.total += progress.total_pages
                topicData.completed += progress.current_page
              }
            })
          })
        })
        
        // Find topics with low progress (below 70%)
        const weakTopics: WeakTopic[] = []
        blocks.forEach(block => {
          block.topics.forEach(topic => {
            const data = topicProgressMap.get(topic.id)
            if (data && data.total > 0) {
              const percentage = Math.round((data.completed / data.total) * 100)
              if (percentage < 70) {
                weakTopics.push({
                  id: topic.id,
                  name: topic.name,
                  block_name: block.name,
                  progress_percentage: percentage,
                  slides_count: data.slides,
                })
              }
            }
          })
        })
        
        // Sort by lowest progress first and take top 3
        weakTopics.sort((a, b) => a.progress_percentage - b.progress_percentage)
        setTopics(weakTopics.slice(0, 3))
      } catch (error) {
        console.error('Failed to fetch weak topics:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchWeakTopics()
  }, [])

  if (loading) {
    return (
      <section
        aria-labelledby="weak-topics-heading"
        className="rounded-2xl border border-border bg-card p-5"
      >
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </section>
    )
  }

  if (topics.length === 0) {
    return (
      <section
        aria-labelledby="weak-topics-heading"
        className="rounded-2xl border border-border bg-card p-5"
      >
        <header className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span
              className="flex size-7 items-center justify-center rounded-lg bg-weakness/15 text-weakness"
              aria-hidden="true"
            >
              <AlertCircle className="size-4" />
            </span>
            <h2
              id="weak-topics-heading"
              className="font-serif text-base font-semibold tracking-tight"
            >
              Needs a little love
            </h2>
          </div>
        </header>
        <p className="mt-4 text-sm text-muted-foreground text-center py-4">
          Great job! No weak topics found. Keep up the good work!
        </p>
      </section>
    )
  }

  return (
    <section
      aria-labelledby="weak-topics-heading"
      className="rounded-2xl border border-border bg-card p-5"
    >
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className="flex size-7 items-center justify-center rounded-lg bg-weakness/15 text-weakness"
            aria-hidden="true"
          >
            <AlertCircle className="size-4" />
          </span>
          <h2
            id="weak-topics-heading"
            className="font-serif text-base font-semibold tracking-tight"
          >
            Needs a little love
          </h2>
        </div>
        <Link
          href="/curriculum"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          View all
        </Link>
      </header>

      <p className="mt-1 text-xs text-muted-foreground">
        Below 70% progress. A few minutes here today pays off fastest.
      </p>

      <ul className="mt-4 space-y-2">
        {topics.map((t, i) => (
          <motion.li
            key={t.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }}
          >
            <Link
              href={`/curriculum?topic=${t.id}`}
              className="group flex items-center gap-3 rounded-xl border border-border bg-background/40 p-3 transition-all duration-150 hover:border-weakness/40 hover:bg-weakness/5 hover:-translate-y-0.5 hover:shadow-md hover:shadow-weakness/10"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {t.name}
                </p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {t.block_name} · {t.slides_count} slides
                </p>
              </div>
              <span className="font-mono text-sm font-semibold tabular-nums text-weakness">
                {t.progress_percentage}%
              </span>
              <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-weakness" />
            </Link>
          </motion.li>
        ))}
      </ul>
    </section>
  )
}
