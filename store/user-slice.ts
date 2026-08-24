import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type UserRole = "student" | "uploader" | "class-rep";

export type AuthProvider = "email" | "google" | null;
export type SubscriptionTier = "free" | "premium";
export type SubscriptionStatus = "free" | "trial" | "active" | "past_due";

export type SubscriptionState = {
  status: SubscriptionStatus;
  tier: SubscriptionTier;
  expiresAt?: string | null;
  paymentCardBrand?: string | null;
  paymentLast4?: string | null;
};

type UserState = {
  id: string;
  name: string;
  username: string;
  email: string;
  photoUrl: string | null;
  school: string;
  setName: string;
  role: UserRole;
  isVerifiedClassHead: boolean; // true only when role=class_head AND class_head_verified=true
  authProvider: AuthProvider;
  isSignedIn: boolean;
  isOnboarded: boolean;
  points: number;
  rank: number;
  streak: number;
  publicProfile: boolean;
  publicRank: boolean;
  subscription: SubscriptionState;
  usage: {
    aiQuestionsUsed: number;
    quizzesTaken: number;
    pastQuestionsUsed: number;
    flashcardsCreated: number;
    steeplechaseAttempts: number;
    lastReset: string;
  };
};

const initialState: UserState = {
  id: "",
  name: "",
  username: "",
  email: "",
  photoUrl: null,
  school: "",
  setName: "",
  role: "student",
  isVerifiedClassHead: false,
  authProvider: null,
  isSignedIn: false,
  isOnboarded: false,
  points: 0,
  rank: 0,
  streak: 0,
  publicProfile: true,
  publicRank: true,
  subscription: {
    status: "free",
    tier: "free",
    expiresAt: null,
    paymentCardBrand: null,
    paymentLast4: null,
  },
  usage: {
    aiQuestionsUsed: 0,
    quizzesTaken: 0,
    pastQuestionsUsed: 0,
    flashcardsCreated: 0,
    steeplechaseAttempts: 0,
    lastReset: new Date().toISOString().split("T")[0],
  },
};

function computeRank(points: number) {
  if (points >= 3000) return 1;
  if (points >= 2200) return 2;
  if (points >= 1800) return 3;
  if (points >= 1400) return 4;
  return 5;
}

export const userSlice = createSlice({
  name: "user",
  initialState,
  reducers: {
    setRole(state, action: PayloadAction<UserRole>) {
      state.role = action.payload;
    },
    setClassRep(state, action: PayloadAction<boolean>) {
      state.isVerifiedClassHead = action.payload;
      if (action.payload) state.role = "class-rep";
    },
    updateUserProfile(
      state,
      action: PayloadAction<Partial<UserState> & { backendRole?: string }>,
    ) {
      const payload = { ...action.payload };
      if (payload.backendRole) {
        const roleMap: Record<string, UserRole> = {
          class_head: "class-rep",
          material_uploader: "uploader",
          student: "student",
        };
        payload.role = roleMap[payload.backendRole] || "student";
        delete payload.backendRole;
      }
      Object.assign(state, payload);
      // isVerifiedClassHead must be explicitly set via the payload
      // It defaults to false unless explicitly provided
    },
    completeOnboarding(state) {
      state.isOnboarded = true;
      state.isSignedIn = true;
    },
    signIn(state, action: PayloadAction<{ email: string }>) {
      if (action.payload.email.trim()) {
        state.isSignedIn = true;
      }
    },
    logout(state) {
      Object.assign(state, initialState);
      state.isSignedIn = false;
    },

    awardPoints(state, action: PayloadAction<number>) {
      state.points += action.payload;
      state.rank = computeRank(state.points);
    },
    setSubscription(state, action: PayloadAction<Partial<SubscriptionState>>) {
      state.subscription = {
        ...state.subscription,
        ...action.payload,
      };
      if (action.payload.tier === "free") {
        state.subscription.status = "free";
      }
    },
    startFreeTrial(state) {
      state.subscription.status = "trial";
      state.subscription.tier = "premium";
      state.subscription.expiresAt = new Date(
        Date.now() + 14 * 24 * 60 * 60 * 1000,
      ).toISOString();
    },
    cancelSubscription(state) {
      state.subscription = {
        status: "free",
        tier: "free",
        expiresAt: null,
        paymentCardBrand: null,
        paymentLast4: null,
      };
    },
    incrementUsage(
      state,
      action: PayloadAction<
        "aiQuestions" | "quizzes" | "flashcards" | "steeplechase" | "pastQuestions"
      >,
    ) {
      const today = new Date().toISOString().split("T")[0];
      if (state.usage.lastReset !== today) {
        state.usage.aiQuestionsUsed = 0;
        state.usage.quizzesTaken = 0;
        state.usage.flashcardsCreated = 0;
        state.usage.steeplechaseAttempts = 0;
        state.usage.lastReset = today;
      }
      switch (action.payload) {
        case "aiQuestions":
          state.usage.aiQuestionsUsed += 1;
          break;
        case "quizzes":
          state.usage.quizzesTaken += 1;
          break;
        case "flashcards":
          state.usage.flashcardsCreated += 1;
          break;
        case "steeplechase":
          state.usage.steeplechaseAttempts += 1;
          break;
        case "pastQuestions":
          state.usage.pastQuestionsUsed += 1;
          break;
      }
    },
  },
});

export const {
  setRole,
  setClassRep,
  updateUserProfile,
  completeOnboarding,
  signIn,
  logout,
  awardPoints,
  setSubscription,
  startFreeTrial,
  cancelSubscription,
  incrementUsage,
} = userSlice.actions;
export default userSlice.reducer;
