"use client"

import { useEffect, useRef, useState } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { api, curriculumApi, type Slide } from "@/lib/api"
import { Reader } from "@/components/reader/reader"
import { SessionFooter } from "@/components/session-footer"
import { usePrivateMediaRefresh } from "@/hooks/use-private-media-refresh"
import { useContentSessionKey } from "@/store/hooks"

export default function ReadPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const courseId = params.courseId as string
  const materialId = params.materialId as string
  const sessionKey = useContentSessionKey()
  const loadVersion = useRef(0)
  
  const [slide, setSlide] = useState<Slide | null>(null)
  const [slideContent, setSlideContent] = useState<any>(null)
  const [suggestedVideos, setSuggestedVideos] = useState<any[]>([])
  const [courseBreadcrumb, setCourseBreadcrumb] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [preparing, setPreparing] = useState(false)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const refreshMedia = usePrivateMediaRefresh(`${materialId}:${sessionKey}`,
    () => Promise.all([curriculumApi.getSlide(materialId), curriculumApi.getSlideContent(materialId)]),
    ([freshSlide, content]) => { setSlide(freshSlide); setSlideContent(content) },
    () => {
      loadVersion.current++
      setSlide(null); setSlideContent(null); setSuggestedVideos([]); setCourseBreadcrumb('')
      router.push('/courses')
    },
  )

  useEffect(() => {
    if (!['pending', 'running'].includes(slideContent?.ai_index?.status)) return
    const session = sessionStorage.getItem('user')
    let cancelled = false
    const timer = setInterval(() => {
      void api.get(`/api/slides/${materialId}/status/`).then(async ({ data }) => {
        if (!data.ai_index || ['pending', 'running'].includes(data.ai_index.status)) return
        const content = data.ai_index.status === 'complete' ? await curriculumApi.getSlideContent(materialId) : null
        if (!cancelled && session === sessionStorage.getItem('user')) {
          setSlideContent((previous: any) => content || { ...previous, ai_index: data.ai_index })
        }
      }).catch((error: any) => {
        if (!cancelled && [401, 403, 404].includes(error?.response?.status)) {
          setSlide(null); setSlideContent(null); router.push('/courses')
        }
      })
    }, 10000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [materialId, sessionKey, slideContent?.ai_index?.status, router])

  useEffect(() => {
    const version = ++loadVersion.current
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    const session = sessionStorage.getItem('user')
    const active = () => version === loadVersion.current && session === sessionStorage.getItem('user')
    setSlide(null); setSlideContent(null); setSuggestedVideos([]); setCourseBreadcrumb(''); setError(''); setPreparing(false)
    async function fetchData() {
      let waitingForPages = false
      try {
        setLoading(true)
        
        // Fetch slide
        const slideData = await curriculumApi.getSlide(materialId)
        if (!active()) return
        setSlide(slideData)
        
        // Fetch slide content (extracted text and images)
        try {
          const content = await curriculumApi.getSlideContent(materialId)
          if (!active()) return
          if (!content?.pages?.length) {
            if (content?.processing) {
              waitingForPages = true
              setPreparing(true)
              retryTimer = setTimeout(fetchData, 2000)
              return
            }
            setError('This document has no readable pages yet. Please try again shortly.'); return
          }
          setPreparing(false)
          setSlideContent(content)
        } catch (error: any) {
          if (!active()) return
          if ([401, 403, 404].includes(error?.response?.status)) {
            setSlide(null); setError('This document is no longer available to your class.'); return
          }
          throw error
        }

        // Reading must not wait for an optional resource service.
        if (!active()) return
        setLoading(false)
        void curriculumApi.getSuggestedVideos(materialId).then((videos) => {
          if (active()) setSuggestedVideos(videos.videos || [])
        }).catch(() => {})
        
        // Build breadcrumb
        if (slideData.topic) {
          const topic = await curriculumApi.getTopic(slideData.topic).catch(() => null)
          if (!active()) return
          const topicName = topic?.name || ''
          setCourseBreadcrumb(topicName)
        } else if (slideData.block) {
          const block = await curriculumApi.getBlock(slideData.block).catch(() => null)
          if (!active()) return
          setCourseBreadcrumb(block?.name || '')
        }
        
      } catch (error: any) {
        if (active()) {
          setSlide(null); setSlideContent(null)
          setError([401, 403, 404].includes(error?.response?.status)
            ? 'This document is no longer available to your class.'
            : 'Could not load this document. Please try again.')
        }
      } finally {
        if (active() && !waitingForPages) setLoading(false)
      }
    }
    
    fetchData()
    return () => { loadVersion.current++; clearTimeout(retryTimer) }
  }, [courseId, materialId, router, sessionKey, attempt])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
          <p role="status" className="mt-4 text-sm text-muted-foreground">{preparing ? 'Upload saved. Preparing your slide pages...' : 'Loading slide...'}</p>
          {preparing && <button className="mt-3 underline" onClick={() => router.push('/courses')}>Back to courses</button>}
        </div>
      </div>
    )
  }

  if (error || !slide) {
    return <div role="alert" className="mx-auto max-w-lg p-8 text-center">
      <p>{error || 'This document is unavailable.'}</p>
      <button className="m-3 underline" onClick={() => setAttempt(value => value + 1)}>Try again</button>
      <button className="m-3 underline" onClick={() => router.push('/courses')}>Back to courses</button>
    </div>
  }

  const step = searchParams.get("step") ? parseInt(searchParams.get("step") as string) : 1
  const queueParam = searchParams.get("queue")
  
  let handleNext = undefined
  
  if (queueParam) {
    const queue = queueParam.split(',')
    const currentIndex = queue.indexOf(materialId)
    
    if (currentIndex !== -1 && currentIndex < queue.length - 1) {
      const nextId = queue[currentIndex + 1]
      handleNext = () => {
        router.push(`/read/${courseId}/${nextId}?session=true&step=${step}&queue=${queueParam}`)
      }
    }
  }

  return (
    <div className="flex flex-col min-h-screen" onErrorCapture={(event) => {
      if (event.target instanceof HTMLImageElement) void refreshMedia()
    }}>
      <div className="flex-1 min-h-0">
        <button className="px-4 py-1 text-sm underline" onClick={() => setAttempt(value => value + 1)}>Try again</button>
        <Reader key={`${materialId}:${sessionKey}`} courseId={courseId} slide={slide} slideContent={slideContent} suggestedVideos={suggestedVideos} courseBreadcrumb={courseBreadcrumb} onAccessDenied={() => {
          loadVersion.current++
          setSlide(null); setSlideContent(null); setSuggestedVideos([])
          setError('This document is no longer available to your class.')
        }} />
      </div>
      <SessionFooter currentStep={step} onNext={handleNext} />
    </div>
  )
}
