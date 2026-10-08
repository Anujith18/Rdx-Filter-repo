"""Signed permanent stream/download links for private clone catalogues."""

import html
import logging
import math
import mimetypes
from urllib.parse import quote

from aiohttp import web
from pyrogram.file_id import FileId

from Deendayal_botz.Bot import work_loads
from Deendayal_botz.util.custom_dl import ByteStreamer
from info import URL
from .database import clone_db
from .manager import clone_manager
from .security import sign_media, valid_media_signature


logger = logging.getLogger(__name__)
streamers = {}


def drop_clone_streamer(bot_id):
    streamer = streamers.pop(f"clone:{int(bot_id)}", None)
    if streamer is not None:
        streamer.close()


def clone_stream_urls(bot_id, record_key, file_name):
    signature = sign_media(bot_id, record_key)
    safe_name = quote(str(file_name or "file"), safe="")
    base = str(URL).rstrip("/")
    watch = (
        f"{base}/clone/watch/{int(bot_id)}/{record_key}/"
        f"{signature}/{safe_name}"
    )
    download = (
        f"{base}/clone/file/{int(bot_id)}/{record_key}/"
        f"{signature}/{safe_name}"
    )
    return watch, download


async def _resolve(request):
    bot_id = int(request.match_info["bot_id"])
    record_key = request.match_info["record_key"]
    signature = request.match_info["signature"]
    if not valid_media_signature(bot_id, record_key, signature):
        raise web.HTTPForbidden(text="Invalid media signature.")
    record = await clone_db.get_media(bot_id, record_key)
    if not record:
        raise web.HTTPNotFound(text="File was not found.")
    client = clone_manager.clients.get(bot_id)
    if client is None:
        raise web.HTTPServiceUnavailable(text="Clone bot is offline.")

    file_id = record.get("file_id")
    try:
        source = await client.get_messages(
            int(record["source_chat_id"]),
            int(record["source_message_id"]),
        )
        media_type = getattr(
            getattr(source, "media", None),
            "value",
            getattr(source, "media", None),
        )
        media = getattr(source, str(media_type), None)
        if media and getattr(media, "file_id", None):
            file_id = media.file_id
    except Exception:
        logger.debug(
            "Using stored clone file reference for %s/%s",
            bot_id,
            record_key,
        )
    return bot_id, record, client, FileId.decode(file_id)


async def watch_clone_media(request):
    bot_id, record, _, _ = await _resolve(request)
    record_key = record["record_key"]
    file_name = html.escape(record.get("file_name") or "Telegram File")
    _, download = clone_stream_urls(bot_id, record_key, record.get("file_name"))
    signature = sign_media(bot_id, record_key)
    safe_name = quote(str(record.get("file_name") or "file"), safe="")
    source = (
        f"/clone/file/{bot_id}/{record_key}/{signature}/{safe_name}"
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{file_name}</title>
  <style>
    body {{ margin:0; background:#080808; color:#fff; font-family:system-ui;
            display:grid; min-height:100vh; place-items:center; }}
    main {{ width:min(1000px,94vw); }}
    video {{ width:100%; max-height:75vh; background:#000; border-radius:16px; }}
    a {{ display:inline-block; margin-top:18px; padding:14px 22px;
         border-radius:12px; background:#9b2f00; color:#fff;
         text-decoration:none; font-weight:700; }}
  </style>
</head>
<body><main>
  <h2>{file_name}</h2>
  <video controls playsinline src="{source}"></video>
  <br><a href="{html.escape(download)}">Download File</a>
</main></body>
</html>"""
    return web.Response(text=page, content_type="text/html")


async def stream_clone_media(request):
    bot_id, record, client, file_id = await _resolve(request)
    range_header = request.headers.get("Range")
    file_size = int(
        getattr(file_id, "file_size", 0)
        or record.get("file_size")
        or 0
    )
    if not file_size:
        raise web.HTTPNotFound(text="File size is unavailable.")

    if range_header:
        try:
            start_text, end_text = range_header.replace("bytes=", "").split(
                "-",
                1,
            )
            from_bytes = int(start_text or 0)
            until_bytes = int(end_text) if end_text else file_size - 1
        except (TypeError, ValueError):
            raise web.HTTPRequestRangeNotSatisfiable()
    else:
        from_bytes = 0
        until_bytes = file_size - 1

    if (
        from_bytes < 0
        or until_bytes < from_bytes
        or from_bytes >= file_size
    ):
        raise web.HTTPRequestRangeNotSatisfiable(
            headers={"Content-Range": f"bytes */{file_size}"}
        )
    until_bytes = min(until_bytes, file_size - 1)
    chunk_size = 1024 * 1024
    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1
    part_count = (
        math.ceil((until_bytes + 1) / chunk_size)
        - math.floor(offset / chunk_size)
    )
    request_length = until_bytes - from_bytes + 1

    stream_key = f"clone:{bot_id}"
    work_loads.setdefault(stream_key, 0)
    streamer = streamers.setdefault(stream_key, ByteStreamer(client))
    body = streamer.yield_file(
        file_id,
        stream_key,
        offset,
        first_part_cut,
        last_part_cut,
        part_count,
        chunk_size,
    )
    file_name = record.get("file_name") or "Telegram_File"
    mime_type = (
        record.get("mime_type")
        or getattr(file_id, "mime_type", None)
        or mimetypes.guess_type(file_name)[0]
        or "application/octet-stream"
    )
    disposition = (
        "attachment"
        if request.path.startswith("/clone/file/")
        else "inline"
    )
    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": mime_type,
            "Content-Range": (
                f"bytes {from_bytes}-{until_bytes}/{file_size}"
            ),
            "Content-Length": str(request_length),
            "Content-Disposition": (
                f"{disposition}; filename*=UTF-8''{quote(file_name)}"
            ),
            "Accept-Ranges": "bytes",
        },
    )
