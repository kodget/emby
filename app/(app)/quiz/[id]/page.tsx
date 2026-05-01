import { notFound } from "next/navigation"
import { quizzes } from "@/lib/data"
import { QuizRunner } from "@/components/quiz/quiz-runner"

export default async function QuizPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const quiz = quizzes[id]
  if (!quiz) notFound()
  return <QuizRunner quiz={quiz} />
}
