import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { Flashcard } from "@/lib/data";

interface FlashcardsState {
  userCards: Flashcard[];
}

const initialState: FlashcardsState = {
  userCards: [],
};

const flashcardsSlice = createSlice({
  name: "flashcards",
  initialState,
  reducers: {
    addCard: (
      state,
      action: PayloadAction<
        Omit<
          Flashcard,
          | "id"
          | "due"
          | "easeFactor"
          | "interval"
          | "repetitions"
          | "nextReview"
        >
      >,
    ) => {
      const newCard: Flashcard = {
        ...action.payload,
        id: Date.now().toString(),
        due: true,
        easeFactor: 2.5,
        interval: 1,
        repetitions: 0,
        nextReview: new Date(),
      };
      state.userCards.push(newCard);
    },
    updateCard: (state, action: PayloadAction<Flashcard>) => {
      const index = state.userCards.findIndex(
        (c) => c.id === action.payload.id,
      );
      if (index !== -1) {
        state.userCards[index] = action.payload;
      }
    },
    deleteCard: (state, action: PayloadAction<string>) => {
      state.userCards = state.userCards.filter((c) => c.id !== action.payload);
    },
  },
});

export const { addCard, updateCard, deleteCard } = flashcardsSlice.actions;
export default flashcardsSlice.reducer;
