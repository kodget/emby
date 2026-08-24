import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import type { SubscriptionStatus, SubscriptionTier } from "@/store/user-slice";

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

/**
 * Access rules:
 *
 * Verified class heads  → full premium (all features)
 * Premium paid/trial    → full premium (all features)
 * Students / uploaders  → free tier only (no premium features)

 */
export function useFeatureAccess() {
  const subscription = useSelector(
    (state: RootState) => state.user.subscription,
  );
  const isVerifiedClassHead = useSelector(
    (state: RootState) => state.user.isVerifiedClassHead,
  );

  const safe: { status: SubscriptionStatus; tier: SubscriptionTier } =
    subscription ?? { status: "free", tier: "free" };

  // Verified class head always gets full access regardless of subscription
  const hasPaidPremium =
    safe.tier === "premium" &&
    (safe.status === "active" || safe.status === "trial");

  const isPremium = isVerifiedClassHead || hasPaidPremium;
  const isTrial = safe.status === "trial" && !isVerifiedClassHead;
  const isFree = !isPremium;

  const hasAccess = (feature: Feature): boolean => isPremium;

  return {
    hasAccess,
    isPremium,
    isTrial,
    isFree,
    isClassHead: isVerifiedClassHead,
    subscription: safe,
  };
}
