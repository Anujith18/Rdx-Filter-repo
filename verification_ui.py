"""English-only text templates for the RDX verification flow."""

from html import escape


def verification_required_text(user_name, access_hours, token_minutes):
    name = escape(user_name or "RDX User")
    return (
        "<b>🔐 RDX ACCESS VERIFICATION</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hello <b>{name}</b> 👋\n\n"
        "To download your requested file, complete one quick verification.\n\n"
        f"⏳ <b>Verify Link Valid:</b> {token_minutes} Minutes\n"
        f"✅ <b>Free Access After Verify:</b> {access_hours} Hours\n"
        "💎 <b>Premium Users:</b> No Verification\n\n"
        "Tap <b>VERIFY NOW</b> below to continue."
    )


def verification_success_text(user_name, expires_at):
    name = escape(user_name or "RDX User")
    expiry_text = expires_at.strftime("%d %b %Y, %I:%M %p")
    timezone_name = expires_at.tzname() or ""
    if timezone_name:
        expiry_text = f"{expiry_text} {timezone_name}"
    return (
        "<b>✅ VERIFICATION COMPLETED</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Hello <b>{name}</b> 👋\n\n"
        "Your RDX access is now active.\n\n"
        f"⏰ <b>Access Valid Until:</b> {expiry_text}\n"
        "🎬 You can download unlimited files during this period.\n\n"
        "Tap <b>GET REQUESTED FILE</b> to continue."
    )


def verification_expired_text():
    return (
        "<b>❌ VERIFICATION LINK EXPIRED</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "This link has expired or was already used.\n"
        "Create a new verification link to continue."
    )


def verification_owner_mismatch_text():
    return (
        "<b>⛔ VERIFICATION LINK NOT VALID</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "This verification link belongs to another user.\n"
        "Please request your own file link from the bot."
    )


def verification_service_unavailable_text():
    return (
        "<b>⚠️ VERIFICATION TEMPORARILY UNAVAILABLE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "A protected verification link could not be created right now.\n"
        "Please wait a moment and try your file again."
    )


def verification_log_text(user_mention, user_id, verified_at, expires_at):
    return (
        "<b>✅ RDX VERIFICATION COMPLETED</b>\n\n"
        f"<b>User:</b> {user_mention}\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n"
        f"<b>Verified At:</b> {verified_at.strftime('%Y-%m-%d %I:%M:%S %p')}\n"
        f"<b>Access Until:</b> {expires_at.strftime('%Y-%m-%d %I:%M:%S %p')}\n\n"
        "#verify_completed"
    )
