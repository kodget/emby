import { configureStore } from "@reduxjs/toolkit";
import uploadsReducer from "./uploads-slice";
import userReducer from "./user-slice";
import progressReducer from "./progress-slice";
import scheduleReducer from "./schedule-slice";
import flashcardsReducer from "./flashcards-slice";

const PERSIST_KEY = "emby_user_state";
const FLASHCARDS_KEY = "emby_flashcards";

function loadUserState() {
  if (typeof window === "undefined") return undefined;
  try {
    const persisted = window.localStorage.getItem(PERSIST_KEY);
    return persisted ? JSON.parse(persisted) : undefined;
  } catch {
    return undefined;
  }
}

function loadFlashcardsState() {
  if (typeof window === "undefined") return undefined;
  try {
    const persisted = window.localStorage.getItem(FLASHCARDS_KEY);
    return persisted ? JSON.parse(persisted) : undefined;
  } catch {
    return undefined;
  }
}

const persistedUser = loadUserState();
const persistedFlashcards = loadFlashcardsState();

export const store = configureStore({
  reducer: {
    uploads: uploadsReducer,
    user: userReducer,
    progress: progressReducer,
    schedule: scheduleReducer,
    flashcards: flashcardsReducer,
  },
  preloadedState: {
    ...(persistedUser ? { user: persistedUser } : {}),
    ...(persistedFlashcards ? { flashcards: persistedFlashcards } : {}),
  },
});

if (typeof window !== "undefined") {
  store.subscribe(() => {
    const state = store.getState();
    window.localStorage.setItem(PERSIST_KEY, JSON.stringify(state.user));
    window.localStorage.setItem(
      FLASHCARDS_KEY,
      JSON.stringify(state.flashcards),
    );
  });
}

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
