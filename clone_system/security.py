"""Encryption and signed-link helpers used by the clone system."""

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from info import API_HASH, BOT_TOKEN, CLONE_SECRET_KEY


class CloneSecurityError(ValueError):
    """Raised when encrypted clone credentials cannot be decoded."""


def _secret_material():
    configured = str(CLONE_SECRET_KEY or "").strip()
    if configured:
        return configured.encode("utf-8")
    # Backward-compatible zero-configuration fallback. Deployments should set
    # CLONE_SECRET_KEY so rotating the main bot token does not lock old clones.
    return f"{API_HASH}:{BOT_TOKEN}:rdx-clone-v1".encode("utf-8")


def _fernet_key():
    return base64.urlsafe_b64encode(hashlib.sha256(_secret_material()).digest())


class TokenCipher:
    def __init__(self):
        self._fernet = Fernet(_fernet_key())

    def encrypt(self, token):
        value = str(token or "").strip()
        if not value:
            raise CloneSecurityError("Bot token is empty.")
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, encrypted_token):
        try:
            return self._fernet.decrypt(
                str(encrypted_token or "").encode("ascii")
            ).decode("utf-8")
        except (InvalidToken, UnicodeError, ValueError) as error:
            raise CloneSecurityError(
                "Clone token cannot be decrypted. Check CLONE_SECRET_KEY."
            ) from error


def sign_media(bot_id, record_key):
    payload = f"{int(bot_id)}:{record_key}".encode("utf-8")
    return hmac.new(
        hashlib.sha256(_secret_material()).digest(),
        payload,
        hashlib.sha256,
    ).hexdigest()[:20]


def valid_media_signature(bot_id, record_key, signature):
    return hmac.compare_digest(
        sign_media(bot_id, record_key),
        str(signature or ""),
    )
