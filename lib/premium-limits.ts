/**
 * Premium Feature Limits
 * Defines and checks limits for free vs premium users
 */

export const LIMITS = {
  FREE: {
    AI_PROMPTS_PER_DAY: 5,
    STUDY_PLAN_ITEMS_PER_DAY: 3,
    MCQ_QUESTIONS_MAX: 10,
    THEORY_QUESTIONS_MAX: 0,
    COMMUNITY_ENGAGEMENT: false,
    ANALYTICS_ACCESS: false,
    VIDEO_SUGGESTIONS: false,
  },
  PREMIUM: {
    AI_PROMPTS_PER_DAY: Infinity,
    STUDY_PLAN_ITEMS_PER_DAY: Infinity,
    MCQ_QUESTIONS_MAX: 100,
    THEORY_QUESTIONS_MAX: 10,
    COMMUNITY_ENGAGEMENT: true,
    ANALYTICS_ACCESS: true,
    VIDEO_SUGGESTIONS: true,
  },
};

export type LimitType = 
  | 'AI_PROMPTS'
  | 'STUDY_PLAN_ITEMS'
  | 'MCQ_QUESTIONS'
  | 'THEORY_QUESTIONS'
  | 'COMMUNITY_ENGAGEMENT'
  | 'ANALYTICS_ACCESS'
  | 'VIDEO_SUGGESTIONS';

/**
 * Check if user has reached their limit for a feature
 */
export function hasReachedLimit(
  isPremium: boolean,
  limitType: LimitType,
  currentUsage: number
): boolean {
  const limits = isPremium ? LIMITS.PREMIUM : LIMITS.FREE;

  switch (limitType) {
    case 'AI_PROMPTS':
      return currentUsage >= limits.AI_PROMPTS_PER_DAY;
    case 'STUDY_PLAN_ITEMS':
      return currentUsage >= limits.STUDY_PLAN_ITEMS_PER_DAY;
    case 'MCQ_QUESTIONS':
      return currentUsage >= limits.MCQ_QUESTIONS_MAX;
    case 'THEORY_QUESTIONS':
      return currentUsage >= limits.THEORY_QUESTIONS_MAX;
    case 'COMMUNITY_ENGAGEMENT':
      return !limits.COMMUNITY_ENGAGEMENT;
    case 'ANALYTICS_ACCESS':
      return !limits.ANALYTICS_ACCESS;
    case 'VIDEO_SUGGESTIONS':
      return !limits.VIDEO_SUGGESTIONS;
    default:
      return false;
  }
}

/**
 * Get the limit value for a feature
 */
export function getLimit(isPremium: boolean, limitType: LimitType): number | boolean {
  const limits = isPremium ? LIMITS.PREMIUM : LIMITS.FREE;

  switch (limitType) {
    case 'AI_PROMPTS':
      return limits.AI_PROMPTS_PER_DAY;
    case 'STUDY_PLAN_ITEMS':
      return limits.STUDY_PLAN_ITEMS_PER_DAY;
    case 'MCQ_QUESTIONS':
      return limits.MCQ_QUESTIONS_MAX;
    case 'THEORY_QUESTIONS':
      return limits.THEORY_QUESTIONS_MAX;
    case 'COMMUNITY_ENGAGEMENT':
      return limits.COMMUNITY_ENGAGEMENT;
    case 'ANALYTICS_ACCESS':
      return limits.ANALYTICS_ACCESS;
    case 'VIDEO_SUGGESTIONS':
      return limits.VIDEO_SUGGESTIONS;
    default:
      return false;
  }
}

/**
 * Get upgrade message for a specific limit
 */
export function getUpgradeMessage(limitType: LimitType): string {
  switch (limitType) {
    case 'AI_PROMPTS':
      return 'You have reached your daily limit of 5 AI prompts. Upgrade to Premium for unlimited prompts or wait until tomorrow.';
    case 'STUDY_PLAN_ITEMS':
      return 'You have reached your daily limit of 3 study plan items. Upgrade to Premium for unlimited planning or wait until tomorrow.';
    case 'MCQ_QUESTIONS':
      return 'Free users can access up to 10 MCQ questions per quiz. Upgrade to Premium for up to 100 questions.';
    case 'THEORY_QUESTIONS':
      return 'Theory questions are only available for Premium users. Upgrade to access up to 10 theory questions per quiz.';
    case 'COMMUNITY_ENGAGEMENT':
      return 'Full community engagement (posting, liking, commenting) is only available for Premium users. Upgrade to join the conversation.';
    case 'ANALYTICS_ACCESS':
      return 'Weekly analytics dashboard is only available for Premium users. Upgrade to track your progress.';
    case 'VIDEO_SUGGESTIONS':
      return 'AI-powered video and textbook suggestions are only available for Premium users. Upgrade for enhanced learning resources.';
    default:
      return 'Upgrade to Premium to unlock this feature.';
  }
}

/**
 * Check if user can access a feature
 */
export function canAccessFeature(isPremium: boolean, limitType: LimitType): boolean {
  if (isPremium) return true;

  const limits = LIMITS.FREE;

  switch (limitType) {
    case 'THEORY_QUESTIONS':
      return limits.THEORY_QUESTIONS_MAX > 0;
    case 'COMMUNITY_ENGAGEMENT':
      return limits.COMMUNITY_ENGAGEMENT;
    case 'ANALYTICS_ACCESS':
      return limits.ANALYTICS_ACCESS;
    case 'VIDEO_SUGGESTIONS':
      return limits.VIDEO_SUGGESTIONS;
    default:
      return true;
  }
}
