PLAN_LIMITS = {
    "free": {
        "max_monitors": 5,
        "min_check_interval": 300,  # 5 minutes
        "retention_hours": 24,
        "features": {"email_alerts"},
    },
    "pro": {
        "max_monitors": 50,
        "min_check_interval": 60,  # 1 minute
        "retention_hours": 90 * 24,  # 90 days
        "features": {"email_alerts", "webhook_alerts", "custom_branding", "ssl_monitoring"},
    },
    "business": {
        "max_monitors": 999999,  # unlimited
        "min_check_interval": 30,  # 30 seconds
        "retention_hours": 365 * 24,  # 1 year
        "features": {
            "email_alerts", "webhook_alerts", "custom_branding",
            "ssl_monitoring", "custom_domain", "team_members", "api_access",
        },
    },
}


def get_plan_limits(plan: str) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
