"""English RDX clone messages and inline keyboard layouts."""

import html

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def start_text(config, user):
    settings = config.get("settings", {})
    template = settings.get("start_message") or (
        "<b>⚜️ WELCOME TO {bot_name} ⚜️</b>\n\n"
        "<blockquote><b>Hello {user} 👋</b>\n\n"
        "Your personal movie and series library is ready!</blockquote>\n\n"
        "🎬 <b>Search movies and series</b>\n"
        "⚡ <b>Get files instantly</b>\n"
        "📥 <b>Stream or download easily</b>\n"
        "🔒 <b>Fast, secure and reliable</b>\n\n"
        "<blockquote>🔎 Simply send the name of your desired movie or series "
        "to begin searching.</blockquote>\n\n"
        "<b>✨ Enjoy your entertainment with {bot_name}!</b>"
    )
    values = {
        "user": getattr(user, "mention", None)
        or html.escape(getattr(user, "first_name", "User") or "User"),
        "bot_name": html.escape(config.get("name") or "RDX Clone Bot"),
        "bot_username": html.escape(config.get("username") or ""),
    }
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return template


def start_markup(config, privileged=False):
    settings = config.get("settings", {})
    rows = [
        [
            InlineKeyboardButton("🕵️ HELP", callback_data="cl:help"),
            InlineKeyboardButton("📜 ABOUT", callback_data="cl:about"),
        ]
    ]
    if privileged:
        rows.append(
            [InlineKeyboardButton("‼️ SETTINGS ‼️", callback_data="cl:panel")]
        )
    custom_text = settings.get("custom_button_text")
    custom_url = settings.get("custom_button_url")
    if custom_text and custom_url:
        rows.append([InlineKeyboardButton(custom_text, url=custom_url)])
    updates_url = settings.get("updates_url")
    support_url = settings.get("support_url")
    links = []
    if updates_url:
        links.append(InlineKeyboardButton("🤖 UPDATES", url=updates_url))
    if support_url:
        links.append(InlineKeyboardButton("🔎 SUPPORT", url=support_url))
    if links:
        rows.append(links)
    return InlineKeyboardMarkup(rows)


def help_text(config):
    name = html.escape(config.get("name") or "RDX Clone Bot")
    return (
        f"<b>🕵️ {name} HELP</b>\n\n"
        "🔎 Send a movie or series name in PM or an enabled group.\n"
        "🎬 Use Episode, Season, Quality, Language and Combined buttons.\n"
        "📥 Tap a file button to receive the file in private chat.\n"
        "⚡ Stream or download when the owner enables streaming.\n\n"
        "<b>Owner commands</b>\n"
        "<code>/settings</code> — open clone settings\n"
        "<code>/index CHANNEL_ID LAST_MESSAGE_ID</code> — index old files\n"
        "<code>/addpremium USER_ID DAYS</code> — add premium\n"
        "<code>/removepremium USER_ID</code> — remove premium"
    )


def about_text(config):
    return (
        "<b>☂️ ABOUT</b>\n\n"
        f"<blockquote>🤖 NAME — {html.escape(config.get('name') or 'RDX Clone Bot')}\n"
        "📨 TYPE — AUTO FILTER CLONE BOT\n"
        "💾 STORES — TELEGRAM MEDIA INDEXES\n"
        "🔗 GENERATES — SEARCH, STREAM AND DOWNLOAD LINKS\n"
        "⚡ FEATURES — EPISODE, SEASON, LANGUAGE, QUALITY AND COMBINED\n"
        "📝 LANGUAGE — PYTHON\n"
        "📚 LIBRARY — PYROFORK\n"
        "🗃 DATABASE — MONGODB</blockquote>\n\n"
        "<b>🚀 Built for fast, secure and isolated media search.</b>\n\n"
        "<i>👑 CLONED FROM — RDX AUTO FILTER</i>"
    )


def back_markup(target="home"):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("≼ BACK", callback_data=f"cl:{target}")]]
    )


def management_markup():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💵 MONETIZATION", callback_data="cl:mon")],
            [InlineKeyboardButton("📝 START MESSAGE", callback_data="cl:startcfg")],
            [InlineKeyboardButton("📢 LOG CHANNEL", callback_data="cl:edit:log")],
            [InlineKeyboardButton("☁️ INDEX CHANNELS", callback_data="cl:edit:index")],
            [InlineKeyboardButton("👥 ADMINS", callback_data="cl:edit:admins")],
            [InlineKeyboardButton("📊 BOT STATUS", callback_data="cl:status")],
            [InlineKeyboardButton("🛍 BOT MODE", callback_data="cl:mode")],
            [InlineKeyboardButton("⏱ RESTART BOT", callback_data="cl:restart")],
            [InlineKeyboardButton("⏸ DEACTIVATE BOT", callback_data="cl:deactivate")],
            [InlineKeyboardButton("🚫 DELETE BOT", callback_data="cl:delask")],
            [InlineKeyboardButton("🔎 MORE FEATURES", callback_data="cl:more")],
            [InlineKeyboardButton("≼ BACK", callback_data="cl:home")],
        ]
    )


def start_config_markup():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📝 EDIT START TEXT", callback_data="cl:edit:start")],
            [InlineKeyboardButton("🖼 START POSTER", callback_data="cl:edit:poster")],
            [InlineKeyboardButton("🔘 CUSTOM BUTTON", callback_data="cl:edit:button")],
            [InlineKeyboardButton("🤖 UPDATES LINK", callback_data="cl:edit:updates")],
            [InlineKeyboardButton("🔎 SUPPORT LINK", callback_data="cl:edit:support")],
            [InlineKeyboardButton("≼ BACK", callback_data="cl:panel")],
        ]
    )


def monetization_markup(settings):
    verify = "ON ✅" if settings.get("verification") else "OFF ❌"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⏰ TOKEN VERIFICATION: {verify}",
                    callback_data="cl:toggle:verify",
                )
            ],
            [InlineKeyboardButton("🔗 LINK SHORTENER", callback_data="cl:edit:short")],
            [InlineKeyboardButton("🎥 VERIFY TUTORIAL", callback_data="cl:edit:tutorial")],
            [InlineKeyboardButton("💎 PREMIUM COMMANDS", callback_data="cl:premiumhelp")],
            [InlineKeyboardButton("🌍 REFER AND EARN", callback_data="cl:refer")],
            [InlineKeyboardButton("≼ BACK", callback_data="cl:panel")],
        ]
    )


def more_features_markup(settings):
    auto_delete = "ON ✅" if settings.get("auto_delete") else "OFF ❌"
    protect = "ON ✅" if settings.get("protect_content") else "OFF ❌"
    stream = "ON ✅" if settings.get("stream_mode") else "OFF ❌"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🍿 CUSTOM CAPTION", callback_data="cl:edit:caption")],
            [InlineKeyboardButton("📣 FORCE SUBSCRIBE", callback_data="cl:edit:fsub")],
            [InlineKeyboardButton("🌄 FALLBACK THUMBNAIL", callback_data="cl:edit:thumb")],
            [InlineKeyboardButton("🔘 CUSTOM BUTTON", callback_data="cl:edit:button")],
            [
                InlineKeyboardButton(
                    f"♻️ AUTO DELETE: {auto_delete}",
                    callback_data="cl:toggle:delete",
                )
            ],
            [InlineKeyboardButton("⏳ AUTO DELETE TIME", callback_data="cl:edit:dtime")],
            [
                InlineKeyboardButton(
                    f"🔒 PROTECT CONTENT: {protect}",
                    callback_data="cl:toggle:protect",
                )
            ],
            [
                InlineKeyboardButton(
                    f"📡 STREAM & DOWNLOAD: {stream}",
                    callback_data="cl:toggle:stream",
                )
            ],
            [
                InlineKeyboardButton(
                    "∞ PERMANENT LINKS",
                    callback_data="cl:permanent",
                )
            ],
            [InlineKeyboardButton("≼ BACK", callback_data="cl:panel")],
        ]
    )


def delete_confirmation_markup():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ YES, DELETE", callback_data="cl:delete"),
                InlineKeyboardButton("❌ CANCEL", callback_data="cl:panel"),
            ]
        ]
    )


def mode_markup(settings):
    pm = "ON ✅" if settings.get("pm_search") else "OFF ❌"
    group = "ON ✅" if settings.get("group_search") else "OFF ❌"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"PRIVATE SEARCH: {pm}",
                    callback_data="cl:toggle:pm",
                )
            ],
            [
                InlineKeyboardButton(
                    f"GROUP SEARCH: {group}",
                    callback_data="cl:toggle:group",
                )
            ],
            [InlineKeyboardButton("≼ BACK", callback_data="cl:panel")],
        ]
    )


def master_start_button(existing=False):
    if existing:
        return InlineKeyboardButton(
            "🛠 MANAGE MY CLONE",
            callback_data="clone:mine",
        )
    return InlineKeyboardButton(
        "👨‍💻 CREATE OWN CLONE 👨‍💻",
        callback_data="clone:create",
    )


def master_clone_markup(config, running):
    username = config.get("username") or ""
    rows = []
    if username:
        rows.append(
            [InlineKeyboardButton("🤖 OPEN CLONE BOT", url=f"https://t.me/{username}")]
        )
    rows.extend(
        [
            [InlineKeyboardButton("📊 BOT STATUS", callback_data="clone:status")],
            [InlineKeyboardButton("⏱ RESTART BOT", callback_data="clone:restart")],
            [
                InlineKeyboardButton(
                    "⏸ DEACTIVATE BOT" if running else "▶️ ACTIVATE BOT",
                    callback_data=(
                        "clone:deactivate" if running else "clone:activate"
                    ),
                )
            ],
            [InlineKeyboardButton("🚫 DELETE BOT", callback_data="clone:delask")],
        ]
    )
    return InlineKeyboardMarkup(rows)
