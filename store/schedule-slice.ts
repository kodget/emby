// store/schedule-slice.ts
//
// The study planner used to live entirely in this slice: items were pushed into an
// array, completion flipped a boolean, and nothing ever reached the server. Building a
// plan and refreshing the page lost all of it — which is what the "planner does not
// persist" reports were describing.
//
// Every mutation is now a thunk against /api/schedule/, and the reducers only reflect
// what the server confirmed. The backend field names are snake_case, so mapping happens
// here in one place rather than leaking into components.

import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";

import api from "@/lib/api";

export type ScheduleItemType =
  | "read"
  | "quiz"
  | "theory"
  | "flashcards"
  | "steeplechase"
  | "histology";

export type ScheduleItem = {
  id: string;
  type: ScheduleItemType;
  title: string;
  courseId: string;
  courseName: string;
  slideId?: string;
  topicId?: string;
  estimatedMinutes: number;
  scheduledDate: string; // YYYY-MM-DD
  scheduledTime?: string; // HH:MM
  completed: boolean;
  completedAt?: string;
  details?: string;
  notes?: string;
};

/** Shape returned by /api/schedule/. */
type ApiScheduleItem = {
  id: number | string;
  activity_type: string;
  title: string;
  slide: string | null;
  slide_title: string | null;
  sub_block: string | null;
  sub_block_name: string | null;
  block: string | null;
  block_name: string | null;
  scheduled_date: string;
  scheduled_time: string | null;
  estimated_minutes: number;
  completed: boolean;
  completed_at: string | null;
};

function fromApi(row: ApiScheduleItem): ScheduleItem {
  return {
    id: String(row.id),
    type: (row.activity_type as ScheduleItemType) || "read",
    title: row.title,
    courseId: row.sub_block || row.block || "",
    courseName: row.sub_block_name || row.block_name || "",
    slideId: row.slide || undefined,
    topicId: row.sub_block || undefined,
    estimatedMinutes: row.estimated_minutes ?? 0,
    scheduledDate: row.scheduled_date,
    // The API returns HH:MM:SS; the UI works in HH:MM.
    scheduledTime: row.scheduled_time ? row.scheduled_time.slice(0, 5) : undefined,
    completed: Boolean(row.completed),
    completedAt: row.completed_at || undefined,
    details: row.slide_title || undefined,
  };
}

function toApi(item: Partial<ScheduleItem>) {
  const payload: Record<string, unknown> = {};
  if (item.type !== undefined) payload.activity_type = item.type;
  if (item.title !== undefined) payload.title = item.title;
  if (item.slideId !== undefined) payload.slide = item.slideId || null;
  if (item.topicId !== undefined) payload.sub_block = item.topicId || null;
  if (item.courseId !== undefined) payload.block = item.courseId || null;
  if (item.scheduledDate !== undefined) payload.scheduled_date = item.scheduledDate;
  if (item.scheduledTime !== undefined) {
    payload.scheduled_time = item.scheduledTime ? `${item.scheduledTime}:00` : null;
  }
  if (item.estimatedMinutes !== undefined) {
    payload.estimated_minutes = item.estimatedMinutes;
  }
  return payload;
}

export type StudyGoal = {
  id: string;
  title: string;
  targetDate: string;
  items: string[];
  progress: number;
};

type ScheduleState = {
  items: ScheduleItem[];
  goals: StudyGoal[];
  isModalOpen: boolean;
  editingItem: ScheduleItem | null;
  status: "idle" | "loading" | "ready" | "error";
  error: string | null;
  /** Ids with an in-flight mutation, so a row can show its own pending state. */
  pending: string[];
};

const initialState: ScheduleState = {
  items: [],
  goals: [],
  isModalOpen: false,
  editingItem: null,
  status: "idle",
  error: null,
  pending: [],
};

// ---------------------------------------------------------------- thunks
export const fetchSchedule = createAsyncThunk(
  "schedule/fetch",
  async (_: void, { rejectWithValue }) => {
    try {
      const res = await api.get("/api/schedule/");
      const rows: ApiScheduleItem[] = res.data?.results ?? res.data ?? [];
      return rows.map(fromApi);
    } catch (err: any) {
      return rejectWithValue(
        err?.response?.data?.detail ?? "Could not load your study plan.",
      );
    }
  },
);

export const createScheduleItem = createAsyncThunk(
  "schedule/create",
  async (item: Omit<ScheduleItem, "id" | "completed">, { rejectWithValue }) => {
    try {
      const res = await api.post("/api/schedule/", toApi(item));
      return fromApi(res.data);
    } catch (err: any) {
      return rejectWithValue(
        err?.response?.data?.detail ?? "Could not save that item.",
      );
    }
  },
);

export const saveScheduleItem = createAsyncThunk(
  "schedule/update",
  async (item: ScheduleItem, { rejectWithValue }) => {
    try {
      const res = await api.patch(`/api/schedule/${item.id}/`, toApi(item));
      return fromApi(res.data);
    } catch (err: any) {
      return rejectWithValue(
        err?.response?.data?.detail ?? "Could not update that item.",
      );
    }
  },
);

export const removeScheduleItem = createAsyncThunk(
  "schedule/delete",
  async (id: string, { rejectWithValue }) => {
    try {
      await api.delete(`/api/schedule/${id}/`);
      return id;
    } catch (err: any) {
      return rejectWithValue(
        err?.response?.data?.detail ?? "Could not delete that item.",
      );
    }
  },
);

export const toggleScheduleItem = createAsyncThunk(
  "schedule/toggle",
  async (
    { id, completed }: { id: string; completed: boolean },
    { rejectWithValue },
  ) => {
    try {
      // Completing is what feeds study time, streaks and XP, so it goes through the
      // dedicated action rather than a plain PATCH.
      const res = await api.post(
        `/api/schedule/${id}/${completed ? "complete" : "uncomplete"}/`,
      );
      return fromApi(res.data);
    } catch (err: any) {
      return rejectWithValue(
        err?.response?.data?.detail ?? "Could not update that item.",
      );
    }
  },
);

const scheduleSlice = createSlice({
  name: "schedule",
  initialState,
  reducers: {
    openScheduleModal: (state, action: PayloadAction<ScheduleItem | null>) => {
      state.isModalOpen = true;
      state.editingItem = action.payload;
    },
    closeScheduleModal: (state) => {
      state.isModalOpen = false;
      state.editingItem = null;
    },
    clearScheduleError: (state) => {
      state.error = null;
    },
    addStudyGoal: (state, action: PayloadAction<StudyGoal>) => {
      state.goals.push(action.payload);
    },
    updateStudyGoal: (state, action: PayloadAction<StudyGoal>) => {
      const index = state.goals.findIndex((g) => g.id === action.payload.id);
      if (index >= 0) state.goals[index] = action.payload;
    },
    deleteStudyGoal: (state, action: PayloadAction<string>) => {
      state.goals = state.goals.filter((g) => g.id !== action.payload);
    },
  },
  extraReducers: (builder) => {
    const upsert = (state: ScheduleState, item: ScheduleItem) => {
      const index = state.items.findIndex((i) => i.id === item.id);
      if (index >= 0) state.items[index] = item;
      else state.items.push(item);
      state.pending = state.pending.filter((id) => id !== item.id);
    };

    builder
      .addCase(fetchSchedule.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(fetchSchedule.fulfilled, (state, action) => {
        state.status = "ready";
        state.items = action.payload;
      })
      .addCase(fetchSchedule.rejected, (state, action) => {
        state.status = "error";
        state.error = String(action.payload ?? "Could not load your study plan.");
      })

      .addCase(createScheduleItem.fulfilled, (state, action) => {
        upsert(state, action.payload);
        state.isModalOpen = false;
        state.editingItem = null;
      })
      .addCase(createScheduleItem.rejected, (state, action) => {
        state.error = String(action.payload ?? "Could not save that item.");
      })

      .addCase(saveScheduleItem.fulfilled, (state, action) => {
        upsert(state, action.payload);
        state.isModalOpen = false;
        state.editingItem = null;
      })
      .addCase(saveScheduleItem.rejected, (state, action) => {
        state.error = String(action.payload ?? "Could not update that item.");
      })

      .addCase(removeScheduleItem.pending, (state, action) => {
        state.pending.push(action.meta.arg);
      })
      .addCase(removeScheduleItem.fulfilled, (state, action) => {
        state.items = state.items.filter((i) => i.id !== action.payload);
        state.pending = state.pending.filter((id) => id !== action.payload);
      })
      .addCase(removeScheduleItem.rejected, (state, action) => {
        state.pending = state.pending.filter((id) => id !== action.meta.arg);
        state.error = String(action.payload ?? "Could not delete that item.");
      })

      .addCase(toggleScheduleItem.pending, (state, action) => {
        state.pending.push(action.meta.arg.id);
      })
      .addCase(toggleScheduleItem.fulfilled, (state, action) => {
        upsert(state, action.payload);
      })
      .addCase(toggleScheduleItem.rejected, (state, action) => {
        state.pending = state.pending.filter((id) => id !== action.meta.arg.id);
        state.error = String(action.payload ?? "Could not update that item.");
      });
  },
});

export const {
  openScheduleModal,
  closeScheduleModal,
  clearScheduleError,
  addStudyGoal,
  updateStudyGoal,
  deleteStudyGoal,
} = scheduleSlice.actions;

export default scheduleSlice.reducer;
