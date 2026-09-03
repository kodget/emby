from dataclasses import dataclass

# How many tokens equal 1 AI credit?
# We will round up. (e.g. 1500 tokens = 2 credits)
TOKENS_PER_CREDIT = 1000

@dataclass
class AIActionConfig:
    reserve_tokens: int
    category: str

    @property
    def reserve_credits(self) -> int:
        return max(1, (self.reserve_tokens + TOKENS_PER_CREDIT - 1) // TOKENS_PER_CREDIT)

# Estimated maximum tokens needed for reservation (to prevent negative balances)
AI_ACTIONS = {
    "CHAT": AIActionConfig(reserve_tokens=1000, category="INTERACTIVE"),
    "EXPLAIN_SELECTION": AIActionConfig(reserve_tokens=1000, category="INTERACTIVE"),
    "SUGGEST_RESOURCES": AIActionConfig(reserve_tokens=1000, category="INTERACTIVE"),
    "DASHBOARD_MESSAGE": AIActionConfig(reserve_tokens=1000, category="INTERACTIVE"),
    "GRADE_THEORY": AIActionConfig(reserve_tokens=1000, category="ASSESSMENT"),
    "GENERATE_FLASHCARDS": AIActionConfig(reserve_tokens=1000, category="GENERATION"),
    "STUDY_PLAN": AIActionConfig(reserve_tokens=1000, category="PLANNING"),
    "BRAIN_BATTLE": AIActionConfig(reserve_tokens=1000, category="INTERACTIVE"),
    "GENERATE_THEORY": AIActionConfig(reserve_tokens=1000, category="GENERATION"),
    "GENERATE_MCQ": AIActionConfig(reserve_tokens=1000, category="GENERATION"),
    "GENERATE_RESOURCES": AIActionConfig(reserve_tokens=1000, category="GENERATION"),
}

# Daily Allowances and Monthly Caps
CLASS_HEAD_DAILY_CREDITS = 150
CLASS_HEAD_MONTHLY_CAP = 4500

MATERIAL_UPLOADER_DAILY_CREDITS = 100
MATERIAL_UPLOADER_MONTHLY_CAP = 3000

PRO_DAILY_CREDITS = 60
PRO_MONTHLY_CAP = 1800

FREE_DAILY_CREDITS = 20
FREE_MONTHLY_CAP = 600

def get_action_reserve_credits(action: str) -> int:
    config = AI_ACTIONS.get(action)
    if not config:
        raise ValueError(f"Unknown AI action: {action}")
    return config.reserve_credits

def get_user_credit_tier(user):
    """
    Returns (daily_amount, monthly_cap, credit_source_choice, tier_name)
    Based on ClassRole and SubscriptionTier.
    """
    from accounts.models import SubscriptionTier, ClassRole
    from .models import CreditSource

    profile = getattr(user, "profile", None)
    if not profile:
        return (FREE_DAILY_CREDITS, FREE_MONTHLY_CAP, CreditSource.DAILY_FREE, "free")

    # Platinum check
    if profile.subscription_tier == SubscriptionTier.PLATINUM:
        return (999999, 999999, "PLATINUM", "platinum")

    # Class Head check (Receives 150 daily, 4500 monthly)
    if profile.class_role == ClassRole.CLASS_HEAD:
        return (CLASS_HEAD_DAILY_CREDITS, CLASS_HEAD_MONTHLY_CAP, CreditSource.DAILY_CLASS_HEAD, "class_head")

    # Material Uploader check (Receives 100 daily, 3000 monthly)
    capabilities = getattr(profile, "class_capabilities", []) or []
    if profile.class_role == ClassRole.MATERIAL_UPLOADER or "SLIDE_UPLOADER" in capabilities:
        return (MATERIAL_UPLOADER_DAILY_CREDITS, MATERIAL_UPLOADER_MONTHLY_CAP, CreditSource.DAILY_MATERIAL_UPLOADER, "material_uploader")

    # Premium check (Receives 60 daily, 1800 monthly)
    if profile.subscription_tier == SubscriptionTier.PREMIUM:
        return (PRO_DAILY_CREDITS, PRO_MONTHLY_CAP, CreditSource.DAILY_PRO, "premium")

    # Free student (Receives 20 daily, 600 monthly)
    return (FREE_DAILY_CREDITS, FREE_MONTHLY_CAP, CreditSource.DAILY_FREE, "free")
