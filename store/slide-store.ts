/**
 * Global Slide Store (Zustand)
 *
 * ARCHITECTURE RULE: currentSlideIndex is the single source of truth.
 * All panels (AI chat, resources, MCQs) subscribe to it.
 * Per-slide data is stored in Maps keyed by slideIndex.
 */

import { create } from "zustand";

// ── Types ──────────────────────────────────────────────────────────────────

export interface SlideData {
  index: number;
  pageNumber: number; // 1-based page number in the rendered PDF
  imageUrl: string; // Cloudinary URL
  text: string; // Extracted text (fed to AI)
  title: string;
  slideId: string; // DB slide ID
}

export interface ChatMessage {
  id: string;
  role: "user" | "ai";
  content: string;
  sources?: string[];
  youtube?: {
    title: string;
    channel?: string;
    query: string;
    isDissection?: boolean;
  };
}

export interface YouTubeResource {
  title: string;
  query: string;
  reason: string;
}

export interface TextbookResource {
  title: string;
  author: string;
  chapter: string;
  reason: string;
}

export interface MCQResource {
  question: string;
  options: string[];
  correct: number;
  explanation: string;
}

export interface ResourceObject {
  youtube: YouTubeResource[];
  textbooks: TextbookResource[];
  mcqs: MCQResource[];
}

export interface SlideStore {
  // ── Data ──────────────────────────────────────────────────────────────
  slides: SlideData[];
  currentSlideIndex: number; // ← single source of truth

  // Per-slide Maps
  chatHistory: Map<number, ChatMessage[]>;
  resources: Map<number, ResourceObject>;
  mcqAnswers: Map<string, number>; // key: `${slideIndex}_${questionIndex}`

  // UI
  isLoading: { chat: boolean; resources: boolean };

  // ── Actions ───────────────────────────────────────────────────────────
  setSlides: (slides: SlideData[]) => void;
  setCurrentSlideIndex: (index: number) => void;

  addChatMessage: (slideIndex: number, message: ChatMessage) => void;
  getChatHistory: (slideIndex: number) => ChatMessage[];

  setResources: (slideIndex: number, resources: ResourceObject) => void;
  getResources: (slideIndex: number) => ResourceObject | undefined;

  setMCQAnswer: (
    slideIndex: number,
    questionIndex: number,
    answer: number,
  ) => void;
  getMCQAnswer: (
    slideIndex: number,
    questionIndex: number,
  ) => number | undefined;

  setLoading: (key: "chat" | "resources", val: boolean) => void;

  reset: () => void;
}

// ── Store ──────────────────────────────────────────────────────────────────

export const useSlideStore = create<SlideStore>((set, get) => ({
  slides: [],
  currentSlideIndex: 0,
  chatHistory: new Map(),
  resources: new Map(),
  mcqAnswers: new Map(),
  isLoading: { chat: false, resources: false },

  setSlides: (slides) => set({ slides, currentSlideIndex: 0 }),

  setCurrentSlideIndex: (index) => set({ currentSlideIndex: index }),

  addChatMessage: (slideIndex, message) => {
    const { chatHistory } = get();
    const prev = chatHistory.get(slideIndex) ?? [];
    chatHistory.set(slideIndex, [...prev, message]);
    set({ chatHistory: new Map(chatHistory) });
  },

  getChatHistory: (slideIndex) => {
    return get().chatHistory.get(slideIndex) ?? [];
  },

  setResources: (slideIndex, resources) => {
    const { resources: map } = get();
    map.set(slideIndex, resources);
    set({ resources: new Map(map) });
  },

  getResources: (slideIndex) => get().resources.get(slideIndex),

  setMCQAnswer: (slideIndex, questionIndex, answer) => {
    const { mcqAnswers } = get();
    mcqAnswers.set(`${slideIndex}_${questionIndex}`, answer);
    set({ mcqAnswers: new Map(mcqAnswers) });
  },

  getMCQAnswer: (slideIndex, questionIndex) => {
    return get().mcqAnswers.get(`${slideIndex}_${questionIndex}`);
  },

  setLoading: (key, val) =>
    set((s) => ({ isLoading: { ...s.isLoading, [key]: val } })),

  reset: () =>
    set({
      slides: [],
      currentSlideIndex: 0,
      chatHistory: new Map(),
      resources: new Map(),
      mcqAnswers: new Map(),
    }),
}));
