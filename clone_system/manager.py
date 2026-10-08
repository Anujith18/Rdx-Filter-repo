"""Lifecycle manager for dynamically created RDX clone bots."""

import asyncio
import logging
import re
import secrets
import time

from pyrogram import Client

from Deendayal_botz.Bot import multi_clients, work_loads
from info import (
    API_HASH,
    API_ID,
    CLONE_MAX_ACTIVE,
    CLONE_MODE,
    CLONE_WORKERS,
)
from .database import clone_db
from .security import TokenCipher


logger = logging.getLogger(__name__)
TOKEN_RE = re.compile(r"(?<!\d)(\d{8,12}:[A-Za-z0-9_-]{30,})(?!\S)")


class CloneManagerError(RuntimeError):
    pass


class CloneManager:
    def __init__(self):
        self.clients = {}
        self.started_at = {}
        self.creation_pending = set()
        self.input_pending = {}
        self.search_sessions = {}
        self._locks = {}
        self._cipher = TokenCipher()

    def _lock(self, bot_id):
        return self._locks.setdefault(int(bot_id), asyncio.Lock())

    @staticmethod
    def extract_token(text):
        match = TOKEN_RE.search(str(text or ""))
        return match.group(1) if match else None

    def mark_creation_pending(self, user_id):
        self.creation_pending.add(int(user_id))

    def cancel_creation(self, user_id):
        self.creation_pending.discard(int(user_id))

    def is_creation_pending(self, user_id):
        return int(user_id) in self.creation_pending

    def set_pending_input(self, bot_id, user_id, action):
        self.input_pending[(int(bot_id), int(user_id))] = {
            "action": str(action),
            "created_at": time.monotonic(),
        }

    def pop_pending_input(self, bot_id, user_id):
        item = self.input_pending.pop((int(bot_id), int(user_id)), None)
        if item and time.monotonic() - item["created_at"] < 900:
            return item["action"]
        return None

    def clear_pending_input(self, bot_id, user_id):
        self.input_pending.pop((int(bot_id), int(user_id)), None)

    def create_search_session(self, bot_id, chat_id, user_id, query):
        self._purge_search_sessions()
        key = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
        self.search_sessions[key] = {
            "bot_id": int(bot_id),
            "chat_id": int(chat_id),
            "user_id": int(user_id),
            "query": str(query),
            "created_at": time.monotonic(),
        }
        return key

    def get_search_session(self, key):
        self._purge_search_sessions()
        return self.search_sessions.get(str(key))

    def update_search_session(self, key, query):
        session = self.get_search_session(key)
        if session:
            session["query"] = str(query)
            session["created_at"] = time.monotonic()
        return session

    def _purge_search_sessions(self):
        now = time.monotonic()
        expired = [
            key
            for key, value in self.search_sessions.items()
            if now - value["created_at"] > 3600
        ]
        for key in expired:
            self.search_sessions.pop(key, None)

    def is_running(self, bot_id):
        client = self.clients.get(int(bot_id))
        return bool(client and getattr(client, "is_connected", True))

    async def creation_enabled(self):
        """Environment is the hard switch; MongoDB is the live admin switch."""
        if not CLONE_MODE:
            return False
        return await clone_db.clone_creation_enabled(default=True)

    async def set_creation_enabled(self, enabled):
        if not CLONE_MODE and enabled:
            raise CloneManagerError(
                "CLONE_MODE is disabled in Config Vars. Enable it and redeploy first."
            )
        return await clone_db.set_clone_creation_enabled(enabled)

    async def start_all(self):
        if not CLONE_MODE:
            logger.info("Clone system is disabled.")
            return
        await clone_db.ensure_indexes()
        documents = await clone_db.get_active_clones(CLONE_MAX_ACTIVE)
        for document in documents:
            try:
                await self.start_clone(document)
            except Exception as error:
                bot_id = document.get("bot_id")
                logger.error("Clone %s could not start: %s", bot_id, error)
                await clone_db.update_runtime(
                    bot_id,
                    active=False,
                    error=str(error),
                )

    async def _new_client(self, bot_id, token):
        client = Client(
            name=f"rdx_clone_{int(bot_id)}",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=token,
            workers=CLONE_WORKERS,
            sleep_threshold=10,
            in_memory=True,
        )
        from .handlers import register_clone_handlers

        register_clone_handlers(client)
        await client.start()
        return client

    async def create_clone(self, owner_id, token):
        if not await self.creation_enabled():
            raise CloneManagerError("Clone creation is disabled.")
        owner_id = int(owner_id)
        existing = await clone_db.get_clone_by_owner(owner_id)
        if existing:
            raise CloneManagerError(
                f"You already have @{existing.get('username') or 'a clone bot'}."
            )
        if await clone_db.count_active_clones() >= CLONE_MAX_ACTIVE:
            raise CloneManagerError(
                "The server clone limit has been reached. Contact the owner."
            )
        token = self.extract_token(token)
        if not token:
            raise CloneManagerError("Invalid BotFather token format.")
        bot_id = int(token.split(":", 1)[0])
        if await clone_db.get_clone(bot_id):
            raise CloneManagerError("This bot is already registered.")

        client = None
        try:
            client = await self._new_client(bot_id, token)
            me = client.me or await client.get_me()
            encrypted = self._cipher.encrypt(token)
            document = await clone_db.save_clone(
                owner_id=owner_id,
                bot_id=me.id,
                username=me.username,
                name=me.first_name,
                encrypted_token=encrypted,
                active=True,
            )
            self._register_runtime(me.id, client)
            return document
        except Exception as error:
            if client is not None:
                try:
                    await client.stop()
                except Exception:
                    pass
            safe_error = str(error).replace(token, "[REDACTED]")
            raise CloneManagerError(
                f"Telegram rejected this bot token: {safe_error}"
            ) from error

    def _register_runtime(self, bot_id, client):
        bot_id = int(bot_id)
        self.clients[bot_id] = client
        self.started_at[bot_id] = time.monotonic()
        stream_key = f"clone:{bot_id}"
        multi_clients[stream_key] = client
        work_loads[stream_key] = 0

    def _unregister_runtime(self, bot_id):
        bot_id = int(bot_id)
        from .streaming import drop_clone_streamer

        drop_clone_streamer(bot_id)
        self.clients.pop(bot_id, None)
        self.started_at.pop(bot_id, None)
        stream_key = f"clone:{bot_id}"
        multi_clients.pop(stream_key, None)
        work_loads.pop(stream_key, None)

    async def start_clone(self, document_or_id):
        document = (
            document_or_id
            if isinstance(document_or_id, dict)
            else await clone_db.get_clone(document_or_id)
        )
        if not document:
            raise CloneManagerError("Clone bot was not found.")
        bot_id = int(document["bot_id"])
        async with self._lock(bot_id):
            if self.is_running(bot_id):
                return self.clients[bot_id]
            token = self._cipher.decrypt(document.get("token"))
            try:
                client = await self._new_client(bot_id, token)
                me = client.me or await client.get_me()
                self._register_runtime(bot_id, client)
                await clone_db.update_identity(bot_id, me.username, me.first_name)
                await clone_db.update_runtime(bot_id, active=True, error="")
                return client
            except Exception as error:
                safe_error = str(error).replace(token, "[REDACTED]")
                await clone_db.update_runtime(
                    bot_id,
                    active=False,
                    error=safe_error,
                )
                raise CloneManagerError(safe_error) from error

    async def stop_clone(self, bot_id, deactivate=True):
        bot_id = int(bot_id)
        async with self._lock(bot_id):
            client = self.clients.get(bot_id)
            if client:
                try:
                    await client.stop()
                finally:
                    self._unregister_runtime(bot_id)
            if deactivate:
                await clone_db.update_runtime(bot_id, active=False, error="")

    async def restart_clone(self, bot_id):
        bot_id = int(bot_id)
        await self.stop_clone(bot_id, deactivate=False)
        document = await clone_db.get_clone(bot_id)
        return await self.start_clone(document)

    async def delete_clone(self, bot_id):
        bot_id = int(bot_id)
        await self.stop_clone(bot_id, deactivate=False)
        await clone_db.delete_clone(bot_id)

    async def stop_all(self):
        for bot_id in list(self.clients):
            try:
                await self.stop_clone(bot_id, deactivate=False)
            except Exception:
                logger.exception("Clone %s could not stop cleanly", bot_id)

    def uptime(self, bot_id):
        started = self.started_at.get(int(bot_id))
        return max(0, int(time.monotonic() - started)) if started else 0


clone_manager = CloneManager()
