"""App settings for YouTube MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value.strip() == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _split_scopes(raw: str) -> list[str]:
    # Accept space or comma separated scopes
    parts = [p.strip() for p in raw.replace(",", " ").split()]
    return [p for p in parts if p]


@dataclass(frozen=True, slots=True)
class Settings:
    # MCP server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "9000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # OAuth / YouTube API
    # OAuth client data (required for OAuth flows, not for pure access-token usage)
    YOUTUBE_CLIENT_ID: str = os.getenv("YOUTUBE_CLIENT_ID", "")
    YOUTUBE_CLIENT_SECRET: str = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    YOUTUBE_REDIRECT_URI: str = os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost")
    YOUTUBE_SCOPES: list[str] = field(
        default_factory=lambda: _split_scopes(
            os.getenv(
                "YOUTUBE_SCOPES",
                "https://www.googleapis.com/auth/youtube.force-ssl",
            )
        )
    )

    # Optional token overrides
    YOUTUBE_ACCESS_TOKEN: str | None = os.getenv("YOUTUBE_ACCESS_TOKEN")
    YOUTUBE_REFRESH_TOKEN: str | None = os.getenv("YOUTUBE_REFRESH_TOKEN")
    YOUTUBE_ACCOUNT_ID: str | None = os.getenv("YOUTUBE_ACCOUNT_ID")

    # Token store
    TOKEN_STORE_PATH: Path = Path(os.getenv("TOKEN_STORE_PATH", ".tokens.json"))
    ACTIVE_ACCOUNT_PATH: Path = Path(
        os.getenv("ACTIVE_ACCOUNT_PATH", ".active_account")
    )

    # OAuth endpoints
    OAUTH_AUTH_URL: str = os.getenv(
        "OAUTH_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth"
    )
    OAUTH_TOKEN_URL: str = os.getenv(
        "OAUTH_TOKEN_URL", "https://oauth2.googleapis.com/token"
    )

    # API base URLs
    YOUTUBE_API_BASE_URL: str = os.getenv(
        "YOUTUBE_API_BASE_URL", "https://www.googleapis.com/youtube/v3"
    )
    YOUTUBE_UPLOAD_BASE_URL: str = os.getenv(
        "YOUTUBE_UPLOAD_BASE_URL", "https://www.googleapis.com/upload/youtube/v3"
    )

    # HTTP
    HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "30"))


settings = Settings()
