"use client"

import { useEffect, useState, use } from "react"
import { SteeplechaseRunner } from "@/components/steeplechase/steeplechase-runner"
import { notFound } from "next/navigation"
import { curriculumApi, SteeplechaseQuestion } from "@/lib/api"
import { Skeleton } from "@/components/ui/skeleton"

export default function SteeplechasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const decodedId = decodeURIComponent(id)
  const [session, setSession] = useState<{ id: string; title: string; items: SteeplechaseQuestion[]; durationSec: number } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchSession = async () => {
      try {
        const questions = await curriculumApi.getSteeplechaseQuestions()
        const sessionQuestions = questions.filter(q => (q.source_file || "Other") === decodedId)
        
        if (sessionQuestions.length === 0) {
          notFound()
          return
        }

        let title = decodedId.replace('.pdf', '')
        if (title === "Other") title = "General Practice Set"

        setSession({
          id: decodedId,
          title,
          items: sessionQuestions,
          durationSec: 30
        })
      } catch (error) {
        console.error("Failed to load steeplechase session:", error)
      } finally {
        setLoading(false)
      }
    }
    fetchSession()
  }, [decodedId])

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center p-4">
        <div className="flex flex-col items-center gap-4">
          <Skeleton className="h-12 w-12 rounded-full" />
          <Skeleton className="h-6 w-48" />
          <p className="text-sm text-muted-foreground">Preparing your steeplechase session...</p>
        </div>
      </div>
    )
  }

  if (!session) return null

  return <SteeplechaseRunner session={session} />
}
