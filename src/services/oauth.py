"""OAuth helpers for YouTube Data API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from config.settings import settings
from utils.token_store import (
    read_tokens,
    upsert_token_record,
    write_active_user,
    write_tokens,
)

logger = logging.getLogger("youtube-mcp.oauth")


def build_authorization_url(
    scopes: list[str] | None = None,
    state: str | None = None,
    access_type: str = "offline",
    prompt: str = "consent",
) -> str:
    if not settings.YOUTUBE_CLIENT_ID:
        raise RuntimeError("Missing YOUTUBE_CLIENT_ID for OAuth flow.")
    scopes = scopes or settings.YOUTUBE_SCOPES
    params = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": access_type,
        "prompt": prompt,
    }
    if state:
        params["state"] = state
    return f"{settings.OAUTH_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    if not settings.YOUTUBE_CLIENT_ID or not settings.YOUTUBE_CLIENT_SECRET:
        raise RuntimeError("Missing OAuth client credentials.")
    payload = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "client_secret": settings.YOUTUBE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
    }

    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        response = await client.post(settings.OAUTH_TOKEN_URL, data=payload)
        response.raise_for_status()
        tokens = response.json()

    await _persist_tokens(tokens)
    return tokens


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    if not settings.YOUTUBE_CLIENT_ID or not settings.YOUTUBE_CLIENT_SECRET:
        raise RuntimeError("Missing OAuth client credentials.")
    payload = {
        "client_id": settings.YOUTUBE_CLIENT_ID,
        "client_secret": settings.YOUTUBE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        response = await client.post(settings.OAUTH_TOKEN_URL, data=payload)
        response.raise_for_status()
        tokens = response.json()

    # Keep refresh token alongside new access token
    tokens["refresh_token"] = refresh_token
    await _persist_tokens(tokens)
    return tokens


async def _persist_tokens(tokens: dict[str, Any]) -> None:
    if not settings.TOKEN_STORE_PATH:
        return

    # Legacy dict storage (kept for backwards compatibility)
    existing = read_tokens(settings.TOKEN_STORE_PATH)
    if isinstance(existing, dict) and existing:
        merged = {**existing, **tokens}
        write_tokens(settings.TOKEN_STORE_PATH, merged)

    # Enrich with channel data and store as list-of-dicts record
    access_token = tokens.get("access_token")
    if not access_token:
        return

    channel_info = await _fetch_channel_info(access_token)
    record = {
        "user_id": channel_info.get("user_id"),
        "user_name": channel_info.get("user_name"),
        "channel_title": channel_info.get("channel_title"),
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "token_type": tokens.get("token_type"),
        "expires_in": tokens.get("expires_in"),
        "scopes": tokens.get("scope", "").split(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    upsert_token_record(settings.TOKEN_STORE_PATH, record, key="user_id")
    user_id = record.get("user_id")
    if user_id:
        write_active_user(settings.ACTIVE_ACCOUNT_PATH, user_id)


async def _fetch_channel_info(access_token: str) -> dict[str, str]:
    url = f"{settings.YOUTUBE_API_BASE_URL.rstrip('/')}/channels"
    params = {"part": "snippet", "mine": "true"}
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

    items = data.get("items", [])
    if not items:
        return {}

    channel = items[0]
    snippet = channel.get("snippet", {})
    return {
        "user_id": channel.get("id", ""),
        "user_name": snippet.get("customUrl", "") or snippet.get("title", ""),
        "channel_title": snippet.get("title", ""),
    }
