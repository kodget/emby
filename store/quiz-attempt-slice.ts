import { createSlice, createAsyncThunk, PayloadAction } from "@reduxjs/toolkit";
import api from "@/lib/api";

// ==================== TYPES ====================

export type QuestionStatus = "unanswered" | "answered" | "flagged" | "review";

export interface QuizQuestion {
  id: string;
  question_type: "mcq" | "theory";
  difficulty: "easy" | "medium" | "hard";
  question_text: string;
  option_a?: string;
  option_b?: string;
  option_c?: string;
  option_d?: string;
  explanation?: string;
  subject_name?: string;
  topic_name?: string;
}

export interface QuizAttempt {
  historical_read_only?: boolean;
  id: string;
  exam_type: "practice" | "mock" | "formal";
  status: "in_progress" | "submitted" | "auto_submitted" | "evaluated";
  is_timed: boolean;
  duration_minutes: number | null;
  started_at: string;
  submitted_at: string | null;
  time_remaining_seconds: number | null;
  questions: QuizQuestion[];
  mcq_count: number;
  theory_count: number;
  total_questions: number;
  responses?: { question: QuizQuestion; selected_option?: string; text_answer?: string; time_taken_seconds?: number }[];
  flagged_questions?: string[];
  subject_name?: string;
  block_name?: string;
  topic_name?: string;
}

export interface QuestionAnswer {
  question_id: string;
  selected_option?: string;
  text_answer?: string;
  time_taken_seconds: number;
}

export interface QuizAttemptState {
  loadRequestId: string | null;
  currentAttempt: QuizAttempt | null;
  currentQuestionIndex: number;
  answers: Record<string, QuestionAnswer>;
  questionStatuses: Record<string, QuestionStatus>;
  timeRemainingSeconds: number | null;
  timerExpiresAt: number | null;
  timerActive: boolean;
  // Record<string, boolean> instead of Set<string> ? Sets are not JSON-serializable
  visitedQuestions: Record<string, boolean>;
  loading: boolean;
  submitting: boolean;
  error: string | null;
  isSubmitted: boolean;
  resultId: string | null;
}

const initialState: QuizAttemptState = {
  loadRequestId: null,
  currentAttempt: null,
  currentQuestionIndex: 0,
  answers: {},
  questionStatuses: {},
  timeRemainingSeconds: null,
  timerExpiresAt: null,
  timerActive: false,
  visitedQuestions: {},   // plain object ? fully serializable
  loading: false,
  submitting: false,
  error: null,
  isSubmitted: false,
  resultId: null,
};

// ==================== ASYNC THUNKS ====================

export const loadAttempt = createAsyncThunk(
  "quizAttempt/loadAttempt",
  async (attemptId: string, { rejectWithValue }) => {
    try {
      const response = await api.get(`/api/quiz-attempts/${attemptId}/`);
      return response.data as QuizAttempt;
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || "Failed to load quiz attempt");
    }
  }
);

export const saveAnswer = createAsyncThunk(
  "quizAttempt/saveAnswer",
  async ({ attemptId, answer }: { attemptId: string; answer: QuestionAnswer }, { rejectWithValue }) => {
    try {
      await api.post(`/api/quiz-attempts/${attemptId}/answer/`, {
        question_id: answer.question_id,
        selected_option: answer.selected_option || null,
        text_answer: answer.text_answer ?? null,
        time_taken_seconds: answer.time_taken_seconds,
      });
      return answer;
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || "Failed to save answer");
    }
  }
);

export const flagQuestion = createAsyncThunk(
  "quizAttempt/flagQuestion",
  async ({ attemptId, questionId, isFlagged = true }: { attemptId: string; questionId: string; isFlagged?: boolean }, { rejectWithValue }) => {
    try {
      await api.post(`/api/quiz-attempts/${attemptId}/flag/`, { question_id: questionId, is_flagged: isFlagged });
      return { questionId, isFlagged };
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || "Failed to flag question");
    }
  }
);

export const submitAttempt = createAsyncThunk(
  "quizAttempt/submitAttempt",
  async (attemptId: string, { rejectWithValue }) => {
    try {
      const response = await api.post(`/api/quiz-attempts/${attemptId}/submit/`);
      return response.data as { id: string; message: string };
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || "Failed to submit quiz");
    }
  }
);

export const autoSubmitAttempt = createAsyncThunk(
  "quizAttempt/autoSubmitAttempt",
  async (attemptId: string, { rejectWithValue }) => {
    try {
      const response = await api.post(`/api/quiz-attempts/${attemptId}/auto_submit/`);
      return response.data as { id: string; message: string };
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.error || "Failed to auto-submit quiz");
    }
  }
);

// ==================== SLICE ====================

const quizAttemptSlice = createSlice({
  name: "quizAttempt",
  initialState,
  reducers: {
    navigateToQuestion(state, action: PayloadAction<number>) {
      const attempt = state.currentAttempt;
      if (!attempt) return;
      const idx = action.payload;
      if (idx >= 0 && idx < attempt.questions.length) {
        state.currentQuestionIndex = idx;
        state.visitedQuestions[attempt.questions[idx].id] = true;
      }
    },

    nextQuestion(state) {
      const attempt = state.currentAttempt;
      if (!attempt) return;
      if (state.currentQuestionIndex < attempt.questions.length - 1) {
        state.currentQuestionIndex += 1;
        state.visitedQuestions[attempt.questions[state.currentQuestionIndex].id] = true;
      }
    },

    prevQuestion(state) {
      if (state.currentQuestionIndex > 0) {
        state.currentQuestionIndex -= 1;
      }
    },

    setMCQAnswer(state, action: PayloadAction<{ questionId: string; option: string }>) {
      const { questionId, option } = action.payload;
      state.answers[questionId] = {
        ...state.answers[questionId],
        question_id: questionId,
        selected_option: option,
        time_taken_seconds: state.answers[questionId]?.time_taken_seconds ?? 0,
      };
      state.questionStatuses[questionId] = "answered";
    },

    setTheoryAnswer(state, action: PayloadAction<{ questionId: string; text: string }>) {
      const { questionId, text } = action.payload;
      state.answers[questionId] = {
        ...state.answers[questionId],
        question_id: questionId,
        text_answer: text,
        time_taken_seconds: state.answers[questionId]?.time_taken_seconds ?? 0,
      };
      if (text.trim().length > 0) {
        state.questionStatuses[questionId] = "answered";
      } else if (state.questionStatuses[questionId] !== "flagged") {
        state.questionStatuses[questionId] = "unanswered";
      }
    },

    toggleFlag(state, action: PayloadAction<string>) {
      const qId = action.payload;
      const current = state.questionStatuses[qId];
      state.questionStatuses[qId] =
        current === "flagged"
          ? state.answers[qId]
            ? "answered"
            : "unanswered"
          : "flagged";
    },

    tickTimer(state) {
      if (state.timerExpiresAt !== null) {
        state.timeRemainingSeconds = Math.max(0, Math.ceil((state.timerExpiresAt - Date.now()) / 1000));
      }
    },

    startTimer(state) {
      state.timerActive = true;
    },

    pauseTimer(state) {
      state.timerActive = false;
    },

    resetAttempt() {
      return initialState;
    },

    clearError(state) {
      state.error = null;
    },
  },

  extraReducers: (builder) => {
    builder
      .addCase(loadAttempt.pending, (state, action) => {
        state.loadRequestId = action.meta.requestId;
        state.timeRemainingSeconds = null;
        state.timerExpiresAt = null;
        state.timerActive = false;
        state.currentAttempt = null;
        state.answers = {};
        state.questionStatuses = {};
        state.currentQuestionIndex = 0;
        state.isSubmitted = false;
        state.loading = true;
        state.error = null;
      })
      .addCase(loadAttempt.fulfilled, (state, action) => {
        if (state.loadRequestId !== action.meta.requestId) return;
        state.loading = false;
        state.currentAttempt = action.payload;
        if (action.payload.status === "submitted" || action.payload.status === "auto_submitted") {
          state.isSubmitted = true;
        }
        action.payload.questions.forEach((q) => {
          if (!state.questionStatuses[q.id]) {
            state.questionStatuses[q.id] = "unanswered";
          }
        });
        action.payload.responses?.forEach(response => {
          if (!response.question || !action.payload.questions.some(q => q.id === response.question.id)) return;
          const id = response.question.id;
          state.answers[id] = { question_id: id, selected_option: response.selected_option,
            text_answer: response.text_answer, time_taken_seconds: response.time_taken_seconds ?? 0 };
          state.questionStatuses[id] = response.selected_option || response.text_answer?.trim() ? "answered" : "unanswered";
        });
        action.payload.flagged_questions?.forEach(id => { if (state.questionStatuses[id]) state.questionStatuses[id] = "flagged"; });
        if (action.payload.is_timed && action.payload.time_remaining_seconds !== null) {
          state.timeRemainingSeconds = action.payload.time_remaining_seconds;
          state.timerExpiresAt = Date.now() + action.payload.time_remaining_seconds * 1000;
        }
        // Mark first question as visited
        if (action.payload.questions.length > 0) {
          state.visitedQuestions[action.payload.questions[0].id] = true;
        }
      })
      .addCase(loadAttempt.rejected, (state, action) => {
        if (state.loadRequestId !== action.meta.requestId) return;
        state.loading = false;
        state.error = action.payload as string;
      });

    builder
      .addCase(saveAnswer.pending, (state) => { state.error = null; })
      .addCase(saveAnswer.fulfilled, (state, action) => {
        if (state.currentAttempt?.id !== action.meta.arg.attemptId) return;
        const answer = action.payload;
        if (answer.text_answer !== undefined && state.answers[answer.question_id]?.text_answer !== answer.text_answer) return;
        state.answers[answer.question_id] = answer;
        if (state.questionStatuses[answer.question_id] !== "flagged") {
          state.questionStatuses[answer.question_id] = answer.selected_option || answer.text_answer?.trim() ? "answered" : "unanswered";
        }
      })
      .addCase(saveAnswer.rejected, (state, action) => {
        if (state.currentAttempt?.id !== action.meta.arg.attemptId) return;
        state.error = action.payload as string;
      });

    builder.addCase(flagQuestion.fulfilled, (state, action) => {
      if (state.currentAttempt?.id !== action.meta.arg.attemptId) return;
      const { questionId, isFlagged } = action.payload;
      state.questionStatuses[questionId] = isFlagged ? "flagged" : state.answers[questionId] ? "answered" : "unanswered";
    });
    builder.addCase(flagQuestion.rejected, (state, action) => {
      if (state.currentAttempt?.id === action.meta.arg.attemptId) state.error = action.payload as string;
    });

    builder
      .addCase(submitAttempt.pending, (state) => {
        state.submitting = true;
        state.error = null;
      })
      .addCase(submitAttempt.fulfilled, (state, action) => {
        if (state.currentAttempt?.id !== action.meta.arg) return;
        state.submitting = false;
        state.isSubmitted = true;
        state.timerActive = false;
        state.resultId = action.payload.id;
      })
      .addCase(submitAttempt.rejected, (state, action) => {
        if (state.currentAttempt?.id !== action.meta.arg) return;
        state.submitting = false;
        state.error = action.payload as string;
      });

    builder.addCase(autoSubmitAttempt.pending, (state) => { state.submitting = true; state.error = null; });
    builder.addCase(autoSubmitAttempt.rejected, (state, action) => {
      if (state.currentAttempt?.id !== action.meta.arg) return;
      state.submitting = false;
      state.error = action.payload as string;
    });
    builder.addCase(autoSubmitAttempt.fulfilled, (state, action) => {
      if (state.currentAttempt?.id !== action.meta.arg) return;
      state.submitting = false;
      state.isSubmitted = true;
      state.timerActive = false;
      state.resultId = action.payload.id;
    });
  },
});

export const {
  navigateToQuestion,
  nextQuestion,
  prevQuestion,
  setMCQAnswer,
  setTheoryAnswer,
  toggleFlag,
  tickTimer,
  startTimer,
  pauseTimer,
  resetAttempt,
  clearError,
} = quizAttemptSlice.actions;

export default quizAttemptSlice.reducer;
