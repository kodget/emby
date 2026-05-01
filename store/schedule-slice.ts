// store/schedule-slice.ts
import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export type ScheduleItemType = "read" | "quiz" | "flashcards" | "steeplechase";

export type ScheduleItem = {
  id: string;
  type: ScheduleItemType;
  title: string;
  courseId: string;
  courseName: string;
  slideId?: string; // For read type
  topicId?: string; // For quiz/flashcards/steeplechase
  estimatedMinutes: number;
  scheduledDate: string; // ISO date string
  scheduledTime?: string; // HH:MM format
  completed: boolean;
  completedAt?: string;
  details?: string;
  notes?: string;
};

export type StudyGoal = {
  id: string;
  title: string;
  targetDate: string;
  items: string[]; // Schedule item IDs
  progress: number; // 0-100
};

type ScheduleState = {
  items: ScheduleItem[];
  goals: StudyGoal[];
  isModalOpen: boolean;
  editingItem: ScheduleItem | null;
};

const initialState: ScheduleState = {
  items: [],
  goals: [],
  isModalOpen: false,
  editingItem: null,
};

const scheduleSlice = createSlice({
  name: "schedule",
  initialState,
  reducers: {
    // Add new schedule item
    addScheduleItem: (state, action: PayloadAction<ScheduleItem>) => {
      state.items.push(action.payload);
    },

    // Update schedule item
    updateScheduleItem: (state, action: PayloadAction<ScheduleItem>) => {
      const index = state.items.findIndex((i) => i.id === action.payload.id);
      if (index >= 0) {
        state.items[index] = action.payload;
      }
    },

    // Delete schedule item
    deleteScheduleItem: (state, action: PayloadAction<string>) => {
      state.items = state.items.filter((i) => i.id !== action.payload);
    },

    // Mark item as complete
    completeScheduleItem: (state, action: PayloadAction<string>) => {
      const item = state.items.find((i) => i.id === action.payload);
      if (item) {
        item.completed = true;
        item.completedAt = new Date().toISOString();
      }
    },

    // Mark item as incomplete
    uncompleteScheduleItem: (state, action: PayloadAction<string>) => {
      const item = state.items.find((i) => i.id === action.payload);
      if (item) {
        item.completed = false;
        item.completedAt = undefined;
      }
    },

    // Open schedule modal
    openScheduleModal: (state, action: PayloadAction<ScheduleItem | null>) => {
      state.isModalOpen = true;
      state.editingItem = action.payload;
    },

    // Close schedule modal
    closeScheduleModal: (state) => {
      state.isModalOpen = false;
      state.editingItem = null;
    },

    // Add study goal
    addStudyGoal: (state, action: PayloadAction<StudyGoal>) => {
      state.goals.push(action.payload);
    },

    // Update study goal
    updateStudyGoal: (state, action: PayloadAction<StudyGoal>) => {
      const index = state.goals.findIndex((g) => g.id === action.payload.id);
      if (index >= 0) {
        state.goals[index] = action.payload;
      }
    },

    // Delete study goal
    deleteStudyGoal: (state, action: PayloadAction<string>) => {
      state.goals = state.goals.filter((g) => g.id !== action.payload);
    },

    // Load mock data
    loadMockSchedule: (state) => {
      const today = new Date().toISOString().split("T")[0];
      state.items = [
        {
          id: "sched-1",
          type: "read",
          title: "Finish Axilla boundaries & contents",
          courseId: "anat-b1-gross",
          courseName: "Gross Anatomy First Block",
          slideId: "slide-anat-b1-gross-1",
          details: "Slide 1–3",
          estimatedMinutes: 25,
          scheduledDate: today,
          scheduledTime: "09:00",
          completed: true,
          completedAt: new Date().toISOString(),
        },
        {
          id: "sched-2",
          type: "quiz",
          title: "5-question quiz · Axilla & Brachial Plexus",
          courseId: "anat-b1-gross",
          courseName: "Gross Anatomy First Block",
          topicId: "anat-b1-gross",
          details: "5 questions",
          estimatedMinutes: 5,
          scheduledDate: today,
          scheduledTime: "09:30",
          completed: false,
        },
        {
          id: "sched-3",
          type: "flashcards",
          title: "Review 12 due flashcards",
          courseId: "mixed",
          courseName: "Mixed",
          details: "12 cards",
          estimatedMinutes: 10,
          scheduledDate: today,
          scheduledTime: "10:00",
          completed: false,
        },
        {
          id: "sched-4",
          type: "steeplechase",
          title: "Steeplechase · 5 stations",
          courseId: "anat-b1-gross",
          courseName: "Gross Anatomy First Block",
          topicId: "anat-b1-gross",
          details: "5 stations",
          estimatedMinutes: 8,
          scheduledDate: today,
          scheduledTime: "10:15",
          completed: false,
        },
        {
          id: "sched-5",
          type: "read",
          title: "Start Glycolysis: slide 1 to 14",
          courseId: "bioc-b1",
          courseName: "Medical Biochemistry Block 1",
          slideId: "slide-bioc-b1-1",
          details: "Slides 1–14",
          estimatedMinutes: 30,
          scheduledDate: today,
          scheduledTime: "14:00",
          completed: false,
        },
      ];
    },
  },
});

export const {
  addScheduleItem,
  updateScheduleItem,
  deleteScheduleItem,
  completeScheduleItem,
  uncompleteScheduleItem,
  openScheduleModal,
  closeScheduleModal,
  addStudyGoal,
  updateStudyGoal,
  deleteStudyGoal,
  loadMockSchedule,
} = scheduleSlice.actions;

export default scheduleSlice.reducer;
