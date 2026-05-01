"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { curriculumApi, progressApi, type Slide } from "@/lib/api"
import { Reader } from "@/components/reader/reader"

export default function ReadPage() {
  const params = useParams()
  const router = useRouter()
  const courseId = params.courseId as string
  const materialId = params.materialId as string
  
  const [slide, setSlide] = useState<Slide | null>(null)
  const [slideContent, setSlideContent] = useState<any>(null)
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

  return <Reader courseId={courseId} slide={slide} slideContent={slideContent} courseBreadcrumb={courseBreadcrumb} />
}
