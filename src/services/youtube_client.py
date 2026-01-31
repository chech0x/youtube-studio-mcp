"""HTTP client wrapper for YouTube Data API v3."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from config.settings import settings
from services.oauth import refresh_access_token
from utils.token_store import (
    read_active_user,
    read_token_records,
    read_tokens,
    write_active_user,
    write_token_records,
    write_tokens,
)

logger = logging.getLogger("youtube-mcp.youtube_client")


class YouTubeClient:
    def __init__(self) -> None:
        self._base_url = settings.YOUTUBE_API_BASE_URL.rstrip("/")
        self._upload_url = settings.YOUTUBE_UPLOAD_BASE_URL.rstrip("/")
        self._timeout = settings.HTTP_TIMEOUT

    def _load_tokens(self) -> dict[str, Any]:
        # Prefer env overrides
        if settings.YOUTUBE_ACCESS_TOKEN or settings.YOUTUBE_REFRESH_TOKEN:
            tokens: dict[str, Any] = {}
            if settings.YOUTUBE_ACCESS_TOKEN:
                tokens["access_token"] = settings.YOUTUBE_ACCESS_TOKEN
            if settings.YOUTUBE_REFRESH_TOKEN:
                tokens["refresh_token"] = settings.YOUTUBE_REFRESH_TOKEN
            return tokens

        # New format: list of dicts
        records = read_token_records(settings.TOKEN_STORE_PATH)
        if records:
            active_id = settings.YOUTUBE_ACCOUNT_ID or read_active_user(
                settings.ACTIVE_ACCOUNT_PATH
            )
            if active_id:
                for record in records:
                    if record.get("user_id") == active_id:
                        return record
            return records[-1]

        # Legacy format: dict
        return read_tokens(settings.TOKEN_STORE_PATH)

    def _save_tokens(self, tokens: dict[str, Any]) -> None:
        # Legacy dict write for backward compatibility
        write_tokens(settings.TOKEN_STORE_PATH, tokens)

        # If list-of-dicts exists, update the latest record
        records = read_token_records(settings.TOKEN_STORE_PATH)
        if records:
            records[-1] = {**records[-1], **tokens}
            write_token_records(settings.TOKEN_STORE_PATH, records)
            user_id = records[-1].get("user_id")
            if user_id:
                write_active_user(settings.ACTIVE_ACCOUNT_PATH, user_id)

    async def _auth_headers(self) -> dict[str, str]:
        tokens = self._load_tokens()
        access_token = tokens.get("access_token")
        if not access_token:
            raise RuntimeError("Missing access token. Run OAuth flow first.")
        return {"Authorization": f"Bearer {access_token}"}

    async def _refresh_if_possible(self) -> Optional[str]:
        tokens = self._load_tokens()
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            return None
        refreshed = await refresh_access_token(refresh_token)
        access_token = refreshed.get("access_token")
        if access_token:
            self._save_tokens(refreshed)
        return access_token

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        base_url: str | None = None,
    ) -> Any:
        url = f"{(base_url or self._base_url)}/{path.lstrip('/')}"
        headers = await self._auth_headers()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method, url, params=params, json=json, headers=headers
            )

            if response.status_code == 401:
                refreshed = await self._refresh_if_possible()
                if refreshed:
                    headers["Authorization"] = f"Bearer {refreshed}"
                    response = await client.request(method, url, params=params, json=json, headers=headers)

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = response.text
                logger.error(
                    "YouTube API error %s for %s: %s",
                    response.status_code,
                    url,
                    detail,
                )
                raise RuntimeError(
                    f"YouTube API error {response.status_code}: {detail}"
                ) from exc

            return response.json()

    async def upload_thumbnail(self, video_id: str, file_path: str) -> Any:
        url = f"{self._upload_url}/thumbnails/set"
        params = {"videoId": video_id, "uploadType": "multipart"}
        headers = await self._auth_headers()
        with open(file_path, "rb") as handle:
            data = handle.read()

        def _files() -> dict[str, Any]:
            return {"media": (file_path, data, "application/octet-stream")}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url, params=params, headers=headers, files=_files()
            )

            if response.status_code == 401:
                refreshed = await self._refresh_if_possible()
                if refreshed:
                    headers["Authorization"] = f"Bearer {refreshed}"
                    response = await client.post(
                        url, params=params, headers=headers, files=_files()
                    )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = response.text
                logger.error(
                    "YouTube upload error %s for %s: %s",
                    response.status_code,
                    url,
                    detail,
                )
                raise RuntimeError(
                    f"YouTube upload error {response.status_code}: {detail}"
                ) from exc

            return response.json()


async def get_youtube_client() -> YouTubeClient:
    return YouTubeClient()
