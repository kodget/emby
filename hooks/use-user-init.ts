import { useEffect } from 'react';
import { useAppDispatch } from '@/store/hooks';
import { updateUserProfile } from '@/store/user-slice';
import { getStoredProfile } from '@/lib/guards';

/**
 * Hook to initialize user data from localStorage into Redux store
 * This should be called once at the app level
 */
export function useUserInit() {
  const dispatch = useAppDispatch();

  useEffect(() => {
    const profile = getStoredProfile();
    
    if (profile) {
      // Map backend profile to Redux user state
      dispatch(updateUserProfile({
        id: profile.id.toString(),
        name: profile.full_name,
        username: profile.username,
        email: profile.email,
        photoUrl: profile.photo_url,
        school: profile.school_name,
        setName: profile.set_name,
        role: mapBackendRoleToStoreRole(profile.role),
        isClassRep: profile.role === 'class_head' && profile.class_head_verified,
        isSignedIn: true,
        isOnboarded: profile.onboarding_completed,
        streak: profile.streak,
        subscription: {
          status: mapSubscriptionStatus(profile.subscription_tier, profile.subscription_expires_at),
          tier: profile.subscription_tier === 'free' ? 'free' : 'premium',
          expiresAt: profile.subscription_expires_at,
        },
      }));
    }
  }, [dispatch]);
}

/**
 * Map backend role to store role format
 */
function mapBackendRoleToStoreRole(backendRole: string): 'student' | 'uploader' | 'brainstormer' | 'class-rep' {
  switch (backendRole) {
    case 'class_head':
      return 'class-rep';
    case 'material_uploader':
      return 'uploader';
    case 'brainstormer':
      return 'brainstormer';
    case 'student':
    default:
      return 'student';
  }
}

/**
 * Determine subscription status based on tier and expiration
 */
function mapSubscriptionStatus(
  tier: string,
  expiresAt: string | null
): 'free' | 'trial' | 'active' | 'past_due' {
  if (tier === 'free') return 'free';
  
  if (expiresAt) {
    const expirationDate = new Date(expiresAt);
    const now = new Date();
    
    if (expirationDate < now) {
      return 'past_due';
    }
    
    // Check if it's within trial period (first 14 days)
    const daysSinceStart = Math.floor((now.getTime() - (expirationDate.getTime() - 30 * 24 * 60 * 60 * 1000)) / (1000 * 60 * 60 * 24));
    if (daysSinceStart <= 14) {
      return 'trial';
    }
    
    return 'active';
  }
  
  return 'free';
}
