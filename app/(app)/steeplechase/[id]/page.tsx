import { steeplechaseSets } from "@/lib/data"
import { SteeplechaseRunner } from "@/components/steeplechase/steeplechase-runner"
import { notFound } from "next/navigation"

export default async function SteeplechasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const session = steeplechaseSets[id]
  if (!session) notFound()

  return <SteeplechaseRunner session={session} />
}
