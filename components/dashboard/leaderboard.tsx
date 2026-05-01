"use client"

import { useRef, useState, useEffect } from "react"
import { motion, useInView } from "framer-motion"
import { Flame } from "lucide-react"
import { statsApi, type UserStats } from "@/lib/api"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import { useAppSelector } from "@/store/hooks"

export function Leaderboard() {
  const ref = useRef<HTMLElement>(null)
  const inView = useInView(ref, { once: true, margin: "-40px" })
  const currentUser = useAppSelector((s) => s.user)
  
  const [leaderboard, setLeaderboard] = useState<UserStats[]>([])
  const [loading, setLoading] = useState(true)
  const [maxScore, setMaxScore] = useState(0)

  useEffect(() => {
    async function fetchLeaderboard() {
      try {
        const data = await statsApi.getLeaderboard(10)
        setLeaderboard(data)
        if (data.length > 0) {
          setMaxScore(Math.max(...data.map(p => p.points)))
        }
      } catch (error) {
        console.error('Error fetching leaderboard:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchLeaderboard()
  }, [])

  if (loading) {
    return (
      <section ref={ref} className="rounded-3xl border border-border bg-card p-6" aria-labelledby="leaderboard-heading">
        <header className="flex items-end justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-primary">This week</p>
            <h2 id="leaderboard-heading" className="mt-1 font-serif text-2xl">
              Class leaderboard
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
    <section ref={ref} className="rounded-3xl border border-border bg-card p-6" aria-labelledby="leaderboard-heading">
      <header className="flex items-end justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-primary">This week</p>
          <h2 id="leaderboard-heading" className="mt-1 font-serif text-2xl">
            Class leaderboard
          </h2>
        </div>
        <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
          Top {leaderboard.length}
        </span>
      </header>

      {leaderboard.length === 0 ? (
        <div className="mt-5 py-8 text-center">
          <p className="text-sm text-muted-foreground">No leaderboard data yet</p>
        </div>
      ) : (
        <ol className="mt-5 space-y-2">
          {leaderboard.map((p, i) => {
            const you = p.username === currentUser.email || p.name === currentUser.name
            const barWidth = maxScore > 0 ? Math.round((p.points / maxScore) * 100) : 0
            return (
              <motion.li
                key={p.id}
                initial={{ opacity: 0, x: -12 }}
                animate={inView ? { opacity: 1, x: 0 } : {}}
                transition={{ delay: i * 0.06, type: "spring", stiffness: 260, damping: 24 }}
                className={cn(
                  "group relative flex items-center gap-3 overflow-hidden rounded-2xl border px-3 py-2.5 transition-colors",
                  you ? "border-primary/40 bg-primary/5" : "border-transparent hover:border-border hover:bg-card",
                )}
              >
                {/* Score bar backdrop */}
                <motion.div
                  className={cn(
                    "absolute inset-y-0 left-0 rounded-2xl opacity-[0.07]",
                    you ? "bg-primary" : "bg-foreground",
                  )}
                  initial={{ width: 0 }}
                  animate={inView ? { width: `${barWidth}%` } : {}}
                  transition={{ delay: i * 0.06 + 0.15, duration: 0.7, ease: "easeOut" }}
                  aria-hidden="true"
                />

                <span
                  className={cn(
                    "relative flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                    p.rank === 1
                      ? "bg-accent text-accent-foreground"
                      : p.rank <= 3
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground",
                  )}
                >
                  {p.rank}
                </span>
                <Avatar className="relative size-8 border border-border">
                  <AvatarFallback className="bg-muted text-[11px]">
                    {p.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")
                      .slice(0, 2)
                      .toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="relative min-w-0 flex-1">
                  <p className={cn("truncate text-sm font-medium", you && "text-primary")}>
                    {you ? "You" : p.name}
                  </p>
                  <p className="text-[11px] text-muted-foreground">{p.points.toLocaleString()} pts</p>
                </div>
                <span className="relative flex items-center gap-1 text-xs text-muted-foreground">
                  <Flame className="size-3.5 text-accent" aria-hidden="true" />
                  {p.current_streak}
                </span>
              </motion.li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
