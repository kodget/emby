// store/progress-slice.ts
import { createSlice, PayloadAction } from "@reduxjs/toolkit"
import type { CourseProgress, SlideProgress } from "@/lib/progress"

type ProgressState = {
  courses: CourseProgress[]
  slides: SlideProgress[]
  recentCourses: string[] // course IDs in order of recent access
}

const initialState: ProgressState = {
  courses: [],
  slides: [],
  recentCourses: [],
}

const progressSlice = createSlice({
  name: "progress",
  initialState,
  reducers: {
    // Update course progress
    updateCourseProgress: (state, action: PayloadAction<CourseProgress>) => {
      const index = state.courses.findIndex((c) => c.courseId === action.payload.courseId)
      if (index >= 0) {
        state.courses[index] = action.payload
      } else {
        state.courses.push(action.payload)
      }
      
      // Update recent courses
      state.recentCourses = state.recentCourses.filter((id) => id !== action.payload.courseId)
      state.recentCourses.unshift(action.payload.courseId)
      if (state.recentCourses.length > 3) {
        state.recentCourses = state.recentCourses.slice(0, 3)
      }
    },

    // Mark slide as viewed
    markSlideViewed: (
      state,
      action: PayloadAction<{ slideId: string; courseId: string; timeSpent: number }>
    ) => {
      const { slideId, courseId, timeSpent } = action.payload
      const index = state.slides.findIndex(
        (s) => s.slideId === slideId && s.courseId === courseId
      )

      if (index >= 0) {
        state.slides[index].viewed = true
        state.slides[index].timeSpent += timeSpent
        state.slides[index].lastViewed = new Date()
      } else {
        state.slides.push({
          slideId,
          courseId,
          viewed: true,
          timeSpent,
          lastViewed: new Date(),
        })
      }
    },

    // Access course (update last accessed time)
    accessCourse: (state, action: PayloadAction<string>) => {
      const courseId = action.payload
      const index = state.courses.findIndex((c) => c.courseId === courseId)
      
      if (index >= 0) {
        state.courses[index].lastAccessed = new Date()
      }

      // Update recent courses
      state.recentCourses = state.recentCourses.filter((id) => id !== courseId)
      state.recentCourses.unshift(courseId)
      if (state.recentCourses.length > 3) {
        state.recentCourses = state.recentCourses.slice(0, 3)
      }
    },

    // Initialize course progress
    initializeCourseProgress: (
      state,
      action: PayloadAction<{ courseId: string; totalSlides: number }>
    ) => {
      const { courseId, totalSlides } = action.payload
      const exists = state.courses.find((c) => c.courseId === courseId)
      
      if (!exists) {
        state.courses.push({
          courseId,
          totalSlides,
          viewedSlides: 0,
          progress: 0,
          lastAccessed: new Date(),
          timeSpent: 0,
        })
      }
    },

    // Reset all progress (for testing/development)
    resetProgress: (state) => {
      state.courses = []
      state.slides = []
      state.recentCourses = []
    },
  },
})

export const {
  updateCourseProgress,
  markSlideViewed,
  accessCourse,
  initializeCourseProgress,
  resetProgress,
} = progressSlice.actions

export default progressSlice.reducer
