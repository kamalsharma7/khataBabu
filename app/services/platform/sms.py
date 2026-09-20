from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def send_login_otp(settings: Settings, mobile: str, otp: str) -> None:
    """
    SMS delivery hook for future platform login OTP step.
    Production must integrate a provider (MSG91, Twilio, etc.).
    """
    if settings.is_production:
        logger.warning(
            "platform_otp_sms_not_configured",
            mobile_last4=mobile[-4:],
        )
        raise RuntimeError("SMS provider is not configured for production OTP delivery")

    logger.info(
        "platform_otp_sms_stub",
        mobile_last4=mobile[-4:],
        otp_length=len(otp),
    )
