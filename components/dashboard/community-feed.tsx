"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { ArrowRight, ArrowUp, MessageSquare } from "lucide-react"
import { communityApi, type CommunityPost } from "@/lib/api"

export function CommunityFeed() {
  const [posts, setPosts] = useState<CommunityPost[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchPosts() {
      try {
        const data = await communityApi.getPosts()
        setPosts(data.slice(0, 3)) // Show top 3
      } catch (error) {
        console.error('Error fetching community posts:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchPosts()
  }, [])

  if (loading) {
    return (
      <section className="rounded-3xl border border-border bg-card p-6" aria-labelledby="community-heading">
        <header className="flex items-end justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-primary">Community</p>
            <h2 id="community-heading" className="mt-1 font-serif text-2xl">
              Trending in your class
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
    <section className="rounded-3xl border border-border bg-card p-6" aria-labelledby="community-heading">
      <header className="flex items-end justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-primary">Community</p>
          <h2 id="community-heading" className="mt-1 font-serif text-2xl">
            Trending in your class
          </h2>
        </div>
        <Link
          href="/community"
          className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          Open <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </header>
      
      {posts.length === 0 ? (
        <div className="mt-5 py-8 text-center">
          <p className="text-sm text-muted-foreground">No posts yet. Be the first to share!</p>
        </div>
      ) : (
        <ul className="mt-5 space-y-3">
          {posts.map((p) => {
            const timeAgo = formatTimeAgo(p.created_at)
            return (
              <li key={p.id} className="rounded-2xl border border-border p-4">
                <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                  {p.post_type} · {timeAgo}
                </p>
                <h3 className="mt-1 font-serif text-base leading-snug">{p.content.split('\n')[0]}</h3>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                  {p.content.split('\n').slice(1).join(' ')}
                </p>
                <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <ArrowUp className="size-3.5" aria-hidden="true" />
                    {p.likes_count}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <MessageSquare className="size-3.5" aria-hidden="true" />
                    {p.comments_count}
                  </span>
                  <span className="ml-auto text-foreground">{p.user_name}</span>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}
