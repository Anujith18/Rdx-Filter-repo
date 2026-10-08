"""Handlers installed on every running clone client."""

import asyncio
import html
import ipaddress
import logging
import re
import socket
from datetime import timedelta

import aiohttp
from pyrogram import enums, filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from media_delivery import send_media_preserve_thumb
from .database import clone_db
from .manager import clone_manager
from .search import (
    apply_filter,
    clear_filters,
    readable_size,
    render_filter_menu,
    render_search,
    safe_edit,
)
from .security import CloneSecurityError, TokenCipher
from .streaming import clone_stream_urls
from .ui import (
    about_text,
    back_markup,
    delete_confirmation_markup,
    help_text,
    management_markup,
    mode_markup,
    monetization_markup,
    more_features_markup,
    start_config_markup,
    start_markup,
    start_text,
)


logger = logging.getLogger(__name__)
BACKGROUND_TASKS = set()
CIPHER = TokenCipher()


def background(coroutine):
    task = asyncio.create_task(coroutine)
    BACKGROUND_TASKS.add(task)
    task.add_done_callback(BACKGROUND_TASKS.discard)
    return task


def privileged(config, user_id):
    user_id = int(user_id)
    admins = {
        int(value)
        for value in config.get("settings", {}).get("admins", [])
        if str(value).lstrip("-").isdigit()
    }
    return user_id == int(config["owner_id"]) or user_id in admins


async def get_config(client):
    return await clone_db.get_clone(client.me.id)


async def send_log(client, config, text):
    log_channel = config.get("settings", {}).get("log_channel")
    if not log_channel:
        return
    try:
        await client.send_message(int(log_channel), text)
    except Exception:
        logger.warning("Clone %s log channel delivery failed.", client.me.id)


async def send_welcome(client, message, config):
    settings = config.get("settings", {})
    is_privileged = privileged(config, message.from_user.id)
    text = start_text(config, message.from_user)
    markup = start_markup(config, is_privileged)
    photo = settings.get("start_photo")
    if photo:
        try:
            return await message.reply_photo(
                photo,
                caption=text,
                reply_markup=markup,
            )
        except Exception:
            logger.warning(
                "Clone %s start poster failed; using text.",
                client.me.id,
            )
    return await message.reply_text(
        text,
        reply_markup=markup,
        disable_web_page_preview=True,
    )


async def force_subscription_markup(client, settings, user_id):
    missing = []
    for item in settings.get("force_sub_channels", []):
        try:
            channel_id = int(item["id"])
            member = await client.get_chat_member(channel_id, int(user_id))
            status = getattr(member, "status", None)
            if status in {
                enums.ChatMemberStatus.LEFT,
                enums.ChatMemberStatus.BANNED,
            }:
                missing.append(item)
        except Exception:
            missing.append(item)
    if not missing:
        return None
    rows = []
    for item in missing:
        url = item.get("url")
        if url:
            rows.append(
                [
                    InlineKeyboardButton(
                        item.get("name") or "📢 JOIN CHANNEL",
                        url=url,
                    )
                ]
            )
    rows.append(
        [
            InlineKeyboardButton(
                "🔄 TRY AGAIN",
                callback_data="cl:subcheck",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


async def ensure_subscribed(client, message, config):
    markup = await force_subscription_markup(
        client,
        config.get("settings", {}),
        message.from_user.id,
    )
    if markup is None:
        return True
    await message.reply_text(
        "<b>📢 Join the required channel(s), then try again.</b>",
        reply_markup=markup,
    )
    return False


async def shorten_url(settings, target):
    domain = re.sub(
        r"^https?://",
        "",
        str(settings.get("shortlink_domain") or "").strip(),
    ).strip("/")
    encrypted_api = settings.get("shortlink_api_encrypted")
    try:
        api_key = CIPHER.decrypt(encrypted_api) if encrypted_api else ""
    except CloneSecurityError:
        logger.error("Clone shortener API cannot be decrypted.")
        return target
    if not domain or not api_key:
        return target
    if not await public_hostname(domain):
        logger.warning("Rejected unsafe clone shortener host.")
        return target
    endpoint = f"https://{domain}/api"
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                endpoint,
                params={"api": api_key, "url": target},
            ) as response:
                payload = await response.json(content_type=None)
        if isinstance(payload, dict):
            return (
                payload.get("shortenedUrl")
                or payload.get("shortened_url")
                or payload.get("url")
                or target
            )
    except Exception:
        logger.warning("Clone shortener failed; using direct verification link.")
    return target


async def public_hostname(domain):
    hostname = str(domain or "").split(":", 1)[0].strip().lower()
    if not hostname or hostname == "localhost" or hostname.endswith(".local"):
        return False
    try:
        literal = ipaddress.ip_address(hostname)
        return literal.is_global
    except ValueError:
        pass
    try:
        loop = asyncio.get_running_loop()
        results = await loop.getaddrinfo(
            hostname,
            443,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
        addresses = {
            ipaddress.ip_address(item[4][0])
            for item in results
        }
        return bool(addresses) and all(address.is_global for address in addresses)
    except Exception:
        return False


def format_caption(config, record):
    settings = config.get("settings", {})
    template = settings.get("custom_caption") or "{file_name}"
    values = {
        "file_name": html.escape(record.get("file_name") or "Telegram File"),
        "file_size": readable_size(record.get("file_size")),
        "file_caption": html.escape(record.get("caption") or ""),
        "bot_name": html.escape(config.get("name") or "RDX Clone Bot"),
    }
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return values["file_name"]


async def delete_later(delay, *messages):
    await asyncio.sleep(max(1, int(delay)))
    for message in messages:
        try:
            await message.delete()
        except Exception:
            pass


async def verification_required(client, message, config, record):
    settings = config.get("settings", {})
    token = await clone_db.create_verification(
        client.me.id,
        message.from_user.id,
        record["record_key"],
        settings.get("verify_token_minutes", 15),
    )
    target = (
        f"https://t.me/{client.me.username}?start=cv_{token}"
    )
    verify_url = await shorten_url(settings, target)
    rows = [[InlineKeyboardButton("✅ VERIFY NOW", url=verify_url)]]
    tutorial = settings.get("tutorial_url")
    if tutorial:
        rows.append(
            [InlineKeyboardButton("🎥 HOW TO VERIFY", url=tutorial)]
        )
    await message.reply_text(
        "<b>⚡ QUICK VERIFICATION REQUIRED</b>\n\n"
        "To download your requested file, complete one quick verification.\n\n"
        f"The link expires in {int(settings.get('verify_token_minutes', 15))} minutes.",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def deliver_file(client, message, config, record, verified=False):
    if not await ensure_subscribed(client, message, config):
        return
    settings = config.get("settings", {})
    user_id = message.from_user.id
    premium = await clone_db.is_premium(client.me.id, user_id)
    if (
        settings.get("verification")
        and not privileged(config, user_id)
        and not premium
        and not verified
        and not await clone_db.is_verified(client.me.id, user_id)
    ):
        return await verification_required(client, message, config, record)

    delivery_record = dict(record)
    custom_thumbnail = settings.get("fallback_thumbnail")
    if custom_thumbnail:
        # A clone owner's explicit custom thumbnail overrides source-copy mode.
        # Without this setting, the original source message is still copied for
        # the highest available Telegram thumbnail quality.
        delivery_record["source_chat_id"] = None
        delivery_record["source_message_id"] = None
        delivery_record["thumb_file_id"] = custom_thumbnail

    rows = []
    if settings.get("stream_mode"):
        watch, download = clone_stream_urls(
            client.me.id,
            record["record_key"],
            record.get("file_name"),
        )
        rows.append(
            [
                InlineKeyboardButton("🍿 STREAM", url=watch),
                InlineKeyboardButton("📂 DOWNLOAD", url=download),
            ]
        )
    custom_text = settings.get("custom_button_text")
    custom_url = settings.get("custom_button_url")
    if custom_text and custom_url:
        rows.append([InlineKeyboardButton(custom_text, url=custom_url)])
    reply_markup = InlineKeyboardMarkup(rows) if rows else None
    sent = await send_media_preserve_thumb(
        client,
        chat_id=message.chat.id,
        file_id=record["file_id"],
        media_record=delivery_record,
        caption=format_caption(config, record),
        protect_content=bool(settings.get("protect_content")),
        reply_markup=reply_markup,
    )
    await send_log(
        client,
        config,
        "<b>#CloneFileDelivered</b>\n\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"📁 File: {html.escape(record.get('file_name') or 'Telegram File')}",
    )
    if settings.get("auto_delete"):
        seconds = max(60, int(settings.get("delete_time", 600)))
        notice = await message.reply_text(
            "<b>⚠️ IMPORTANT NOTICE</b>\n\n"
            f"This file will be deleted in {seconds // 60 or 1} minute(s).\n"
            "Forward it to Saved Messages before it expires."
        )
        background(delete_later(seconds, sent, notice))
    return sent


async def clone_start(client, message):
    config = await get_config(client)
    if not config or not message.from_user:
        return
    new_user = await clone_db.add_user(client.me.id, message.from_user)
    if new_user:
        await send_log(
            client,
            config,
            "<b>#CloneNewUser</b>\n\n"
            f"👤 {message.from_user.mention}\n"
            f"🆔 <code>{message.from_user.id}</code>",
        )
    payload = message.command[1] if len(message.command) > 1 else ""
    if payload.startswith("cf_"):
        record = await clone_db.get_media(client.me.id, payload[3:])
        if not record:
            return await message.reply_text("<b>File not found.</b>")
        return await deliver_file(client, message, config, record)
    if payload.startswith("cv_"):
        item = await clone_db.consume_verification(
            client.me.id,
            message.from_user.id,
            payload[3:],
        )
        if not item:
            return await message.reply_text(
                "<b>This verification link is invalid, expired or already used.</b>"
            )
        await clone_db.grant_verified_access(
            client.me.id,
            message.from_user.id,
            config.get("settings", {}).get("verify_access_hours", 24),
        )
        record = await clone_db.get_media(
            client.me.id,
            item["record_key"],
        )
        await message.reply_text(
            "<b>✅ Verification completed successfully.</b>"
        )
        if record:
            return await deliver_file(
                client,
                message,
                config,
                record,
                verified=True,
            )
        return
    if payload.startswith("ref_"):
        try:
            inviter_id = int(payload[4:])
        except ValueError:
            inviter_id = 0
        if inviter_id:
            points = await clone_db.add_referral(
                client.me.id,
                inviter_id,
                message.from_user.id,
            )
            if points and points % 100 == 0:
                await clone_db.add_premium(client.me.id, inviter_id, 30)
                try:
                    await client.send_message(
                        inviter_id,
                        "<b>🎉 You earned 30 days of Premium from referrals!</b>",
                    )
                except Exception:
                    pass
    return await send_welcome(client, message, config)


async def owner_command(client, message):
    config = await get_config(client)
    if (
        not config
        or not message.from_user
        or not privileged(config, message.from_user.id)
    ):
        return
    command = (message.command or [""])[0].lower()
    if command == "settings":
        return await message.reply_text(
            "<b>🔧 MANAGE YOUR CLONE BOT</b>",
            reply_markup=management_markup(),
        )
    if command == "status":
        return await send_status(client, message, config)
    if command == "addpremium":
        if len(message.command) < 3:
            return await message.reply_text(
                "<code>/addpremium USER_ID DAYS</code>"
            )
        try:
            expires = await clone_db.add_premium(
                client.me.id,
                int(message.command[1]),
                int(message.command[2]),
            )
        except ValueError:
            return await message.reply_text("Invalid user ID or days.")
        return await message.reply_text(
            f"<b>✅ Premium added until {expires:%Y-%m-%d %H:%M UTC}</b>"
        )
    if command == "removepremium":
        if len(message.command) < 2:
            return await message.reply_text(
                "<code>/removepremium USER_ID</code>"
            )
        try:
            await clone_db.remove_premium(
                client.me.id,
                int(message.command[1]),
            )
        except ValueError:
            return await message.reply_text("Invalid user ID.")
        return await message.reply_text("<b>✅ Premium removed.</b>")
    if command == "index":
        if len(message.command) < 3:
            return await message.reply_text(
                "<b>Bulk index format:</b>\n"
                "<code>/index CHANNEL_ID LAST_MESSAGE_ID</code>\n\n"
                "Make the clone bot an admin in that channel first."
            )
        try:
            channel_id = int(message.command[1])
            last_message_id = int(message.command[2])
        except ValueError:
            return await message.reply_text("Invalid channel or message ID.")
        settings = config.get("settings", {})
        channels = list(settings.get("index_channels", []))
        if channel_id not in channels:
            channels.append(channel_id)
            await clone_db.update_settings(
                client.me.id,
                {"index_channels": channels},
            )
        progress = await message.reply_text("<b>⏳ Indexing started...</b>")
        background(
            bulk_index(
                client,
                channel_id,
                last_message_id,
                progress,
            )
        )


async def bulk_index(client, channel_id, last_message_id, progress):
    saved = duplicate = skipped = 0
    try:
        for start in range(1, int(last_message_id) + 1, 200):
            ids = list(range(start, min(start + 200, last_message_id + 1)))
            messages = await client.get_messages(channel_id, ids)
            for message in messages:
                if not message or getattr(message, "empty", False):
                    skipped += 1
                    continue
                media_type = getattr(
                    getattr(message, "media", None),
                    "value",
                    getattr(message, "media", None),
                )
                media = getattr(message, str(media_type), None)
                if media_type not in {"document", "video", "audio"} or not media:
                    skipped += 1
                    continue
                before = await clone_db.get_media(
                    client.me.id,
                    clone_db.media_key(client.me.id, media.file_id),
                )
                await clone_db.save_media(
                    client.me.id,
                    media,
                    message,
                    file_type=media_type,
                )
                if before:
                    duplicate += 1
                else:
                    saved += 1
            await progress.edit_text(
                "<b>⏳ INDEXING...</b>\n\n"
                f"Processed: {min(start + 199, last_message_id)}\n"
                f"Saved: {saved}\n"
                f"Duplicates: {duplicate}\n"
                f"Skipped: {skipped}"
            )
        await progress.edit_text(
            "<b>✅ INDEXING COMPLETED</b>\n\n"
            f"Saved: {saved}\nDuplicates: {duplicate}\nSkipped: {skipped}"
        )
    except Exception as error:
        logger.exception("Clone bulk indexing failed")
        await progress.edit_text(
            f"<b>❌ INDEXING FAILED</b>\n\n<code>{html.escape(str(error))}</code>"
        )


async def channel_media(client, message):
    config = await get_config(client)
    if not config:
        return
    settings = config.get("settings", {})
    chat_id = int(message.chat.id)
    media_type = getattr(
        getattr(message, "media", None),
        "value",
        getattr(message, "media", None),
    )
    media = getattr(message, str(media_type), None)
    if not media or media_type not in {"document", "video", "audio"}:
        return
    if chat_id in settings.get("delete_channels", []):
        await clone_db.delete_media_by_file_id(client.me.id, media.file_id)
        return
    if chat_id not in settings.get("index_channels", []):
        return
    record_key = clone_db.media_key(client.me.id, media.file_id)
    existed = await clone_db.get_media(client.me.id, record_key)
    await clone_db.save_media(
        client.me.id,
        media,
        message,
        file_type=media_type,
    )
    if not existed:
        await send_log(
            client,
            config,
            "<b>#CloneFileIndexed</b>\n\n"
            f"📁 {html.escape(getattr(media, 'file_name', None) or 'Telegram File')}\n"
            f"📢 Channel: <code>{chat_id}</code>\n"
            f"🔑 Record: <code>{record_key}</code>",
        )


async def clone_text_search(client, message):
    if not message.from_user or not message.text:
        return
    if message.text.startswith(("/", "#")):
        return
    config = await get_config(client)
    if not config:
        return
    settings = config.get("settings", {})
    if not settings.get("auto_filter", True):
        return
    if (
        message.chat.type == enums.ChatType.PRIVATE
        and not settings.get("pm_search", True)
    ):
        return await message.reply_text(
            "<b>Private search is disabled by the clone owner.</b>"
        )
    if (
        message.chat.type in {
            enums.ChatType.GROUP,
            enums.ChatType.SUPERGROUP,
        }
        and not settings.get("group_search", True)
    ):
        return
    new_user = await clone_db.add_user(client.me.id, message.from_user)
    if new_user:
        await send_log(
            client,
            config,
            "<b>#CloneNewUser</b>\n\n"
            f"👤 {message.from_user.mention}\n"
            f"🆔 <code>{message.from_user.id}</code>",
        )
    await render_search(
        client,
        message,
        message.text,
        requester_id=message.from_user.id,
    )


async def send_status(client, target, config=None):
    config = config or await get_config(client)
    media = await clone_db.media_count(client.me.id)
    users = await clone_db.user_count(client.me.id)
    uptime = timedelta(seconds=clone_manager.uptime(client.me.id))
    settings = config.get("settings", {})
    text = (
        "<b>📊 BOT STATUS</b>\n\n"
        f"<blockquote>🤖 Bot: @{html.escape(client.me.username or '')}\n"
        f"🟢 Runtime: {'ONLINE' if clone_manager.is_running(client.me.id) else 'OFFLINE'}\n"
        f"⏱ Uptime: {uptime}\n"
        f"🎬 Indexed Files: {media}\n"
        f"👥 Users: {users}\n"
        f"📥 PM Search: {'ON' if settings.get('pm_search') else 'OFF'}\n"
        f"👥 Group Search: {'ON' if settings.get('group_search') else 'OFF'}</blockquote>"
    )
    if hasattr(target, "edit_text"):
        return await safe_edit(target, text, back_markup("panel"))
    return await target.reply_text(text, reply_markup=back_markup("panel"))


INPUT_HELP = {
    "start": (
        "<b>Send the new English start message.</b>\n\n"
        "Available: <code>{user}</code>, <code>{bot_name}</code>, "
        "<code>{bot_username}</code>"
    ),
    "poster": "<b>Send a photo, image URL, Telegram file ID, or <code>off</code>.</b>",
    "log": "<b>Send the log channel ID, for example <code>-1001234567890</code>, or <code>off</code>.</b>",
    "index": "<b>Send one or more index channel IDs separated by spaces.</b>",
    "admins": "<b>Send admin user IDs separated by spaces.</b>",
    "button": "<b>Send <code>BUTTON TEXT | https://example.com</code>, or <code>off</code>.</b>",
    "caption": (
        "<b>Send the custom file caption.</b>\n\n"
        "Available: <code>{file_name}</code>, <code>{file_size}</code>, "
        "<code>{file_caption}</code>, <code>{bot_name}</code>"
    ),
    "fsub": (
        "<b>Send one channel per line:</b>\n"
        "<code>-1001234567890|https://t.me/channel</code>\n\n"
        "Send <code>off</code> to remove all."
    ),
    "thumb": "<b>Send a photo, thumbnail file ID, URL, or <code>off</code>.</b>",
    "dtime": "<b>Send auto-delete time in seconds (minimum 60).</b>",
    "short": "<b>Send <code>shortener-domain.com API_KEY</code>, or <code>off</code>.</b>",
    "tutorial": "<b>Send the verification tutorial URL, or <code>off</code>.</b>",
    "updates": "<b>Send the updates channel URL, or <code>off</code>.</b>",
    "support": "<b>Send the support chat URL, or <code>off</code>.</b>",
}


async def pending_input(client, message):
    if not message.from_user:
        return
    action = clone_manager.pop_pending_input(client.me.id, message.from_user.id)
    if not action:
        return
    config = await get_config(client)
    if not config or not privileged(config, message.from_user.id):
        return
    if message.text and message.text.lower() == "/cancel":
        await message.reply_text("<b>Cancelled.</b>")
        message.stop_propagation()
        return
    try:
        updates = parse_setting_input(action, message)
        await clone_db.update_settings(client.me.id, updates)
        await client.send_message(
            message.chat.id,
            "<b>✅ Setting updated successfully.</b>",
            reply_markup=management_markup(),
        )
    except ValueError as error:
        # Keep the prompt active so a typo can be corrected without reopening
        # the entire Settings menu.
        clone_manager.set_pending_input(
            client.me.id,
            message.from_user.id,
            action,
        )
        await client.send_message(
            message.chat.id,
            f"<b>❌ {html.escape(str(error))}</b>\n\n"
            f"{INPUT_HELP.get(action, '')}"
        )
    if action == "short":
        try:
            await message.delete()
        except Exception:
            pass
    message.stop_propagation()


def _ids(text):
    values = []
    for value in str(text or "").replace(",", " ").split():
        if not value.lstrip("-").isdigit():
            raise ValueError(f"Invalid numeric ID: {value}")
        values.append(int(value))
    return list(dict.fromkeys(values))


def _photo_or_text(message):
    if message.photo:
        return message.photo.file_id
    return str(message.text or message.caption or "").strip()


def parse_setting_input(action, message):
    text = str(message.text or message.caption or "").strip()
    off = text.lower() in {"off", "none", "remove", "delete"}
    if action == "start":
        if not text:
            raise ValueError("Start message cannot be empty.")
        return {"start_message": text}
    if action == "poster":
        value = "" if off else _photo_or_text(message)
        if not value and not off:
            raise ValueError("Send a photo, URL or file ID.")
        return {"start_photo": value}
    if action == "log":
        return {"log_channel": None if off else _ids(text)[0]}
    if action == "index":
        return {"index_channels": [] if off else _ids(text)}
    if action == "admins":
        return {"admins": [] if off else _ids(text)}
    if action == "button":
        if off:
            return {"custom_button_text": "", "custom_button_url": ""}
        if "|" not in text:
            raise ValueError("Separate button text and URL with |.")
        label, url = [part.strip() for part in text.split("|", 1)]
        if not label or not re.match(r"^https?://", url):
            raise ValueError("Button text or URL is invalid.")
        return {"custom_button_text": label[:64], "custom_button_url": url}
    if action == "caption":
        if not text:
            raise ValueError("Caption cannot be empty.")
        return {"custom_caption": text}
    if action == "fsub":
        if off:
            return {"force_sub_channels": []}
        channels = []
        for line in text.splitlines():
            parts = [part.strip() for part in line.split("|", 1)]
            if len(parts) != 2 or not parts[0].lstrip("-").isdigit():
                raise ValueError("Force-subscribe line format is invalid.")
            if not re.match(r"^https?://", parts[1]):
                raise ValueError("Force-subscribe URL is invalid.")
            channels.append(
                {
                    "id": int(parts[0]),
                    "url": parts[1],
                    "name": "📢 JOIN CHANNEL",
                }
            )
        return {"force_sub_channels": channels}
    if action == "thumb":
        value = "" if off else _photo_or_text(message)
        if not value and not off:
            raise ValueError("Send a photo, URL or file ID.")
        return {"fallback_thumbnail": value}
    if action == "dtime":
        try:
            seconds = int(text)
        except ValueError as error:
            raise ValueError("Auto-delete time must be a number.") from error
        if not 60 <= seconds <= 86400:
            raise ValueError("Choose a value between 60 and 86400 seconds.")
        return {"delete_time": seconds}
    if action == "short":
        if off:
            return {
                "shortlink_domain": "",
                "shortlink_api_encrypted": "",
            }
        parts = text.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError("Send shortener domain and API key.")
        domain = re.sub(r"^https?://", "", parts[0]).strip("/")
        if not re.fullmatch(r"[A-Za-z0-9.-]+(?::\d{1,5})?", domain):
            raise ValueError("Shortener domain is invalid.")
        return {
            "shortlink_domain": domain,
            "shortlink_api_encrypted": CIPHER.encrypt(parts[1].strip()),
        }
    if action == "tutorial":
        if off:
            return {"tutorial_url": ""}
        if not re.match(r"^https?://", text):
            raise ValueError("Tutorial URL is invalid.")
        return {"tutorial_url": text}
    if action in {"updates", "support"}:
        if off:
            return {f"{action}_url": ""}
        if not re.match(r"^https?://", text):
            raise ValueError(f"{action.title()} URL is invalid.")
        return {f"{action}_url": text}
    raise ValueError("Unknown setting.")


async def clone_callback(client, query):
    data = query.data or ""
    config = await get_config(client)
    if not config:
        return await query.answer("Clone configuration is unavailable.", show_alert=True)
    if not data.startswith("cl:edit:"):
        # Navigating away from an edit prompt must not consume the owner's
        # next ordinary search message as a setting value.
        clone_manager.clear_pending_input(
            client.me.id,
            query.from_user.id,
        )

    if data == "cl:noop":
        return await query.answer()
    if data.startswith(("cl:sp:", "cl:sm:", "cl:sf:", "cl:sx:")):
        parts = data.split(":")
        session_key = parts[2]
        session = clone_manager.get_search_session(session_key)
        if not session:
            return await query.answer("Search expired. Search again.", show_alert=True)
        if int(session["user_id"]) != int(query.from_user.id):
            return await query.answer(
                "This is not your search request.",
                show_alert=True,
            )
        await query.answer()
        if data.startswith("cl:sp:"):
            return await render_search(
                client,
                query.message,
                session["query"],
                requester_id=session["user_id"],
                session_key=session_key,
                offset=int(parts[3]),
                edit=True,
            )
        if data.startswith("cl:sm:"):
            return await render_filter_menu(
                client,
                query.message,
                session_key,
                parts[3],
            )
        if data.startswith("cl:sf:"):
            return await apply_filter(
                client,
                query.message,
                session_key,
                parts[3],
                parts[4],
            )
        return await clear_filters(client, query.message, session_key)

    if data == "cl:home":
        await query.answer()
        return await safe_edit(
            query.message,
            start_text(config, query.from_user),
            start_markup(config, privileged(config, query.from_user.id)),
        )
    if data == "cl:help":
        await query.answer()
        return await safe_edit(
            query.message,
            help_text(config),
            back_markup("home"),
        )
    if data == "cl:about":
        await query.answer()
        return await safe_edit(
            query.message,
            about_text(config),
            back_markup("home"),
        )
    if data == "cl:subcheck":
        markup = await force_subscription_markup(
            client,
            config.get("settings", {}),
            query.from_user.id,
        )
        return await query.answer(
            (
                "✅ Subscription confirmed. Tap the file link again."
                if markup is None
                else "Join every required channel."
            ),
            show_alert=markup is not None,
        )

    if not privileged(config, query.from_user.id):
        return await query.answer(
            "Only the clone owner or an authorized admin can use this.",
            show_alert=True,
        )
    await query.answer()
    settings = config.get("settings", {})

    if data == "cl:panel":
        return await safe_edit(
            query.message,
            "<b>🔧 MANAGE YOUR CLONE BOT</b>\n\n"
            f"<blockquote>🤖 @{html.escape(config.get('username') or '')}\n"
            "Select a setting below.</blockquote>",
            management_markup(),
        )
    if data == "cl:startcfg":
        return await safe_edit(
            query.message,
            "<b>📝 START MESSAGE & DESIGN</b>",
            start_config_markup(),
        )
    if data == "cl:mon":
        return await safe_edit(
            query.message,
            "<b>💵 MONETIZATION</b>\n\n"
            "Configure verification, shortlinks, premium and referrals.",
            monetization_markup(settings),
        )
    if data == "cl:more":
        return await safe_edit(
            query.message,
            "<b>🔎 MORE FEATURES</b>",
            more_features_markup(settings),
        )
    if data == "cl:mode":
        return await safe_edit(
            query.message,
            "<b>🛍 BOT MODE</b>\n\nChoose where users can search.",
            mode_markup(settings),
        )
    if data == "cl:status":
        return await send_status(client, query.message, config)
    if data == "cl:premiumhelp":
        return await safe_edit(
            query.message,
            "<b>💎 PREMIUM MANAGEMENT</b>\n\n"
            "<code>/addpremium USER_ID DAYS</code>\n"
            "<code>/removepremium USER_ID</code>\n\n"
            "Premium users bypass clone verification.",
            back_markup("mon"),
        )
    if data == "cl:refer":
        link = f"https://t.me/{client.me.username}?start=ref_{query.from_user.id}"
        return await safe_edit(
            query.message,
            "<b>🌍 REFER AND EARN</b>\n\n"
            "Share your referral link. Every successful referral earns 10 points; "
            "100 points grants 30 days of Premium.\n\n"
            f"<code>{html.escape(link)}</code>",
            back_markup("mon"),
        )
    if data == "cl:permanent":
        return await safe_edit(
            query.message,
            "<b>∞ PERMANENT LINKS</b>\n\n"
            "Every clone file button and signed stream/download URL remains valid "
            "while the clone and indexed source file exist.",
            back_markup("more"),
        )
    if data.startswith("cl:edit:"):
        action = data.split(":", 2)[2]
        clone_manager.set_pending_input(
            client.me.id,
            query.from_user.id,
            action,
        )
        return await safe_edit(
            query.message,
            INPUT_HELP.get(action, "<b>Send the new value.</b>")
            + "\n\nSend <code>/cancel</code> to cancel.",
            back_markup("panel"),
        )
    if data.startswith("cl:toggle:"):
        action = data.split(":", 2)[2]
        mapping = {
            "verify": "verification",
            "delete": "auto_delete",
            "protect": "protect_content",
            "stream": "stream_mode",
            "pm": "pm_search",
            "group": "group_search",
        }
        field = mapping.get(action)
        if not field:
            return
        settings[field] = not bool(settings.get(field))
        config = await clone_db.update_settings(
            client.me.id,
            {field: settings[field]},
        )
        if action in {"pm", "group"}:
            return await safe_edit(
                query.message,
                "<b>🛍 BOT MODE UPDATED</b>",
                mode_markup(config["settings"]),
            )
        if action == "verify":
            return await safe_edit(
                query.message,
                "<b>💵 MONETIZATION UPDATED</b>",
                monetization_markup(config["settings"]),
            )
        return await safe_edit(
            query.message,
            "<b>🔎 FEATURE UPDATED</b>",
            more_features_markup(config["settings"]),
        )
    if data == "cl:restart":
        await safe_edit(
            query.message,
            "<b>⏳ Restarting your clone bot...</b>",
            None,
        )
        background(restart_after(client.me.id))
        return
    if data == "cl:deactivate":
        await safe_edit(
            query.message,
            "<b>⏸ Clone deactivated.</b>\n\n"
            "Use the main RDX bot to activate it again.",
            None,
        )
        background(stop_after(client.me.id))
        return
    if data == "cl:delask":
        return await safe_edit(
            query.message,
            "<b>⚠️ DELETE THIS CLONE?</b>\n\n"
            "The clone configuration and its private indexed database will be deleted. "
            "This cannot be undone.",
            delete_confirmation_markup(),
        )
    if data == "cl:delete":
        await safe_edit(
            query.message,
            "<b>✅ Clone data deleted.</b>\n\n"
            "Revoke the bot token in BotFather to invalidate it completely.",
            None,
        )
        background(delete_after(client.me.id))


async def restart_after(bot_id):
    await asyncio.sleep(1)
    try:
        await clone_manager.restart_clone(bot_id)
    except Exception:
        logger.exception("Clone restart failed for %s", bot_id)


async def stop_after(bot_id):
    await asyncio.sleep(1)
    await clone_manager.stop_clone(bot_id, deactivate=True)


async def delete_after(bot_id):
    await asyncio.sleep(1)
    await clone_manager.delete_clone(bot_id)


def register_clone_handlers(client):
    client.add_handler(
        MessageHandler(
            pending_input,
            filters.private & filters.incoming,
        ),
        group=-30,
    )
    client.add_handler(
        MessageHandler(
            clone_start,
            filters.command("start") & filters.private & filters.incoming,
        ),
        group=-20,
    )
    client.add_handler(
        MessageHandler(
            owner_command,
            filters.command(
                [
                    "settings",
                    "status",
                    "index",
                    "addpremium",
                    "removepremium",
                ]
            )
            & filters.private
            & filters.incoming,
        ),
        group=-20,
    )
    client.add_handler(
        MessageHandler(
            channel_media,
            filters.channel
            & (filters.document | filters.video | filters.audio),
        ),
        group=-20,
    )
    client.add_handler(
        MessageHandler(
            clone_text_search,
            filters.text & filters.incoming,
        ),
        group=0,
    )
    client.add_handler(
        CallbackQueryHandler(
            clone_callback,
            filters.regex(r"^cl:"),
        ),
        group=-20,
    )
