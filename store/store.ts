import { configureStore } from "@reduxjs/toolkit";
import uploadsReducer from "./uploads-slice";
import userReducer from "./user-slice";
import progressReducer from "./progress-slice";
import scheduleReducer from "./schedule-slice";
import flashcardsReducer from "./flashcards-slice";
import quizAttemptReducer from "./quiz-attempt-slice";

export const store = configureStore({
  reducer: {
    uploads: uploadsReducer,
    user: userReducer,
    progress: progressReducer,
    schedule: scheduleReducer,
    flashcards: flashcardsReducer,
    quizAttempt: quizAttemptReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
