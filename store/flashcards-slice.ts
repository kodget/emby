/**
 * Flashcard Redux slice -- minimal UI state only.
 * All flashcard data is fetched from the server via flashcardApi (lib/api.ts).
 * This slice previously held local mock data; that has been removed.
 */
import { createSlice } from "@reduxjs/toolkit";

interface FlashcardsState {
  loading: boolean;
  error: string | null;
}

const initialState: FlashcardsState = {
  loading: false,
  error: null,
};

const flashcardsSlice = createSlice({
  name: "flashcards",
  initialState,
  reducers: {
    setLoading: (state, action) => { state.loading = action.payload; },
    setError: (state, action) => { state.error = action.payload; },
    clearError: (state) => { state.error = null; },
  },
});

export const { setLoading, setError, clearError } = flashcardsSlice.actions;

// Legacy no-op stubs so any remaining import does not crash
export const addCard = () => ({ type: "flashcards/noop" });
export const updateCard = () => ({ type: "flashcards/noop" });
export const deleteCard = () => ({ type: "flashcards/noop" });

export default flashcardsSlice.reducer;
