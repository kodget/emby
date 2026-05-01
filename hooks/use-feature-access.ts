import { useSelector } from "react-redux";
import { RootState } from "@/store/store";

export type Feature =
  | "unlimited_ai_explanations"
  | "all_past_questions"
  | "steeplechase"
  | "spaced_repetition_flashcards"
  | "community_posting"
  | "weekly_analytics"
  | "offline_pdf_reader"
  | "unlimited_ai_chat"
  | "unlimited_past_questions";

const FREE_FEATURES: Feature[] = [];
const PREMIUM_FEATURES: Feature[] = [
  "unlimited_ai_explanations",
  "all_past_questions",
  "steeplechase",
  "spaced_repetition_flashcards",
  "community_posting",
  "weekly_analytics",
  "offline_pdf_reader",
];

export function useFeatureAccess() {
  const subscription = useSelector(
    (state: RootState) => state.user.subscription,
  );

  // Safety check: ensure subscription exists with default values
  const safeSubscription = subscription || {
    status: "free" as SubscriptionStatus,
    tier: "free" as SubscriptionTier,
  };

  const hasAccess = (feature: Feature): boolean => {
    if (safeSubscription.tier === "premium" && safeSubscription.status === "active") {
      return true;
    }
    if (safeSubscription.status === "trial") {
      return true; // Trial users have access to all features
    }
    return FREE_FEATURES.includes(feature);
  };

  const isPremium = safeSubscription.tier === "premium";
  const isTrial = safeSubscription.status === "trial";
  const isFree = safeSubscription.tier === "free" || safeSubscription.status === "free";

  return {
    hasAccess,
    isPremium,
    isTrial,
    isFree,
    subscription: safeSubscription,
  };
}
