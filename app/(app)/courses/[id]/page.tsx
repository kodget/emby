"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import {
  ArrowLeft,
  BookOpen,
  FileText,
  ListChecks,
  Sparkles,
  Video,
  Link as LinkIcon,
  FileQuestion,
} from "lucide-react"
import { curriculumApi, progressApi, type Topic, type Block, type Slide, type Material, type UserProgress } from "@/lib/api"
import { ModuleUploadButton } from "@/components/app/module-upload-button"

const subjectColors: Record<string, string> = {
  anatomy: "#0d6b5e",
  physiology: "#b94a3b",
  "medical-biochemistry": "#6b7d3a",
}

export default function CourseDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string
  
  const [loading, setLoading] = useState(true)
  const [courseData, setCourseData] = useState<{
    id: string
    name: string
    subject: string
    subjectId: string
    breadcrumb: string
    color: string
    isTopic: boolean
  } | null>(null)
  const [slides, setSlides] = useState<Slide[]>([])
  const [materials, setMaterials] = useState<Material[]>([])
  const [progress, setProgress] = useState(0)
  
  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true)
        
        // Try to fetch as topic first
        let topicData: Topic | null = null
        let blockData: Block | null = null
        let isTopic = false
        
        try {
          topicData = await curriculumApi.getTopic(id)
          isTopic = true
        } catch (error) {
          // Not a topic, try as block
          try {
            blockData = await curriculumApi.getBlock(id)
          } catch (blockError) {
            // Neither topic nor block found
            router.push('/courses')
            return
          }
        }
        
        // Get subject info
        let subjectId = ''
        let subjectName = ''
        
        if (topicData) {
          const block = await curriculumApi.getBlock(topicData.id.split('-').slice(0, -1).join('-'))
          subjectId = block.subject
          const subject = await curriculumApi.getSubjects().then(subjects => 
            subjects.find(s => s.id === subjectId)
          )
          subjectName = subject?.name || ''
        } else if (blockData) {
          subjectId = blockData.subject
          const subject = await curriculumApi.getSubjects().then(subjects => 
            subjects.find(s => s.id === subjectId)
          )
          subjectName = subject?.name || ''
        }
        
        const courseName = topicData ? topicData.name : blockData!.name
        const color = subjectColors[subjectId] || "#0d6b5e"
        
        // Build breadcrumb
        let breadcrumb = subjectName
        if (blockData) {
          breadcrumb += ` · ${blockData.name}`
        }
        if (topicData) {
          breadcrumb += ` · ${topicData.name}`
        }
        
        setCourseData({
          id,
          name: courseName,
          subject: subjectName,
          subjectId,
          breadcrumb,
          color,
          isTopic,
        })
        
        // Fetch slides and materials
        const [slidesData, materialsData] = await Promise.all([
          isTopic 
            ? curriculumApi.getSlides({ topic: id })
            : curriculumApi.getSlides({ block: id }),
          isTopic
            ? curriculumApi.getMaterials({ topic: id })
            : curriculumApi.getMaterials({ block: id })
        ])
        
        setSlides(slidesData)
        setMaterials(materialsData)
        
        // Fetch user progress
        try {
          const progressData = await progressApi.getProgress()
          const courseSlideIds = slidesData.map(s => s.id)
          const courseProgress = progressData.filter(p => courseSlideIds.includes(p.slide))
          
          if (courseProgress.length > 0) {
            const avgProgress = courseProgress.reduce((sum, p) => sum + p.progress_percentage, 0) / courseProgress.length
            setProgress(Math.round(avgProgress))
          }
        } catch (error) {
          console.log('Progress data not available:', error)
        }
        
      } catch (error) {
        console.error('Error fetching course data:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchData()
  }, [id, router])
  
  if (loading) {
    return (
      <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:py-10">
        <div className="flex items-center justify-center py-20">
          <div className="text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
            <p className="mt-4 text-sm text-muted-foreground">Loading course...</p>
          </div>
        </div>
      </div>
    )
  }
  
  if (!courseData) {
    return null
  }
  
  const totalSlides = slides.reduce((sum, s) => sum + s.page_count, 0)

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:py-10">
      <Link
        href="/courses"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        All courses
      </Link>

      <header className="mt-4 grid gap-6 rounded-3xl border border-border bg-card p-6 md:grid-cols-[1.5fr_1fr] md:p-8">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
            {courseData.breadcrumb}
          </p>
          <h1 className="mt-2 font-serif text-4xl leading-tight tracking-tight md:text-5xl">{courseData.name}</h1>
          <p className="mt-4 max-w-2xl text-muted-foreground">
            {slides.length > 0 
              ? `${slides.length} slide set${slides.length > 1 ? 's' : ''} · ${totalSlides} pages${materials.length > 0 ? ` · ${materials.length} extra material${materials.length > 1 ? 's' : ''}` : ''}`
              : materials.length > 0
              ? `${materials.length} extra material${materials.length > 1 ? 's' : ''} available`
              : "No content uploaded yet for this course."}
          </p>

          <div className="mt-6 flex flex-wrap gap-2">
            {slides.length > 0 && (
              <>
                <Link
                  href={`/read/${courseData.id}/${slides[0].id}`}
                  className="inline-flex h-10 items-center gap-2 rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
                >
                  <Sparkles className="size-4" aria-hidden="true" />
                  Start reading
                </Link>
                <Link
                  href={`/quiz?topic=${courseData.id}`}
                  className="inline-flex h-10 items-center gap-2 rounded-full border border-border bg-background px-4 text-sm font-medium hover:border-primary"
                >
                  <ListChecks className="size-4" aria-hidden="true" />
                  Take a quiz
                </Link>
              </>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-4 rounded-2xl border border-border bg-background p-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Your progress</p>
            <p className="mt-1 font-serif text-5xl leading-none">{progress}%</p>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full"
              style={{ width: `${progress}%`, backgroundColor: courseData.color }}
              aria-hidden="true"
            />
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-xl border border-border p-3">
              <p className="text-[11px] uppercase tracking-widest text-muted-foreground">Slides</p>
              <p className="mt-1 font-serif text-xl">{slides.length}</p>
            </div>
            <div className="rounded-xl border border-border p-3">
              <p className="text-[11px] uppercase tracking-widest text-muted-foreground">Pages</p>
              <p className="mt-1 font-serif text-xl">{totalSlides}</p>
            </div>
          </div>
        </div>
      </header>

      <section className="mt-10" aria-labelledby="slides-heading">
        <h2 id="slides-heading" className="font-serif text-2xl">
          Slides
        </h2>
        <ul className="mt-4 space-y-4">
          {/* Upload button */}
          <li>
            <ModuleUploadButton courseId={courseData.id} moduleId={courseData.id} />
          </li>
          
          {slides.length === 0 && (
            <li className="rounded-2xl border border-dashed border-border bg-background/40 px-4 py-8 text-center">
              <p className="text-sm text-muted-foreground">No slides uploaded yet for this course.</p>
              <p className="mt-1 text-xs text-muted-foreground">Ask your class rep to upload slides.</p>
            </li>
          )}
          
          {slides.map((slide) => (
            <li key={slide.id}>
              <Link
                href={`/read/${courseData.id}/${slide.id}`}
                className="group flex items-center gap-4 rounded-2xl border border-border bg-card p-4 transition-all hover:border-primary/40 hover:bg-primary/5 hover:-translate-y-0.5 hover:shadow-md hover:shadow-primary/10"
              >
                <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary">
                  <FileText className="size-5" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{slide.title}</p>
                  <p className="truncate text-sm text-muted-foreground">
                    {slide.page_count} pages · {slide.uploaded_by_name || 'Unknown'} · {formatDate(slide.created_at)}
                  </p>
                </div>
                <span className="shrink-0 rounded-full border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground">
                  {slide.page_count} pages
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {/* Extra Materials Section */}
      {materials.length > 0 && (
        <section className="mt-10" aria-labelledby="materials-heading">
          <h2 id="materials-heading" className="font-serif text-2xl">
            Extra Materials
          </h2>
          <ul className="mt-4 space-y-4">
            {materials.map((material) => {
              const Icon = 
                material.material_type === 'video' ? Video :
                material.material_type === 'link' ? LinkIcon :
                material.material_type === 'past_question' ? FileQuestion :
                FileText
              
              return (
                <li key={material.id}>
                  <a
                    href={material.file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center gap-4 rounded-2xl border border-border bg-card p-4 transition-all hover:border-primary/40 hover:bg-primary/5 hover:-translate-y-0.5 hover:shadow-md hover:shadow-primary/10"
                  >
                    <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary">
                      <Icon className="size-5" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate font-medium">{material.title}</p>
                        <span className="shrink-0 rounded bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-primary">
                          {material.material_type.replace('_', ' ')}
                        </span>
                      </div>
                      {material.description && (
                        <p className="truncate text-sm text-muted-foreground">{material.description}</p>
                      )}
                      <p className="truncate text-xs text-muted-foreground">
                        {material.uploaded_by_name || 'Unknown'} · {formatDate(material.created_at)}
                      </p>
                    </div>
                  </a>
                </li>
              )
            })}
          </ul>
        </section>
      )}
    </div>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  return date.toLocaleDateString()
}
