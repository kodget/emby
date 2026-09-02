"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { curriculumApi, progressApi, type Slide } from "@/lib/api"
import { Reader } from "@/components/reader/reader"
import { SessionFooter } from "@/components/session-footer"

export default function ReadPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const courseId = params.courseId as string
  const materialId = params.materialId as string
  
  const [slide, setSlide] = useState<Slide | null>(null)
  const [slideContent, setSlideContent] = useState<any>(null)
  const [suggestedVideos, setSuggestedVideos] = useState<any[]>([])
  const [courseBreadcrumb, setCourseBreadcrumb] = useState<string>('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true)
        
        // Fetch slide
        const slideData = await curriculumApi.getSlide(materialId)
        setSlide(slideData)
        
        // Fetch slide content (extracted text and images)
        try {
          const content = await curriculumApi.getSlideContent(materialId)
          setSlideContent(content)
        } catch (error) {
          console.log('Content extraction failed, will show fallback:', error)
        }
        
        // Fetch AI suggested videos
        try {
          const videos = await curriculumApi.getSuggestedVideos(materialId)
          setSuggestedVideos(videos.videos || [])
        } catch (error) {
          console.log('Video suggestions failed:', error)
        }
        
        // Build breadcrumb
        if (slideData.topic) {
          const topic = await curriculumApi.getTopic(slideData.topic)
          const topicName = topic.name
          setCourseBreadcrumb(topicName)
        } else if (slideData.block) {
          const block = await curriculumApi.getBlock(slideData.block)
          setCourseBreadcrumb(block.name)
        }
        
        // Update progress - mark as accessed
        try {
          await progressApi.updateProgress({
            slide_id: materialId,
            current_page: 1,
            total_pages: slideData.page_count,
            time_spent_minutes: 0,
          })
        } catch (error) {
          console.log('Progress update failed:', error)
        }
        
      } catch (error) {
        console.error('Error fetching slide:', error)
        router.push('/courses')
      } finally {
        setLoading(false)
      }
    }
    
    fetchData()
  }, [courseId, materialId, router])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
          <p className="mt-4 text-sm text-muted-foreground">Loading slide...</p>
        </div>
      </div>
    )
  }

  if (!slide) {
    return null
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
    <div className="flex flex-col min-h-screen">
      <div className="flex-1 min-h-0">
        <Reader courseId={courseId} slide={slide} slideContent={slideContent} suggestedVideos={suggestedVideos} courseBreadcrumb={courseBreadcrumb} />
      </div>
      <SessionFooter currentStep={step} onNext={handleNext} />
    </div>
  )
}
