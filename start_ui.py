"""Fault-tolerant private-chat start animation and welcome delivery."""

import asyncio
import logging

from branding import BRAND_NAME, WELCOME_BANNER


logger = logging.getLogger(__name__)


ANIMATION_STYLES = {
    "cinema": (
        f"<b>🎬 {BRAND_NAME}</b>\n\n<code>▰▱▱▱▱</code> Opening cinema...",
        f"<b>🎬 {BRAND_NAME}</b>\n\n<code>▰▰▰▱▱</code> Connecting...",
        f"<b>🍿 {BRAND_NAME}</b>\n\n<code>▰▰▰▰▱</code> Preparing movies...",
        f"<b>✅ {BRAND_NAME} READY</b>\n\n<code>▰▰▰▰▰</code>",
    ),
    "neon": (
        f"<b>◢⚡ {BRAND_NAME} ⚡◣</b>\n\n<code>◇◇◇</code> Powering up...",
        f"<b>◢⚡ {BRAND_NAME} ⚡◣</b>\n\n<code>◆◇◇</code> Loading...",
        f"<b>◢⚡ {BRAND_NAME} ⚡◣</b>\n\n<code>◆◆◇</code> Almost ready...",
        f"<b>◢✅ {BRAND_NAME} ONLINE ◣</b>\n\n<code>◆◆◆</code>",
    ),
    "minimal": (
        f"<b>⚜️ {BRAND_NAME}</b>\n\n<code>●○○</code> Starting...",
        f"<b>⚜️ {BRAND_NAME}</b>\n\n<code>●●○</code> Loading...",
        f"<b>⚜️ {BRAND_NAME}</b>\n\n<code>●●●</code> Ready",
    ),
}


async def _with_timeout(awaitable, seconds):
    return await asyncio.wait_for(awaitable, timeout=seconds)


async def play_start_animation(message, style="cinema", enabled=True, delay=0.32):
    """Play a short editable loader without ever blocking the welcome."""
    if not enabled:
        return None

    frames = ANIMATION_STYLES.get(
        str(style or "").strip().lower(),
        ANIMATION_STYLES["cinema"],
    )
    loading = None
    try:
        loading = await _with_timeout(
            message.reply_text(frames[0]),
            5,
        )
    except Exception as error:
        logger.warning("Start animation could not be created: %s", error)
        return None

    for frame in frames[1:]:
        await asyncio.sleep(delay)
        try:
            await _with_timeout(loading.edit_text(frame), 3)
        except Exception as error:
            logger.debug("Start animation frame skipped: %s", error)

    await asyncio.sleep(delay)
    try:
        await _with_timeout(loading.delete(), 3)
    except Exception as error:
        # The old implementation stopped here and never sent the welcome.
        logger.debug("Start animation cleanup skipped: %s", error)
    return loading


def _unique_photo_candidates(photo_sources):
    candidates = []
    for source in list(photo_sources or []) + [WELCOME_BANNER]:
        source = str(source or "").strip()
        if source and source not in candidates:
            candidates.append(source)
    return candidates


async def send_start_welcome(
    message,
    photo_sources,
    caption,
    reply_markup,
    parse_mode,
):
    """Send the welcome with local-banner and text-only fallbacks."""
    for photo in _unique_photo_candidates(photo_sources):
        try:
            return await _with_timeout(
                message.reply_photo(
                    photo=photo,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                ),
                15,
            )
        except Exception as error:
            logger.warning("Start welcome photo failed; trying fallback: %s", error)

    # A broken PICS URL or Telegram media fetch must not make /start silent.
    return await _with_timeout(
        message.reply_text(
            text=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        ),
        10,
    )
