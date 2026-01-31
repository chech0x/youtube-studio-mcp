---
name: youtube-streamings
description: Manage YouTube live broadcasts via the YouTube MCP: list completed and upcoming broadcasts, inspect a broadcast and its bound stream, schedule a new unlisted broadcast (optionally +N minutes from now), bind it to an existing stream to reuse connection parameters, list live chats for broadcasts, and update thumbnails from a local file or base64. Use when the user asks to view past transmissions, find upcoming/hidden scheduled events, schedule a new stream, reuse previous ingest settings, list chats, or set thumbnails.
---

# Youtube Streamings

## Overview

Use the YouTube MCP to query completed and upcoming broadcasts (including unlisted), reuse a previous stream’s ingest configuration, schedule new unlisted broadcasts, list live chats for broadcasts, and update thumbnails from a local path or base64 input.

## Concepts (Broadcast vs Live vs Chat)

- **Broadcast (Emisión / Evento programado)**: evento agendado con fecha/hora, título, miniatura y link fijo; puede existir sin estar transmitiendo.
- **Live (Transmisión en vivo)**: la emisión real cuando se hace clic en “Transmitir”; solo existe mientras estás en directo.
- **Chat**: pertenece al **Broadcast**; se crea al agendar el evento y se mantiene aunque reinicies OBS si usas el mismo Broadcast.

Resumen ultra corto: Broadcast → evento agendado; Live → transmisión en curso; Chat → del Broadcast.

## Quick Workflow (Typical “reuse previous config”)

1) List completed broadcasts (most recent first)
- `mcp__youtube-mcp__youtube_live_broadcasts_list_completed` with `max_results` (10–50).

2) Pick a broadcast to reuse
- Extract `id` and `contentDetails.boundStreamId` from the chosen broadcast.

3) Fetch details for accuracy and past config
- `mcp__youtube-mcp__youtube_live_broadcasts_get` with `part="snippet,contentDetails,status"`.
- `mcp__youtube-mcp__youtube_live_streams_get` with `part="snippet,cdn,contentDetails,status"` using the `boundStreamId`.
- Present the previous broadcast’s date/time and stream config (ingestion endpoints, resolution, frame rate) to guide the user.

4) Schedule a new unlisted broadcast
- Ask for title and description (empty is OK).
- If user says “+N minutes”, compute with `date -u` and add N minutes.
- Use `mcp__youtube-mcp__youtube_live_broadcasts_insert` with:
  - `privacy_status: "unlisted"`
  - `enable_auto_start: false` and `enable_auto_stop: false` unless user requests otherwise.
  - `scheduled_start_time` in RFC3339 UTC.

5) Bind to the previous stream to reuse ingest parameters
- `mcp__youtube-mcp__youtube_live_broadcasts_bind` with new `broadcast_id` and the previous `stream_id`.
- Confirm broadcast status is `ready` and report the stream key + ingest addresses.

## Tasks

### List Completed Broadcasts
- Tool: `mcp__youtube-mcp__youtube_live_broadcasts_list_completed`
- Inputs: `max_results`, optionally a channel id if required.
- Output: title, date/time, ID; ask if they want the next page if `nextPageToken` exists.

### List Upcoming Broadcasts (Scheduled/Unlisted)
- Tool: `mcp__youtube-mcp__youtube_live_broadcasts_list_upcoming`
- Inputs: `max_results`, optionally `channel_id`, optionally `page_token`.
- Output: title, scheduled time, privacy, ID, `liveChatId` if present.

### List Live Chats (by Broadcast Status)
- Tool: `mcp__youtube-mcp__youtube_live_chats_list`
- Inputs: `status` = `upcoming|active|completed`, optionally `channel_id`, optionally `page_token`.
- Output: broadcast + `liveChatId` for sending messages.

### Get Broadcast Details + Previous Config
- Tool: `mcp__youtube-mcp__youtube_live_broadcasts_get` for timestamps and bound stream.
- Tool: `mcp__youtube-mcp__youtube_live_streams_get` for ingest addresses, key, resolution/frame rate.
- Always show absolute UTC timestamps to avoid confusion.

### Schedule New Unlisted Broadcast (+N minutes)
- Use `date -u` to get current time and compute target start time.
- Insert with `mcp__youtube-mcp__youtube_live_broadcasts_insert`.
- If user wants “same parameters”, bind to previous stream after insert.

### Bind to Existing Stream
- Use `mcp__youtube-mcp__youtube_live_broadcasts_bind`.
- Confirm `boundStreamId` and report ingest endpoints + key for the user’s encoder.

### Update Thumbnail
- If local file path provided: call `mcp__youtube-mcp__youtube_thumbnails_set` directly.
- If image not local: ask for base64 (and its file type). Decode to a temp file (e.g., `/tmp/yt-thumb.png`) and upload.
- If the user is unsure, suggest “use the previous broadcast’s thumbnail or a new file path”.

### Send Live Chat Message
- Tool: `mcp__youtube-mcp__youtube_live_chat_messages_insert`
- Requires `live_chat_id` and `message_text`.
- Use the latest scheduled or live broadcast if the user does not specify which chat to use.

## Notes
- Prefer showing UTC and ask for local timezone if needed.
- Never fabricate stream keys or endpoints—only use returned MCP data.
- When reusing settings, explicitly mention the prior broadcast date/time and stream config before scheduling the new one.
- If a broadcast is “upcoming” and unlisted, use `list_upcoming` or `live_chats_list` to get its `liveChatId`.

## Current Account (session context)
- Active channel: (set at runtime)
- Channel ID: (set at runtime)
- Activated on: (set at runtime)

## Example Exercises (based on the session)
1) List completed broadcasts and pick the latest
- Use `mcp__youtube-mcp__youtube_live_broadcasts_list_completed` (`max_results: 10`).
- Identify the most recent broadcast and note its `id`.

2) Inspect the latest broadcast and its bound stream
- Call `mcp__youtube-mcp__youtube_live_broadcasts_get` to get `liveChatId`, times, and `boundStreamId`.
- Call `mcp__youtube-mcp__youtube_live_streams_get` to surface ingest endpoints, key, resolution, and frame rate.

3) Schedule a new unlisted broadcast +10 minutes (no auto-start/stop)
- Compute UTC start time with `date -u` and add 10 minutes.
- Call `mcp__youtube-mcp__youtube_live_broadcasts_insert` with:
  - `privacy_status: "unlisted"`
  - `enable_auto_start: false`
  - `enable_auto_stop: false`
  - `scheduled_start_time: <computed>`

4) Bind the new broadcast to the previous stream (reuse ingest settings)
- Call `mcp__youtube-mcp__youtube_live_broadcasts_bind` with the new `broadcast_id` and prior `stream_id`.

5) Update thumbnail from a local file path
- Use `mcp__youtube-mcp__youtube_thumbnails_set` with `video_id` and `file_path`.

6) Update thumbnail from base64 (if file not local)
- Ask user for base64 and file type.
- Decode to a temp file (e.g., `/tmp/yt-thumb.png`) and upload via `mcp__youtube-mcp__youtube_thumbnails_set`.

7) Monitor live chat (read-only)
- Fetch `liveChatId` from the broadcast.
- Use `mcp__youtube-mcp__youtube_live_chat_messages_list` with paging to poll.
- Note: `youtube_live_chat_messages_list` returns messages in chronological order (oldest to newest) within each page. To fetch all in order, paginate with `nextPageToken` and respect `pollingIntervalMillis`.

8) Send a chat message (write)
- Use `mcp__youtube-mcp__youtube_live_chat_messages_insert` with the `liveChatId`.

## Selection Guidance
- When the user asks to reuse settings, suggest the latest scheduled or currently-live broadcast if no specific ID/title is given.
- If multiple candidates exist, show a short list (title + UTC time + ID) and ask which to use.

## Future Enhancement (Optional)
- Add a tool "archivar chat" that walks all pages and returns the full chat ordered chronologically.
