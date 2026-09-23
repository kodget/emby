import { notFound } from "next/navigation"
import { redirect } from "next/navigation"

export default async function QuizPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  // This legacy route previously rendered a fabricated quiz from lib/data. Real
  // attempts are created by the backend and rendered by /quiz/attempt/[id].
  if (!id) notFound()
  redirect(`/quiz/attempt/${encodeURIComponent(id)}`)
}
