import { UserProfile } from "./api";

export const isAuthenticated = (): boolean => {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("token");
};

export const getStoredProfile = (): UserProfile | null => {
  if (typeof window === "undefined") return null;
  const profile = localStorage.getItem("user");
  return profile ? JSON.parse(profile) : null;
};

export const hasCompletedOnboarding = (): boolean => {
  const profile = getStoredProfile();
  return profile?.onboarding_completed ?? false;
};

export const isEmailVerified = (): boolean => {
  const profile = getStoredProfile();
  return profile?.email_verified ?? false;
};

export const isClassHeadVerified = (): boolean => {
  const profile = getStoredProfile();
  if (profile?.role !== "class_head") return true;
  return profile?.class_head_verified ?? false;
};

export const canAccessApp = (): boolean => {
  return isAuthenticated() && hasCompletedOnboarding() && isClassHeadVerified();
};

export const isPremium = (): boolean => {
  const profile = getStoredProfile();
  return profile?.subscription_tier === "premium" || profile?.subscription_tier === "class_head";
};

export const isClassHead = (): boolean => {
  const profile = getStoredProfile();
  return profile?.role === "class_head" && profile?.class_head_verified;
};

export const isBrainstormer = (): boolean => {
  const profile = getStoredProfile();
  return profile?.role === "brainstormer";
};

export const isMaterialUploader = (): boolean => {
  const profile = getStoredProfile();
  return profile?.role === "material_uploader";
};

export const isStudent = (): boolean => {
  const profile = getStoredProfile();
  return profile?.role === "student";
};

export const canCreatePosts = (): boolean => {
  const profile = getStoredProfile();
  if (!profile) return false;
  // FREE users cannot create posts - premium feature
  if (!isPremium()) return false;
  // All roles can create posts if they have premium
  return true;
};

export const canEngageCommunity = (): boolean => {
  const profile = getStoredProfile();
  if (!profile) return false;
  // FREE users can only read community - cannot like/comment
  return isPremium();
};

export const canUploadMaterials = (): boolean => {
  const profile = getStoredProfile();
  if (!profile) return false;
  // Material uploaders and class heads can upload materials
  return ["material_uploader", "class_head"].includes(profile.role);
};

export const canManageClass = (): boolean => {
  return isClassHead();
};

export const getRedirectPath = (): string => {
  if (!isAuthenticated()) return "/signin";
  if (!hasCompletedOnboarding()) return "/onboarding";
  if (!isClassHeadVerified()) return "/verification-pending";
  return "/dashboard";
};

export const checkFeatureAccess = (feature: "premium" | "class_head" | "create_posts" | "upload_materials" | "manage_class" | "engage_community" | "steeplechase" | "unlimited_ai" | "unlimited_quiz"): boolean => {
  const profile = getStoredProfile();
  if (!profile) return false;

  switch (feature) {
    case "premium":
      return isPremium();
    case "class_head":
      return isClassHead();
    case "create_posts":
      return canCreatePosts();
    case "engage_community":
      return canEngageCommunity();
    case "upload_materials":
      return canUploadMaterials();
    case "manage_class":
      return canManageClass();
    case "steeplechase":
      return isPremium();
    case "unlimited_ai":
      return isPremium();
    case "unlimited_quiz":
      return isPremium();
    default:
      return false;
  }
};
