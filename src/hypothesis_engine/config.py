"""Runtime configuration loaded from environment (never hardcode secrets)."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Official xAI OpenAI-compatible API root (override only if you know why).
DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"
_TRUSTED_XAI_HOSTS = frozenset({"api.x.ai"})


class Settings(BaseSettings):
    """Application settings.

    Values come from environment variables and optional `.env` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    xai_api_key: str | None = Field(default=None, validation_alias="XAI_API_KEY")
    xai_base_url: str = Field(
        default=DEFAULT_XAI_BASE_URL,
        validation_alias="XAI_BASE_URL",
    )
    xai_model: str = Field(default="grok-4.5", validation_alias="XAI_MODEL")

    def require_api_key(self) -> str:
        if not self.xai_api_key or not self.xai_api_key.strip():
            raise RuntimeError(
                "Missing XAI_API_KEY. Copy .env.example to .env and set your key, "
                "or export XAI_API_KEY. See getting-started.md."
            )
        return self.xai_api_key.strip()

    def endpoint_host(self) -> str:
        """Hostname of XAI_BASE_URL (empty string if unparseable)."""
        try:
            return (urlparse(self.xai_base_url.strip()).hostname or "").lower()
        except Exception:  # noqa: BLE001 — display helper only
            return ""

    def uses_trusted_xai_host(self) -> bool:
        """True when base URL points at the known xAI API host."""
        host = self.endpoint_host()
        return host in _TRUSTED_XAI_HOSTS


def get_settings() -> Settings:
    return Settings()
