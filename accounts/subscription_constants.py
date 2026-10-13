"""Teacher subscription tiers for AI quiz generation."""

SUBSCRIPTION_TIERS = {
    "free": {
        "label": "Free",
        "daily_ai_limit": 1,
        "price_uzs": 0,
        "order": 0,
    },
    "pro": {
        "label": "Pro",
        "daily_ai_limit": 5,
        "price_uzs": 19999,
        "order": 1,
    },
    "premium": {
        "label": "Premium",
        "daily_ai_limit": 10,
        "price_uzs": 49999,
        "order": 2,
    },
    "vip": {
        "label": "VIP",
        "daily_ai_limit": None,
        "price_uzs": 99999,
        "order": 3,
    },
}

SUBSCRIPTION_DURATION_DAYS = 30
PAID_TIERS = ("pro", "premium", "vip")
