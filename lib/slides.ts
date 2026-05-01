// lib/slides.ts
// Slide management system linked to curriculum

import type { TopicId, BlockId } from "./curriculum"

export type SlideId = string

export type Slide = {
  id: SlideId
  title: string
  // Link to curriculum
  topicId?: TopicId // For anatomy & physiology
  blockId?: BlockId // For biochemistry (no topic)
  // Metadata
  pages: number
  uploadedBy: string
  uploadedAt: string
  fileUrl?: string
  thumbnailUrl?: string
  // Content (for reader)
  content?: SlideContent[]
}

export type SlideContent = {
  pageNumber: number
  imageUrl: string // Base64 or URL
  text?: string // Extracted text for AI
}

// In-memory slide storage (replace with database in production)
const slidesStore: Map<string, Slide[]> = new Map()

// Initialize flag
let initialized = false

// Add a slide
function addSlide(slide: Slide): void {
  if (slide.topicId) {
    const key = `topic:${slide.topicId}`
    const existing = slidesStore.get(key) || []
    slidesStore.set(key, [...existing, slide])
  } else if (slide.blockId) {
    const key = `block:${slide.blockId}`
    const existing = slidesStore.get(key) || []
    slidesStore.set(key, [...existing, slide])
  }
}

// Mock data for development
function initializeMockSlides(): void {
  if (initialized) return // Prevent double initialization
  initialized = true
  
  // Anatomy slides
  addSlide({
    id: "slide-anat-b1-gross-1",
    title: "Introduction to Gross Anatomy",
    topicId: "anat-b1-gross",
    pages: 24,
    uploadedBy: "Uploader · Chioma",
    uploadedAt: "2 days ago",
  })
  
  addSlide({
    id: "slide-anat-b1-gross-2",
    title: "Upper Limb Anatomy",
    topicId: "anat-b1-gross",
    pages: 32,
    uploadedBy: "Uploader · Chioma",
    uploadedAt: "1 week ago",
  })

  addSlide({
    id: "slide-anat-b1-embryo-1",
    title: "Early Embryonic Development",
    topicId: "anat-b1-embryo",
    pages: 18,
    uploadedBy: "Uploader · Chioma",
    uploadedAt: "3 days ago",
  })

  addSlide({
    id: "slide-anat-b1-histo-1",
    title: "Epithelial Tissue",
    topicId: "anat-b1-histo",
    pages: 28,
    uploadedBy: "Uploader · Chioma",
    uploadedAt: "5 days ago",
  })

  // Physiology slides
  addSlide({
    id: "slide-phys-b1-general-1",
    title: "Introduction to Physiology",
    topicId: "phys-b1-general",
    pages: 20,
    uploadedBy: "Uploader · Tunde",
    uploadedAt: "1 day ago",
  })

  addSlide({
    id: "slide-phys-b1-ans-1",
    title: "Autonomic Nervous System Overview",
    topicId: "phys-b1-ans",
    pages: 26,
    uploadedBy: "Uploader · Tunde",
    uploadedAt: "4 days ago",
  })

  addSlide({
    id: "slide-phys-b2-cvs-1",
    title: "Cardiovascular System Basics",
    topicId: "phys-b2-cvs",
    pages: 30,
    uploadedBy: "Uploader · Tunde",
    uploadedAt: "2 days ago",
  })

  addSlide({
    id: "slide-phys-b2-resp-1",
    title: "Respiratory Physiology",
    topicId: "phys-b2-resp",
    pages: 22,
    uploadedBy: "Uploader · Tunde",
    uploadedAt: "1 week ago",
  })

  // Biochemistry slides (no topics, directly to blocks)
  addSlide({
    id: "slide-bioc-b1-1",
    title: "Introduction to Biochemistry",
    blockId: "bioc-b1",
    pages: 25,
    uploadedBy: "Uploader · Amara",
    uploadedAt: "Today",
  })

  addSlide({
    id: "slide-bioc-b1-2",
    title: "Carbohydrate Chemistry",
    blockId: "bioc-b1",
    pages: 30,
    uploadedBy: "Uploader · Amara",
    uploadedAt: "3 days ago",
  })

  addSlide({
    id: "slide-bioc-b2-1",
    title: "Protein Structure",
    blockId: "bioc-b2",
    pages: 28,
    uploadedBy: "Uploader · Amara",
    uploadedAt: "1 week ago",
  })

  addSlide({
    id: "slide-bioc-b3-1",
    title: "Lipid Metabolism",
    blockId: "bioc-b3",
    pages: 26,
    uploadedBy: "Uploader · Amara",
    uploadedAt: "2 weeks ago",
  })
}

// Get all slides for a topic
export function getSlidesByTopic(topicId: TopicId): Slide[] {
  initializeMockSlides()
  return slidesStore.get(`topic:${topicId}`) || []
}

// Get all slides for a block (biochemistry)
export function getSlidesByBlock(blockId: BlockId): Slide[] {
  initializeMockSlides()
  return slidesStore.get(`block:${blockId}`) || []
}

// Get a specific slide by ID
export function getSlideById(slideId: SlideId): Slide | undefined {
  initializeMockSlides()
  for (const slides of slidesStore.values()) {
    const found = slides.find((s) => s.id === slideId)
    if (found) return found
  }
  return undefined
}

// Get all slides for a course (topic or block)
export function getSlidesForCourse(courseId: string): Slide[] {
  initializeMockSlides()
  // Try as topic first
  const topicSlides = getSlidesByTopic(courseId)
  if (topicSlides.length > 0) return topicSlides
  
  // Try as block
  const blockSlides = getSlidesByBlock(courseId)
  return blockSlides
}
