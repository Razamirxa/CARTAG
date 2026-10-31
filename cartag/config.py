from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """All configuration comes from environment variables (or the .env file in the repo root).

    The app refuses to start if anything is missing or unsafe, so a bad deploy fails loudly
    instead of running half-configured.
    """

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", case_sensitive=False)

    app_env: Literal["development", "test", "production"] = "development"
    # Public address of the site. Printed into every QR code, so decide it BEFORE printing.
    public_base_url: str
    database_url: str
    session_secret: str = Field(min_length=32)
    otp_secret: str = Field(min_length=32)
    ip_hash_salt: str = Field(min_length=16)
    sms_provider: Literal["console"] = "console"
    # "none" means online payment is off and only cash on delivery is offered.
    # "mock" is a pretend provider for development and tests.
    payment_provider: Literal["none", "mock"] = "none"
    # Flat delivery charge in rupees, until the real delivery pricing is decided.
    shipping_fee_pkr: int = Field(default=0, ge=0, le=10_000)
    tag_code_length: int = Field(default=10, ge=8, le=24)
    qr_physical_size_mm: float = Field(default=25, ge=10, le=200)
    # Number of reverse proxies in front of the app (Nginx = 1). 0 when exposed directly.
    trust_proxy: int = Field(default=0, ge=0, le=5)
    # Folder with the built React app. The server serves it when it exists.
    web_dist_dir: Path = ROOT / "web" / "dist"

    @field_validator("public_base_url")
    @classmethod
    def _clean_base_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("must be a full URL such as https://example.com")
        return value.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def _sqlalchemy_url(cls, value: str) -> str:
        """Accepts postgresql://... (with an optional ?schema=public) and makes it a psycopg 3 URL."""
        parts = urlsplit(value)
        scheme = "postgresql+psycopg" if parts.scheme in {"postgresql", "postgres"} else parts.scheme
        # "schema" is not a libpq option and would be rejected by the driver.
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k != "schema"])
        return urlunsplit((scheme, parts.netloc, parts.path, query, ""))

    @model_validator(mode="after")
    def _production_rules(self) -> "Settings":
        if self.app_env == "production":
            if self.sms_provider == "console":
                raise ValueError("SMS_PROVIDER=console prints OTP codes to the log and is not allowed in production")
            if self.payment_provider == "mock":
                raise ValueError("PAYMENT_PROVIDER=mock is a pretend provider and is not allowed in production")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("PUBLIC_BASE_URL must be https in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def public_origin(self) -> str:
        parts = urlsplit(self.public_base_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def _cookie_prefix(self) -> str:
        # The __Host- prefix makes browsers refuse cookies that are not Secure, host-only and path=/.
        return "__Host-" if self.is_production else ""

    @property
    def session_cookie_name(self) -> str:
        return f"{self._cookie_prefix}st_session"

    @property
    def admin_cookie_name(self) -> str:
        return f"{self._cookie_prefix}st_admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
