// lib/progress.ts
// Dynamic progress tracking utilities

export type CourseProgress = {
  courseId: string
  totalSlides: number
  viewedSlides: number
  progress: number // 0-100
  lastAccessed: Date
  timeSpent: number // in seconds
}

export type SlideProgress = {
  slideId: string
  courseId: string
  viewed: boolean
  timeSpent: number
  lastViewed?: Date
}

// Calculate course progress based on viewed slides
export function calculateCourseProgress(
  totalSlides: number,
  viewedSlides: number
): number {
  if (totalSlides === 0) return 0
  return Math.round((viewedSlides / totalSlides) * 100)
}

// Get recent courses sorted by last accessed time
export function getRecentCourses(
  courses: CourseProgress[],
  limit: number = 3
): CourseProgress[] {
  return courses
    .sort((a, b) => b.lastAccessed.getTime() - a.lastAccessed.getTime())
    .slice(0, limit)
}

// Update slide progress
export function updateSlideProgress(
  currentProgress: SlideProgress[],
  slideId: string,
  courseId: string,
  timeSpent: number
): SlideProgress[] {
  const existingIndex = currentProgress.findIndex(
    (p) => p.slideId === slideId && p.courseId === courseId
  )

  const updatedSlide: SlideProgress = {
    slideId,
    courseId,
    viewed: true,
    timeSpent,
    lastViewed: new Date(),
  }

  if (existingIndex >= 0) {
    const updated = [...currentProgress]
    updated[existingIndex] = {
      ...updated[existingIndex],
      timeSpent: updated[existingIndex].timeSpent + timeSpent,
      lastViewed: new Date(),
      viewed: true,
    }
    return updated
  }

  return [...currentProgress, updatedSlide]
}

// Calculate aggregate progress for a block (multiple topics)
export function calculateBlockProgress(
  topicProgresses: Array<{ totalSlides: number; viewedSlides: number }>
): number {
  const totalSlides = topicProgresses.reduce((sum, t) => sum + t.totalSlides, 0)
  const viewedSlides = topicProgresses.reduce((sum, t) => sum + t.viewedSlides, 0)
  return calculateCourseProgress(totalSlides, viewedSlides)
}

// Format last accessed time
export function formatLastAccessed(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return "Just now"
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? "s" : ""} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`
  if (diffDays === 1) return "Yesterday"
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} week${Math.floor(diffDays / 7) > 1 ? "s" : ""} ago`
  return date.toLocaleDateString()
}

// Mock data generator for development (remove in production)
export function generateMockProgress(courseId: string): CourseProgress {
  return {
    courseId,
    totalSlides: Math.floor(Math.random() * 100) + 20,
    viewedSlides: Math.floor(Math.random() * 50),
    progress: Math.floor(Math.random() * 100),
    lastAccessed: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000),
    timeSpent: Math.floor(Math.random() * 3600),
  }
}
