import logging
from typing import Protocol

from cartag.config import Settings
from cartag.domain import mask_phone

log = logging.getLogger("cartag.sms")


class SmsProvider(Protocol):
    def send(self, to_e164: str, message: str) -> None:
        """Sends a text message to an E.164 number. Raises if the provider rejects it."""


class ConsoleSmsProvider:
    """Development provider: prints the message, OTP included, to the server log.

    Configuration refuses to start in production with this provider.
    """

    def send(self, to_e164: str, message: str) -> None:
        log.info("[sms:console] to %s: %s", mask_phone(to_e164), message)


def create_sms_provider(settings: Settings) -> SmsProvider:
    if settings.sms_provider == "console":
        return ConsoleSmsProvider()
    raise ValueError(f"Unknown SMS provider {settings.sms_provider}")
