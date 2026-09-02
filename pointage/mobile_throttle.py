from rest_framework.throttling import AnonRateThrottle


class MobileLoginRateThrottle(AnonRateThrottle):
    """Limite les tentatives de connexion mobile pour réduire le brute-force."""

    scope = "mobile_login"
    rate = "5/minute"
