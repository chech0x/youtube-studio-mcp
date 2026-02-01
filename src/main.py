"""FastMCP server for YouTube Live workflows."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from config.settings import settings
from services.oauth import (
    build_authorization_url,
    exchange_code_for_tokens,
    refresh_access_token,
)
from services.youtube_client import get_youtube_client
from utils.token_store import (
    read_active_user,
    read_token_records,
    write_active_user,
)

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("youtube-mcp")
logging.getLogger("fakeredis").setLevel(logging.WARNING)
logging.getLogger("redis").setLevel(logging.WARNING)
logging.getLogger("docket").setLevel(logging.WARNING)

mcp = FastMCP("YouTube-MCP")

# ASGI apps for uvicorn
http_app = mcp.http_app(transport="streamable-http")
sse_app = mcp.http_app(transport="sse")


@mcp.tool(name="youtube_oauth_authorization_url", description="Build OAuth consent URL")
async def youtube_oauth_authorization_url() -> dict[str, Any]:
    url = build_authorization_url()
    return {"authorization_url": url}


class OAuthExchangeParams(BaseModel):
    code: str = Field(..., description="Authorization code returned by Google")


@mcp.tool(
    name="youtube_oauth_exchange_code",
    description="Exchange OAuth code for tokens. Input: {\"code\":\"...\"}",
)
async def youtube_oauth_exchange_code(params: OAuthExchangeParams) -> dict[str, Any]:
    tokens = await exchange_code_for_tokens(params.code)
    return tokens


class OAuthRefreshParams(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")


@mcp.tool(
    name="youtube_oauth_refresh_token",
    description="Refresh access token. Input: {\"refresh_token\":\"...\"}",
)
async def youtube_oauth_refresh_token(params: OAuthRefreshParams) -> dict[str, Any]:
    tokens = await refresh_access_token(params.refresh_token)
    return tokens


@mcp.custom_route("/callback", methods=["GET"])
async def oauth_callback(request):
    """OAuth redirect endpoint to persist tokens."""
    from starlette.responses import JSONResponse

    code = request.query_params.get("code")
    error = request.query_params.get("error")

    if error:
        return JSONResponse({"status": "error", "error": error}, status_code=400)
    if not code:
        return JSONResponse({"status": "error", "error": "missing_code"}, status_code=400)

    try:
        tokens = await exchange_code_for_tokens(code)
        return JSONResponse({"status": "ok", "tokens": tokens}, status_code=200)
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)


class BroadcastsListCompletedParams(BaseModel):
    max_results: int = Field(10, description="Max results (1-50)")
    page_token: Optional[str] = Field(None, description="Page token")
    channel_id: Optional[str] = Field(
        None, description="Channel ID (optional, overrides stored user_id)"
    )


class BroadcastsListByStatusParams(BaseModel):
    broadcast_status: str = Field(
        ...,
        description="one of: completed | active | upcoming",
    )
    max_results: int = Field(10, description="Max results (1-50)")
    page_token: Optional[str] = Field(None, description="Page token")
    channel_id: Optional[str] = Field(
        None, description="Channel ID (optional, overrides stored user_id)"
    )


class BroadcastsListUpcomingParams(BaseModel):
    max_results: int = Field(10, description="Max results (1-50)")
    page_token: Optional[str] = Field(None, description="Page token")
    channel_id: Optional[str] = Field(
        None, description="Channel ID (optional, overrides stored user_id)"
    )


class LiveChatsListParams(BaseModel):
    status: str = Field(
        "upcoming",
        description="broadcast status to scan for chats: upcoming | active | completed",
    )
    max_results: int = Field(10, description="Max results (1-50)")
    page_token: Optional[str] = Field(None, description="Page token")
    channel_id: Optional[str] = Field(
        None, description="Channel ID (optional, overrides stored user_id)"
    )


@mcp.tool(
    name="youtube_live_broadcasts_list_completed",
    description=(
        "List completed live broadcasts using broadcastStatus=completed. "
        "Uses channelId if provided or inferred from stored tokens; does not send mine=true "
        "to avoid YouTube incompatible-parameters errors. "
        "Input: {\"max_results\":10,\"page_token\":\"...\",\"channel_id\":\"UC...\"}"
    ),
)
async def youtube_live_broadcasts_list_completed(
    params: BroadcastsListCompletedParams,
) -> dict[str, Any]:
    client = await get_youtube_client()
    if not params.channel_id:
        try:
            from utils.token_store import read_token_records

            records = read_token_records(settings.TOKEN_STORE_PATH)
            if records:
                params.channel_id = records[-1].get("user_id")
        except Exception:
            pass

    query = {
        "broadcastStatus": "completed",
        "part": "snippet,contentDetails,status",
        "maxResults": params.max_results,
    }
    if params.channel_id:
        query["channelId"] = params.channel_id
    if params.page_token:
        query["pageToken"] = params.page_token
    return await client.request("GET", "/liveBroadcasts", params=query)


@mcp.tool(
    name="youtube_live_broadcasts_list_by_status",
    description=(
        "List live broadcasts by status (active or upcoming; completed also allowed). "
        "Uses channelId if provided or inferred from stored tokens. "
        "Input: {\"broadcast_status\":\"active|upcoming|completed\",\"max_results\":10,"
        "\"page_token\":\"...\",\"channel_id\":\"UC...\"}"
    ),
)
async def youtube_live_broadcasts_list_by_status(
    params: BroadcastsListByStatusParams,
) -> dict[str, Any]:
    client = await get_youtube_client()
    if not params.channel_id:
        try:
            from utils.token_store import read_token_records

            records = read_token_records(settings.TOKEN_STORE_PATH)
            if records:
                params.channel_id = records[-1].get("user_id")
        except Exception:
            pass

    query = {
        "broadcastStatus": params.broadcast_status,
        "part": "snippet,contentDetails,status",
        "maxResults": params.max_results,
    }
    if params.channel_id:
        query["channelId"] = params.channel_id
    if params.page_token:
        query["pageToken"] = params.page_token
    return await client.request("GET", "/liveBroadcasts", params=query)


@mcp.tool(
    name="youtube_live_broadcasts_list_upcoming",
    description=(
        "List upcoming (not started) live broadcasts. "
        "Uses channelId if provided or inferred from stored tokens. "
        "Input: {\"max_results\":10,\"page_token\":\"...\",\"channel_id\":\"UC...\"}"
    ),
)
async def youtube_live_broadcasts_list_upcoming(
    params: BroadcastsListUpcomingParams,
) -> dict[str, Any]:
    client = await get_youtube_client()
    if not params.channel_id:
        try:
            from utils.token_store import read_token_records

            records = read_token_records(settings.TOKEN_STORE_PATH)
            if records:
                params.channel_id = records[-1].get("user_id")
        except Exception:
            pass

    query = {
        "broadcastStatus": "upcoming",
        "part": "snippet,contentDetails,status",
        "maxResults": params.max_results,
    }
    if params.channel_id:
        query["channelId"] = params.channel_id
    if params.page_token:
        query["pageToken"] = params.page_token
    return await client.request("GET", "/liveBroadcasts", params=query)


@mcp.tool(
    name="youtube_live_chats_list",
    description=(
        "List broadcasts that have liveChatId. Input: "
        "{\"status\":\"upcoming|active|completed\",\"max_results\":10,"
        "\"page_token\":\"...\",\"channel_id\":\"UC...\"}"
    ),
)
async def youtube_live_chats_list(params: LiveChatsListParams) -> dict[str, Any]:
    client = await get_youtube_client()
    if not params.channel_id:
        try:
            from utils.token_store import read_token_records

            records = read_token_records(settings.TOKEN_STORE_PATH)
            if records:
                params.channel_id = records[-1].get("user_id")
        except Exception:
            pass

    query = {
        "broadcastStatus": params.status,
        "part": "snippet,contentDetails,status",
        "maxResults": params.max_results,
    }
    if params.channel_id:
        query["channelId"] = params.channel_id
    if params.page_token:
        query["pageToken"] = params.page_token

    data = await client.request("GET", "/liveBroadcasts", params=query)
    items = data.get("items", []) if isinstance(data, dict) else []
    chats = []
    for item in items:
        snippet = item.get("snippet", {})
        live_chat_id = snippet.get("liveChatId")
        if live_chat_id:
            chats.append(
                {
                    "broadcast_id": item.get("id"),
                    "title": snippet.get("title"),
                    "scheduled_start_time": snippet.get("scheduledStartTime"),
                    "live_chat_id": live_chat_id,
                }
            )
    return {"items": chats, "pageInfo": data.get("pageInfo"), "nextPageToken": data.get("nextPageToken")}


class BroadcastGetParams(BaseModel):
    broadcast_id: str = Field(..., description="Broadcast ID")
    part: str = Field("snippet,contentDetails,status", description="Parts to retrieve")


@mcp.tool(
    name="youtube_live_broadcasts_get",
    description="Get a live broadcast by id. Input: {\"broadcast_id\":\"...\",\"part\":\"snippet,contentDetails,status\"}",
)
async def youtube_live_broadcasts_get(params: BroadcastGetParams) -> dict[str, Any]:
    client = await get_youtube_client()
    query = {"id": params.broadcast_id, "part": params.part}
    return await client.request("GET", "/liveBroadcasts", params=query)


class StreamsGetParams(BaseModel):
    stream_id: str = Field(..., description="Live stream ID")
    part: str = Field("snippet,cdn,contentDetails,status", description="Parts to retrieve")


@mcp.tool(
    name="youtube_live_streams_get",
    description="Get a live stream by id. Input: {\"stream_id\":\"...\",\"part\":\"snippet,cdn,contentDetails,status\"}",
)
async def youtube_live_streams_get(params: StreamsGetParams) -> dict[str, Any]:
    client = await get_youtube_client()
    query = {"id": params.stream_id, "part": params.part}
    return await client.request("GET", "/liveStreams", params=query)


class BroadcastInsertParams(BaseModel):
    title: str = Field(..., description="Broadcast title")
    scheduled_start_time: str = Field(
        ..., description="Scheduled start time (RFC3339)"
    )
    privacy_status: str = Field("private", description="public|unlisted|private")
    enable_auto_start: Optional[bool] = Field(None, description="Auto start")
    enable_auto_stop: Optional[bool] = Field(None, description="Auto stop")
    description: Optional[str] = Field(None, description="Broadcast description")
    request_body: Optional[dict[str, Any]] = Field(
        None, description="Raw request body (overrides other fields)"
    )


@mcp.tool(
    name="youtube_live_broadcasts_insert",
    description=(
        "Create a scheduled live broadcast. Input: "
        "{\"title\":\"...\",\"scheduled_start_time\":\"RFC3339\",\"privacy_status\":\"public|unlisted|private\","
        "\"enable_auto_start\":true,\"enable_auto_stop\":true,\"description\":\"...\"}"
    ),
)
async def youtube_live_broadcasts_insert(params: BroadcastInsertParams) -> dict[str, Any]:
    client = await get_youtube_client()

    if params.request_body:
        body = params.request_body
    else:
        body = {
            "snippet": {
                "title": params.title,
                "scheduledStartTime": params.scheduled_start_time,
            },
            "status": {"privacyStatus": params.privacy_status},
            "contentDetails": {},
        }
        if params.description:
            body["snippet"]["description"] = params.description
        if params.enable_auto_start is not None:
            body["contentDetails"]["enableAutoStart"] = params.enable_auto_start
        if params.enable_auto_stop is not None:
            body["contentDetails"]["enableAutoStop"] = params.enable_auto_stop

    query = {"part": "snippet,contentDetails,status"}
    return await client.request("POST", "/liveBroadcasts", params=query, json=body)


class StreamInsertParams(BaseModel):
    title: str = Field(..., description="Stream title")
    ingestion_type: str = Field("rtmp", description="rtmp|dash")
    resolution: Optional[str] = Field(None, description="720p|1080p|etc")
    frame_rate: Optional[str] = Field(None, description="30fps|60fps")
    is_reusable: Optional[bool] = Field(True, description="Reusable stream")
    request_body: Optional[dict[str, Any]] = Field(
        None, description="Raw request body (overrides other fields)"
    )


@mcp.tool(
    name="youtube_live_streams_insert",
    description=(
        "Create a live stream. Input: "
        "{\"title\":\"...\",\"ingestion_type\":\"rtmp\",\"resolution\":\"720p\",\"frame_rate\":\"30fps\","
        "\"is_reusable\":true}"
    ),
)
async def youtube_live_streams_insert(params: StreamInsertParams) -> dict[str, Any]:
    client = await get_youtube_client()

    if params.request_body:
        body = params.request_body
    else:
        cdn: dict[str, Any] = {"ingestionType": params.ingestion_type}
        if params.resolution:
            cdn["resolution"] = params.resolution
        if params.frame_rate:
            cdn["frameRate"] = params.frame_rate

        body = {
            "snippet": {"title": params.title},
            "cdn": cdn,
            "contentDetails": {"isReusable": params.is_reusable},
        }

    query = {"part": "snippet,cdn,contentDetails,status"}
    return await client.request("POST", "/liveStreams", params=query, json=body)


class BroadcastBindParams(BaseModel):
    broadcast_id: str = Field(..., description="Broadcast ID")
    stream_id: str = Field(..., description="Stream ID")


@mcp.tool(
    name="youtube_live_broadcasts_bind",
    description="Bind a broadcast to a stream. Input: {\"broadcast_id\":\"...\",\"stream_id\":\"...\"}",
)
async def youtube_live_broadcasts_bind(params: BroadcastBindParams) -> dict[str, Any]:
    client = await get_youtube_client()
    query = {
        "id": params.broadcast_id,
        "streamId": params.stream_id,
        "part": "snippet,contentDetails,status",
    }
    return await client.request("POST", "/liveBroadcasts/bind", params=query)


class ThumbnailSetParams(BaseModel):
    video_id: str = Field(..., description="Video ID (broadcastId for live)")
    file_path: str = Field(..., description="Path to thumbnail file")


@mcp.tool(
    name="youtube_thumbnails_set",
    description="Upload a thumbnail for a video. Input: {\"video_id\":\"...\",\"file_path\":\"/path/to.jpg\"}",
)
async def youtube_thumbnails_set(params: ThumbnailSetParams) -> dict[str, Any]:
    client = await get_youtube_client()
    return await client.upload_thumbnail(params.video_id, params.file_path)


class LiveChatListParams(BaseModel):
    live_chat_id: str = Field(..., description="Live chat ID")
    max_results: int = Field(200, description="Max results (1-200)")
    page_token: Optional[str] = Field(None, description="Page token")
    part: str = Field("snippet,authorDetails", description="Parts to retrieve")


@mcp.tool(
    name="youtube_live_chat_messages_list",
    description=(
        "List live chat messages. Input: "
        "{\"live_chat_id\":\"...\",\"max_results\":200,\"page_token\":\"...\",\"part\":\"snippet,authorDetails\"}"
    ),
)
async def youtube_live_chat_messages_list(params: LiveChatListParams) -> dict[str, Any]:
    client = await get_youtube_client()
    query = {
        "liveChatId": params.live_chat_id,
        "part": params.part,
        "maxResults": params.max_results,
    }
    if params.page_token:
        query["pageToken"] = params.page_token
    return await client.request("GET", "/liveChat/messages", params=query)


class LiveChatInsertParams(BaseModel):
    live_chat_id: str = Field(..., description="Live chat ID")
    message_text: str = Field(..., description="Message text")
    request_body: Optional[dict[str, Any]] = Field(
        None, description="Raw request body (overrides other fields)"
    )


@mcp.tool(
    name="youtube_live_chat_messages_insert",
    description=(
        "Send a live chat message. Input: "
        "{\"live_chat_id\":\"...\",\"message_text\":\"...\"}"
    ),
)
async def youtube_live_chat_messages_insert(
    params: LiveChatInsertParams,
) -> dict[str, Any]:
    client = await get_youtube_client()
    if params.request_body:
        body = params.request_body
    else:
        body = {
            "snippet": {
                "liveChatId": params.live_chat_id,
                "type": "textMessageEvent",
                "textMessageDetails": {"messageText": params.message_text},
            }
        }
    query = {"part": "snippet"}
    return await client.request("POST", "/liveChat/messages", params=query, json=body)


@mcp.tool(
    name="youtube_accounts_list",
    description="List stored YouTube accounts from token storage.",
)
async def youtube_accounts_list() -> dict[str, Any]:
    records = read_token_records(settings.TOKEN_STORE_PATH)
    active_id = read_active_user(settings.ACTIVE_ACCOUNT_PATH)
    data = []
    for record in records:
        data.append(
            {
                "user_id": record.get("user_id"),
                "user_name": record.get("user_name"),
                "channel_title": record.get("channel_title"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "active": record.get("user_id") == active_id,
            }
        )
    return {"accounts": data, "active_user_id": active_id}


class AccountsSetActiveParams(BaseModel):
    user_id: str = Field(..., description="Channel ID to set as active")


@mcp.tool(
    name="youtube_accounts_set_active",
    description="Set the active YouTube account by channel id. Input: {\"user_id\":\"UC...\"}",
)
async def youtube_accounts_set_active(params: AccountsSetActiveParams) -> dict[str, Any]:
    records = read_token_records(settings.TOKEN_STORE_PATH)
    if not any(record.get("user_id") == params.user_id for record in records):
        return {"status": "error", "error": "user_id_not_found"}
    write_active_user(settings.ACTIVE_ACCOUNT_PATH, params.user_id)
    return {"status": "ok", "active_user_id": params.user_id}


def main() -> None:  # pragma: no cover
    mcp.run(
        transport="streamable-http",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":  # pragma: no cover
    main()

__all__ = ["mcp", "main", "http_app", "sse_app"]
