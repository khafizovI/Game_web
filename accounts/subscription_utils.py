from django.utils import timezone

from .models import Profile, TeacherAIUsage
from .subscription_constants import SUBSCRIPTION_TIERS


def get_effective_tier(profile: Profile) -> str:
    tier = profile.subscription_tier or "free"
    if tier == "free":
        return "free"
    if profile.subscription_expires_at and profile.subscription_expires_at <= timezone.now():
        return "free"
    return tier


def get_tier_config(tier: str) -> dict:
    return SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["free"])


def get_daily_ai_limit(tier: str) -> int | None:
    return get_tier_config(tier).get("daily_ai_limit")


def get_today_usage_count(user) -> int:
    usage = TeacherAIUsage.objects.filter(user=user, date=timezone.localdate()).first()
    return usage.count if usage else 0


def get_ai_quota_status(user) -> dict:
    profile = user.profile
    tier = get_effective_tier(profile)
    tier_config = get_tier_config(tier)
    daily_limit = tier_config["daily_ai_limit"]
    used_today = get_today_usage_count(user)

    if daily_limit is None:
        remaining = None
        allowed = True
        limit_label = "unlimited"
    else:
        remaining = max(0, daily_limit - used_today)
        allowed = remaining > 0
        limit_label = str(daily_limit)

    return {
        "tier": tier,
        "tier_label": tier_config["label"],
        "daily_limit": daily_limit,
        "limit_label": limit_label,
        "used_today": used_today,
        "remaining": remaining,
        "allowed": allowed,
        "is_unlimited": daily_limit is None,
        "expires_at": profile.subscription_expires_at,
        "price_uzs": tier_config["price_uzs"],
    }


def check_ai_generation_allowed(user) -> tuple[bool, dict]:
    status = get_ai_quota_status(user)
    return status["allowed"], status


def record_ai_generation(user) -> None:
    today = timezone.localdate()
    usage, _ = TeacherAIUsage.objects.get_or_create(user=user, date=today, defaults={"count": 0})
    usage.count += 1
    usage.save(update_fields=["count"])


def activate_subscription(profile: Profile, tier: str, days: int | None = None) -> None:
    from datetime import timedelta
    from .subscription_constants import SUBSCRIPTION_DURATION_DAYS

    if tier not in SUBSCRIPTION_TIERS:
        raise ValueError(f"Unknown subscription tier: {tier}")

    duration = days if days is not None else SUBSCRIPTION_DURATION_DAYS
    now = timezone.now()
    base = profile.subscription_expires_at if (
        profile.subscription_expires_at and profile.subscription_expires_at > now
    ) else now

    profile.subscription_tier = tier
    if tier == "free":
        profile.subscription_expires_at = None
    else:
        profile.subscription_expires_at = base + timedelta(days=duration)
    profile.save(update_fields=["subscription_tier", "subscription_expires_at"])


def format_uzs_price(amount: int) -> str:
    if amount <= 0:
        return "0"
    return f"{amount:,}".replace(",", " ")
