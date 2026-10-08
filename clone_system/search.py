"""Private, tenant-aware search and filter UI for clone bots."""

import html
import math
import re

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from info import CLONE_SEARCH_PAGE_SIZE
from search_filters import (
    LANGUAGE_LABELS,
    LANGUAGE_PATTERNS,
    QUALITY_PATTERNS,
    display_filter_query,
    extract_episode_numbers,
    make_filter_query,
    matches_filter,
    parse_filter_query,
)
from .database import clone_db
from .manager import clone_manager


def readable_size(size):
    size = int(size or 0)
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024


def file_button_text(record):
    name = (
        record.get("original_file_name")
        or record.get("file_name")
        or "File"
    )
    return f"📁 {readable_size(record.get('file_size'))} ▹ {name}"


def record_text(record):
    return " ".join(
        str(record.get(key) or "")
        for key in ("file_name", "caption")
    )


async def safe_edit(message, text, reply_markup):
    try:
        return await message.edit_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    except Exception:
        try:
            return await message.edit_caption(
                text,
                reply_markup=reply_markup,
            )
        except Exception:
            replacement = await message.reply_text(
                text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            try:
                await message.delete()
            except Exception:
                pass
            return replacement


async def render_search(
    client,
    message,
    query,
    *,
    requester_id,
    session_key=None,
    offset=0,
    edit=False,
):
    bot_id = int(client.me.id)
    offset = max(0, int(offset or 0))
    files, total = await clone_db.search_media(
        bot_id,
        query,
        offset=offset,
        limit=CLONE_SEARCH_PAGE_SIZE,
    )
    if not files:
        text = (
            "<b>RDX AUTO FILTER</b>\n\n"
            "🚫 <b>NO FILES WERE FOUND</b>\n\n"
            "Check the spelling or clear one of the selected filters."
        )
        markup = None
        if session_key:
            markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🧹 CLEAR FILTERS",
                            callback_data=f"cl:sx:{session_key}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "≼ BACK TO FILES",
                            callback_data=f"cl:sp:{session_key}:0",
                        )
                    ],
                ]
            )
        if edit:
            return await safe_edit(message, text, markup)
        return await message.reply_text(text, reply_markup=markup)

    if not session_key:
        session_key = clone_manager.create_search_session(
            bot_id,
            message.chat.id,
            requester_id,
            query,
        )
    else:
        clone_manager.update_search_session(session_key, query)

    shown_query = html.escape(display_filter_query(query) or query)
    page = (offset // CLONE_SEARCH_PAGE_SIZE) + 1
    pages = max(1, math.ceil(total / CLONE_SEARCH_PAGE_SIZE))
    text = (
        f"<b>🎯 TITLE:</b> {shown_query}\n"
        f"<b>📂 TOTAL FILES:</b> {total}\n"
        f"<b>📄 PAGE:</b> {page}/{pages}\n\n"
        "<b>🌳 REQUESTED FILES 👇</b>\n\n"
    )

    username = client.me.username
    for record in files:
        file_name = html.escape(
            str(
                record.get("original_file_name")
                or record.get("file_name")
                or "Telegram File"
            )
        )
        file_url = (
            f"https://t.me/{username}?start=cf_{record['record_key']}"
        )
        text += (
            f"<b><a href='{file_url}'>📁 "
            f"{readable_size(record.get('file_size'))} ▷ "
            f"{file_name}</a></b>\n\n"
        )

    rows = []
    _, selected = parse_filter_query(query)
    combined_label = (
        "✅ COMBINED FILES" if selected.get("combined") else "📦 COMBINED FILES"
    )
    rows.append(
        [
            InlineKeyboardButton(
                combined_label,
                callback_data=f"cl:sf:{session_key}:c:t",
            ),
            InlineKeyboardButton(
                "🧹 CLEAR",
                callback_data=f"cl:sx:{session_key}",
            ),
        ],
    )
    rows.append(
        [
            InlineKeyboardButton(
                "🎞 QUALITY",
                callback_data=f"cl:sm:{session_key}:q",
            ),
            InlineKeyboardButton(
                "🌐 LANGUAGE",
                callback_data=f"cl:sm:{session_key}:l",
            ),
        ],
    )
    rows.append(
        [
            InlineKeyboardButton(
                "📺 SEASON",
                callback_data=f"cl:sm:{session_key}:s",
            ),
            InlineKeyboardButton(
                "🎬 EPISODES",
                callback_data=f"cl:sm:{session_key}:e",
            ),
        ],
    )

    nav = []
    if offset > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅ PREV",
                callback_data=(
                    f"cl:sp:{session_key}:"
                    f"{max(0, offset - CLONE_SEARCH_PAGE_SIZE)}"
                ),
            )
        )
    nav.append(InlineKeyboardButton(f"{page}/{pages}", callback_data="cl:noop"))
    if offset + CLONE_SEARCH_PAGE_SIZE < total:
        nav.append(
            InlineKeyboardButton(
                "NEXT ➡",
                callback_data=(
                    f"cl:sp:{session_key}:"
                    f"{offset + CLONE_SEARCH_PAGE_SIZE}"
                ),
            )
        )
    rows.append(nav)
    markup = InlineKeyboardMarkup(rows)
    if edit:
        return await safe_edit(message, text, markup)
    return await message.reply_text(
        text,
        reply_markup=markup,
        disable_web_page_preview=True,
    )


def _count_values(records, query, kind, candidates):
    results = []
    for value, label in candidates:
        filtered = make_filter_query(query, **{kind: value})
        count = sum(
            1
            for record in records
            if matches_filter(record_text(record), filtered)
        )
        if count:
            results.append((value, label, count))
    return results


def _rows(items, session_key, kind):
    buttons = [
        InlineKeyboardButton(
            f"{label} ({count})",
            callback_data=f"cl:sf:{session_key}:{kind}:{value}",
        )
        for value, label, count in items
    ]
    return [buttons[index:index + 2] for index in range(0, len(buttons), 2)]


async def render_filter_menu(client, message, session_key, kind):
    session = clone_manager.get_search_session(session_key)
    if not session:
        return await safe_edit(
            message,
            "<b>This search session has expired. Search again.</b>",
            None,
        )
    query = session["query"]
    field_map = {
        "q": "quality",
        "l": "language",
        "s": "season",
        "e": "episode",
    }
    field = field_map.get(kind)
    if not field:
        return
    base_query = make_filter_query(query, **{field: None})
    records = await clone_db.all_matching_media(client.me.id, base_query)
    if kind == "q":
        candidates = [
            (value, value.upper())
            for value in QUALITY_PATTERNS
        ]
        items = _count_values(records, base_query, "quality", candidates)
        title = "🎞 SELECT QUALITY"
    elif kind == "l":
        candidates = [
            (value, LANGUAGE_LABELS.get(value, value.title()))
            for value in LANGUAGE_PATTERNS
        ]
        items = _count_values(records, base_query, "language", candidates)
        title = "🌐 SELECT LANGUAGE"
    elif kind == "s":
        counts = {}
        for record in records:
            match = re.search(
                r"(?i)(?<![a-z0-9])(?:s|season)[\W_]*0*(\d{1,2})(?!\d)",
                record_text(record),
            )
            if match:
                number = int(match.group(1))
                counts[number] = counts.get(number, 0) + 1
        items = [
            (str(number), f"SEASON {number:02d}", count)
            for number, count in sorted(counts.items())
        ]
        title = "📺 SELECT SEASON"
    else:
        counts = {}
        for record in records:
            for number in extract_episode_numbers(record_text(record)):
                counts[number] = counts.get(number, 0) + 1
        items = [
            (str(number), f"E{number:02d}", count)
            for number, count in sorted(counts.items())
        ]
        title = f"🎬 SELECT EPISODE • {len(items)} AVAILABLE"

    rows = _rows(items, session_key, kind)
    rows.append(
        [
            InlineKeyboardButton(
                f"❌ CLEAR {field.upper()}",
                callback_data=f"cl:sf:{session_key}:{kind}:off",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                "≼ BACK TO FILES",
                callback_data=f"cl:sp:{session_key}:0",
            )
        ]
    )
    text = (
        f"<b>{title}</b>\n\n"
        f"Found {len(records)} matching files across every result page."
    )
    await safe_edit(message, text, InlineKeyboardMarkup(rows))


async def apply_filter(client, message, session_key, kind, value):
    session = clone_manager.get_search_session(session_key)
    if not session:
        return await safe_edit(
            message,
            "<b>This search session has expired. Search again.</b>",
            None,
        )
    query = session["query"]
    current = parse_filter_query(query)[1]
    field_map = {
        "q": "quality",
        "l": "language",
        "s": "season",
        "e": "episode",
    }
    if kind == "c":
        updated = make_filter_query(
            query,
            combined=None if current.get("combined") else "on",
        )
    else:
        field = field_map.get(kind)
        if not field:
            return
        updated = make_filter_query(
            query,
            **{field: None if value == "off" else value},
        )
    clone_manager.update_search_session(session_key, updated)
    await render_search(
        client,
        message,
        updated,
        requester_id=session["user_id"],
        session_key=session_key,
        offset=0,
        edit=True,
    )


async def clear_filters(client, message, session_key):
    session = clone_manager.get_search_session(session_key)
    if not session:
        return await safe_edit(
            message,
            "<b>This search session has expired. Search again.</b>",
            None,
        )
    base, _ = parse_filter_query(session["query"])
    clone_manager.update_search_session(session_key, base)
    await render_search(
        client,
        message,
        base,
        requester_id=session["user_id"],
        session_key=session_key,
        offset=0,
        edit=True,
    )
