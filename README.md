# youtube-mcp

![YouTube MCP](images/banner.png)

FastMCP server for YouTube Live workflows: list completed broadcasts, clone or create streams, bind broadcasts, upload thumbnails, and read live chat.

## Requirements

- Python 3.12
- `uv` (optional but recommended)

## Quick start

```bash
uv sync
cp .env.example .env  # create your env file
uv run python -m main
```

## OAuth setup

Set these in `.env`:

```
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REDIRECT_URI=http://localhost:9000/callback
YOUTUBE_SCOPES=https://www.googleapis.com/auth/youtube.force-ssl
```

Then use the MCP tool:

- `youtube_oauth_authorization_url`

After consent, Google redirects to `/callback` and the server **automatically stores tokens** in `.tokens.json` (configurable with `TOKEN_STORE_PATH`). Each entry includes user id/name, timestamps, and tokens. Active account is stored in `.active_account` (configurable with `ACTIVE_ACCOUNT_PATH`).

Important:
- This is **local/dev only** and uses **no additional security hardening** beyond file permissions.
- Multi-account support is **not intended for production** use.

## MCP tools (high level)

- `youtube_live_broadcasts_list_completed`
- `youtube_live_broadcasts_list_by_status`
- `youtube_live_broadcasts_list_upcoming`
- `youtube_live_chats_list`
- `youtube_live_broadcasts_get`
- `youtube_live_streams_get`
- `youtube_live_broadcasts_insert`
- `youtube_live_streams_insert`
- `youtube_live_broadcasts_bind`
- `youtube_thumbnails_set`
- `youtube_live_chat_messages_list`
- `youtube_live_chat_messages_insert`
- `youtube_accounts_list`
- `youtube_accounts_set_active`

## Input structure (named parameters)

All tools accept **named fields directly** (no extra `params` wrapper). Examples:

```json
{"max_results": 10, "page_token": "...", "channel_id": "UC..."}
```

```json
{"broadcast_id": "...", "part": "snippet,contentDetails,status"}
```

```json
{"title": "...", "scheduled_start_time": "2026-02-01T15:00:00Z", "privacy_status": "unlisted"}
```
