import { useEffect } from "react";
import { useAppDispatch } from "@/store/hooks";
import { updateUserProfile } from "@/store/user-slice";
import { getStoredProfile } from "@/lib/guards";

/**
 * Initializes Redux user state from the profile stored in sessionStorage.
 * Called once at app level via AppInitializer.
 *
 * Role mapping (backend → frontend):
 *   class_head         → "class-rep"   (isVerifiedClassHead=class_head_verified)
 *   material_uploader  → "uploader"
 *   student            → "student"
 *
 * Premium access rules:
 *   - Verified class heads (class_head_verified=true)  → full premium
 *   - Paid premium subscribers (subscription_tier=premium, not expired) → full premium
 *   - Trial users                                       → full premium during trial
 *   - All others                                        → free tier only
 */
export function useUserInit() {
  const dispatch = useAppDispatch();

  useEffect(() => {
    const profile = getStoredProfile();
    if (!profile) return;

    const isVerifiedClassHead =
      profile.class_role === "class_head" && profile.class_head_verified === true;

    dispatch(
      updateUserProfile({
        id: profile.id.toString(),
        name: profile.full_name,
        username: profile.username,
        email: profile.email,
        photoUrl: profile.photo_url,
        school: profile.school_name,
        setName: profile.set_name,
        role: mapRole(profile.class_role),
        isVerifiedClassHead,
        isSignedIn: true,
        isOnboarded: profile.onboarding_completed,
        streak: profile.streak,
        subscription: mapSubscription(
          profile.subscription_tier,
          profile.subscription_expires_at,
          isVerifiedClassHead,
        ),
      }),
    );
  }, [dispatch]);
}

function mapRole(
  backendRole: string,
): "student" | "uploader" | "class-rep" {
  switch (backendRole) {
    case "class_head":
      return "class-rep";
    case "material_uploader":
      return "uploader";
    default:
      return "student";
  }
}

function mapSubscription(
  tier: string,
  expiresAt: string | null,
  isVerifiedClassHead: boolean,
) {
  // Verified class heads always get premium active status
  if (isVerifiedClassHead) {
    return {
      status: "active" as const,
      tier: "premium" as const,
      expiresAt: null,
    };
  }

  if (tier === "free" || !tier) {
    return { status: "free" as const, tier: "free" as const, expiresAt: null };
  }

  // Paid premium — check expiry
  if (expiresAt) {
    const expiry = new Date(expiresAt);
    const now = new Date();
    if (expiry < now) {
      return {
        status: "past_due" as const,
        tier: "premium" as const,
        expiresAt,
      };
    }
    return { status: "active" as const, tier: "premium" as const, expiresAt };
  }

  return {
    status: "active" as const,
    tier: "premium" as const,
    expiresAt: null,
  };
}
