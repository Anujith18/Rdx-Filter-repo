"""Client for creating browser-bound links with RDX Anti-Bypass."""

import asyncio
import logging
from urllib.parse import urlsplit

import aiohttp

from info import (
    ANTI_BYPASS_API_KEY,
    ANTI_BYPASS_BASE_URL,
    ANTI_BYPASS_REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)


class AntiBypassError(RuntimeError):
    """Raised when a protected verification link cannot be created."""


def _is_web_url(value):
    parsed = urlsplit(str(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def create_protected_verification_url(target_url, user_id, expires_in):
    """
    Return a protected URL or None when Anti-Bypass is fully disabled.

    A partial or invalid configuration fails closed so the bot never sends an
    unprotected token link by mistake.
    """

    has_base_url = bool(ANTI_BYPASS_BASE_URL)
    has_api_key = bool(ANTI_BYPASS_API_KEY)
    if not has_base_url and not has_api_key:
        return None
    if not has_base_url or not has_api_key:
        raise AntiBypassError(
            "Both ANTI_BYPASS_BASE_URL and ANTI_BYPASS_API_KEY are required."
        )
    if not _is_web_url(target_url):
        raise AntiBypassError("The Telegram verification target URL is invalid.")

    base_url = ANTI_BYPASS_BASE_URL.rstrip("/")
    if not _is_web_url(base_url):
        raise AntiBypassError("ANTI_BYPASS_BASE_URL must be an http(s) URL.")

    try:
        timeout_seconds = max(1, int(ANTI_BYPASS_REQUEST_TIMEOUT))
        link_expiry = max(60, min(int(expires_in), 31_536_000))
    except (TypeError, ValueError) as error:
        raise AntiBypassError("Anti-Bypass timeout configuration is invalid.") from error

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{base_url}/api/v1/links",
                headers={
                    "X-API-Key": ANTI_BYPASS_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "target_url": target_url,
                    "user_id": int(user_id),
                    "expires_in": link_expiry,
                    "max_uses": 1,
                    "metadata": {
                        "source": "rdx-auto-filter",
                        "purpose": "telegram-file-verification",
                    },
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
    except aiohttp.ClientResponseError as error:
        logger.error("Anti-Bypass API returned HTTP %s.", error.status)
        raise AntiBypassError(
            "The protection service rejected the link creation request."
        ) from error
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError) as error:
        logger.error("Anti-Bypass request failed: %s", type(error).__name__)
        raise AntiBypassError("The protection service request failed.") from error

    protected_url = payload.get("protected_url") if isinstance(payload, dict) else None
    if not isinstance(protected_url, str) or not _is_web_url(protected_url):
        raise AntiBypassError(
            "The protection service returned an invalid protected URL."
        )
    return protected_url
