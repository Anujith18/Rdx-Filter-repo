"""Main-bot controls for creating and managing RDX clone bots."""

import html

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from clone_system.database import clone_db
from clone_system.manager import CloneManagerError, clone_manager
from clone_system.ui import master_clone_markup
from database.users_chats_db import db
from info import (
    ADMINS,
    CLONE_MAX_ACTIVE,
    CLONE_MODE,
    CLONE_REQUIRE_PREMIUM,
    admin_user_ids,
)


def create_instructions():
    return (
        "<b>👨‍💻 CREATE YOUR OWN RDX CLONE</b>\n\n"
        "1. Open @BotFather and send <code>/newbot</code>.\n"
        "2. Choose a name and username.\n"
        "3. Copy the HTTP API token.\n"
        "4. Send or forward the BotFather token message here.\n\n"
        "<b>🔐 Security:</b> The token message will be deleted immediately and "
        "the token is stored encrypted.\n\n"
        "Send <code>/cancel</code> to cancel."
    )


def clone_admin_markup(enabled):
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                f"🤖 CLONE SYSTEM: {'ON ✅' if enabled else 'OFF ❌'}",
                callback_data=(
                    "cloneadmin:toggle:off"
                    if enabled
                    else "cloneadmin:toggle:on"
                ),
            )
        ]]
    )


async def clone_admin_text():
    enabled = await clone_manager.creation_enabled()
    total = await clone_db.clones.count_documents(
        {"deleted": {"$ne": True}}
    )
    active = await clone_db.clones.count_documents(
        {"active": True, "deleted": {"$ne": True}}
    )
    state = "ON ✅" if enabled else "OFF ❌"
    note = (
        "Users can create and manage clone bots."
        if enabled
        else "New clone creation is disabled. Existing clone bots remain online."
    )
    text = (
        "<b>🤖 RDX CLONE ADMIN</b>\n\n"
        f"<blockquote>System: <b>{state}</b>\n"
        f"Total: {total} • Active: {active} • Offline: {max(0, total-active)}\n"
        f"{note}</blockquote>"
    )
    return text, clone_admin_markup(enabled)


async def show_clone_panel(message, owner_id, edit=False):
    config = await clone_db.get_clone_by_owner(owner_id)
    if not config:
        text = (
            "<b>You do not have a clone bot yet.</b>\n\n"
            "Tap Create Own Clone to begin."
        )
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👨‍💻 CREATE OWN CLONE",
                        callback_data="clone:create",
                    )
                ]
            ]
        )
    else:
        running = clone_manager.is_running(config["bot_id"])
        text = (
            "<b>🔧 MANAGE YOUR CLONE BOT</b>\n\n"
            f"<blockquote>🤖 Bot: @{html.escape(config.get('username') or '')}\n"
            f"📊 Status: {'ONLINE ✅' if running else 'OFFLINE ❌'}\n"
            f"🛍 Plan: {html.escape(config.get('plan', 'free').upper())}\n"
            f"⚠️ Last Error: {html.escape(config.get('last_error') or 'None')}</blockquote>"
        )
        markup = master_clone_markup(config, running)
    if edit:
        try:
            return await message.edit_text(text, reply_markup=markup)
        except Exception:
            pass
    return await message.reply_text(text, reply_markup=markup)


@Client.on_message(
    filters.command("clone") & filters.private & filters.incoming,
    group=-40,
)
async def clone_command(client, message):
    config = await clone_db.get_clone_by_owner(message.from_user.id)
    if not config and not await clone_manager.creation_enabled():
        return await message.reply_text(
            "<b>🤖 Clone creation is temporarily disabled.</b>"
        )
    await show_clone_panel(message, message.from_user.id)


@Client.on_message(
    filters.command("clones") & filters.private & filters.user(ADMINS),
    group=-40,
)
async def all_clones_command(client, message):
    total = await clone_db.clones.count_documents(
        {"deleted": {"$ne": True}}
    )
    active = await clone_db.clones.count_documents(
        {"active": True, "deleted": {"$ne": True}}
    )
    rows = await clone_db.clones.find(
        {"deleted": {"$ne": True}},
        {
            "bot_id": 1,
            "owner_id": 1,
            "username": 1,
            "active": 1,
        },
    ).sort("updated_at", -1).limit(50).to_list(length=50)
    lines = [
        "<b>🤖 RDX CLONE ADMIN</b>",
        "",
        f"Total: {total} • Active: {active} • Offline: {max(0, total-active)}",
        "",
    ]
    for item in rows:
        state = "🟢" if clone_manager.is_running(item["bot_id"]) else "🔴"
        lines.append(
            f"{state} @{html.escape(item.get('username') or 'unknown')} "
            f"• Owner <code>{item.get('owner_id')}</code> "
            f"• Bot <code>{item.get('bot_id')}</code>"
        )
    lines.extend(
        [
            "",
            "<code>/clone_start BOT_ID</code>",
            "<code>/clone_stop BOT_ID</code>",
            "<code>/clone_delete BOT_ID</code>",
        ]
    )
    enabled = await clone_manager.creation_enabled()
    await message.reply_text(
        "\n".join(lines),
        reply_markup=clone_admin_markup(enabled),
    )


@Client.on_callback_query(filters.regex(r"^cloneadmin:"), group=-41)
async def clone_admin_callback(client, query):
    if query.from_user.id not in admin_user_ids():
        return await query.answer("Admins only.", show_alert=True)
    parts = query.data.split(":")
    if len(parts) != 3 or parts[1] != "toggle":
        return await query.answer("Invalid clone setting.", show_alert=True)
    requested = parts[2] == "on"
    try:
        enabled = await clone_manager.set_creation_enabled(requested)
    except CloneManagerError as error:
        return await query.answer(str(error), show_alert=True)
    await query.answer(
        f"Clone system {'enabled' if enabled else 'disabled'}.",
        show_alert=True,
    )
    text, markup = await clone_admin_text()
    try:
        await query.message.edit_text(text, reply_markup=markup)
    except Exception:
        await query.message.reply_text(text, reply_markup=markup)


@Client.on_message(
    filters.command(["clone_start", "clone_stop", "clone_delete"])
    & filters.private
    & filters.user(ADMINS),
    group=-40,
)
async def clone_admin_action(client, message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("<b>Send a valid clone bot ID.</b>")
    bot_id = int(message.command[1])
    config = await clone_db.get_clone(bot_id)
    if not config:
        return await message.reply_text("<b>Clone not found.</b>")
    command = message.command[0].lower()
    try:
        if command == "clone_start":
            await clone_manager.start_clone(config)
            result = "started"
        elif command == "clone_stop":
            await clone_manager.stop_clone(bot_id, deactivate=True)
            result = "stopped"
        else:
            await clone_manager.delete_clone(bot_id)
            result = "deleted"
    except Exception as error:
        return await message.reply_text(
            f"<b>Action failed:</b> {html.escape(str(error))}"
        )
    await message.reply_text(f"<b>✅ Clone {result}.</b>")


@Client.on_message(filters.private & filters.incoming, group=-50)
async def receive_clone_token(client, message):
    if not message.from_user:
        return
    user_id = message.from_user.id
    if not clone_manager.is_creation_pending(user_id):
        return
    if not await clone_manager.creation_enabled():
        clone_manager.cancel_creation(user_id)
        await message.reply_text(
            "<b>🤖 Clone creation was disabled by the administrator.</b>"
        )
        message.stop_propagation()
        return
    text = message.text or message.caption or ""
    if text.strip().lower() == "/cancel":
        clone_manager.cancel_creation(user_id)
        await message.reply_text("<b>Clone creation cancelled.</b>")
        message.stop_propagation()
        return
    token = clone_manager.extract_token(text)
    if not token:
        await message.reply_text(
            "<b>❌ I could not find a valid BotFather token.</b>\n\n"
            "Send or forward the complete BotFather token message, or send "
            "<code>/cancel</code>."
        )
        message.stop_propagation()
        return
    try:
        await message.delete()
    except Exception:
        pass
    checking = await client.send_message(
        user_id,
        "<b>👨‍💻 CHECKING BOT INFORMATION...</b>\n\n"
        "<code>▰▰▱▱▱</code>",
    )
    try:
        config = await clone_manager.create_clone(user_id, token)
    except CloneManagerError as error:
        await checking.edit_text(
            f"<b>❌ CLONE CREATION FAILED</b>\n\n"
            f"{html.escape(str(error))}\n\n"
            "Send a valid token again or <code>/cancel</code>."
        )
    else:
        clone_manager.cancel_creation(user_id)
        await checking.edit_text(
            "<b>✅ YOUR CLONE BOT IS READY</b>\n\n"
            f"🤖 Bot: @{html.escape(config.get('username') or '')}\n"
            "🔐 Token: encrypted and secured\n"
            "☁️ Database: private clone catalogue\n\n"
            "Open the clone and use <code>/settings</code>.",
            reply_markup=master_clone_markup(config, True),
        )
    message.stop_propagation()


@Client.on_callback_query(filters.regex(r"^clone:"), group=-40)
async def clone_manager_callback(client, query):
    action = query.data.split(":", 1)[1]
    owner_id = query.from_user.id
    config = await clone_db.get_clone_by_owner(owner_id)

    if action == "create":
        if config:
            await query.answer("Opening your clone manager.")
            return await show_clone_panel(query.message, owner_id, edit=True)
        if not await clone_manager.creation_enabled():
            message = (
                "Clone creation is temporarily disabled by the administrator."
                if CLONE_MODE
                else "Clone system is disabled. Set CLONE_MODE=True in Config Vars and redeploy."
            )
            return await query.answer(message, show_alert=True)
        if (
            CLONE_REQUIRE_PREMIUM
            and not await db.has_premium_access(owner_id)
        ):
            return await query.answer(
                "Clone creation is available for Premium users.",
                show_alert=True,
            )
        if await clone_db.count_active_clones() >= CLONE_MAX_ACTIVE:
            return await query.answer(
                "The server clone limit has been reached.",
                show_alert=True,
            )
        clone_manager.mark_creation_pending(owner_id)
        await query.answer()
        return await query.message.reply_text(
            create_instructions(),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "❌ CANCEL",
                            callback_data="clone:cancel",
                        )
                    ]
                ]
            ),
        )
    if action == "cancel":
        clone_manager.cancel_creation(owner_id)
        await query.answer("Cancelled.")
        return await query.message.edit_text("<b>Clone creation cancelled.</b>")
    if action == "mine":
        await query.answer()
        return await show_clone_panel(query.message, owner_id, edit=True)
    if not config:
        return await query.answer(
            "You do not have a clone bot.",
            show_alert=True,
        )

    bot_id = config["bot_id"]
    if action == "status":
        media = await clone_db.media_count(bot_id)
        users = await clone_db.user_count(bot_id)
        running = clone_manager.is_running(bot_id)
        return await query.answer(
            f"Status: {'ONLINE' if running else 'OFFLINE'}\n"
            f"Files: {media}\nUsers: {users}",
            show_alert=True,
        )
    if action == "restart":
        await query.answer("Restarting clone...", show_alert=True)
        try:
            await clone_manager.restart_clone(bot_id)
        except Exception as error:
            return await query.message.reply_text(
                f"<b>❌ Restart failed:</b> {html.escape(str(error))}"
            )
        return await show_clone_panel(query.message, owner_id, edit=True)
    if action == "deactivate":
        await query.answer("Deactivating clone...")
        await clone_manager.stop_clone(bot_id, deactivate=True)
        return await show_clone_panel(query.message, owner_id, edit=True)
    if action == "activate":
        await query.answer("Activating clone...")
        try:
            await clone_manager.start_clone(config)
        except Exception as error:
            return await query.message.reply_text(
                f"<b>❌ Activation failed:</b> {html.escape(str(error))}"
            )
        return await show_clone_panel(query.message, owner_id, edit=True)
    if action == "delask":
        await query.answer()
        return await query.message.edit_text(
            "<b>⚠️ DELETE YOUR CLONE?</b>\n\n"
            "All private indexed files and clone settings will be removed. "
            "This cannot be undone.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ YES, DELETE",
                            callback_data="clone:delete",
                        ),
                        InlineKeyboardButton(
                            "❌ CANCEL",
                            callback_data="clone:mine",
                        ),
                    ]
                ]
            ),
        )
    if action == "delete":
        await query.answer("Deleting clone...")
        await clone_manager.delete_clone(bot_id)
        return await query.message.edit_text(
            "<b>✅ Clone data deleted.</b>\n\n"
            "For complete security, revoke its token from @BotFather."
        )
