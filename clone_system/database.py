"""MongoDB persistence for clone bots and their private media catalogues."""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from info import (
    CLONE_SEARCH_SCAN_LIMIT,
    DATABASE_NAME,
    DATABASE_URI,
)
from search_filters import (
    build_search_pattern,
    make_filter_query,
    matches_filter,
    parse_filter_query,
)


UTC = timezone.utc


def searchable_file_name(file_name):
    """Return a punctuation-insensitive search value without changing display."""
    value = re.sub(r"[\[\]{}()_\-.+]+", " ", str(file_name or ""))
    return re.sub(r"\s+", " ", value).strip()


def utcnow():
    return datetime.now(UTC)


def default_clone_settings():
    return {
        "start_message": (
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
        ),
        "start_photo": "assets/rdx-welcome-banner.jpg",
        "log_channel": None,
        "index_channels": [],
        "delete_channels": [],
        "admins": [],
        "pm_search": True,
        "group_search": True,
        "auto_filter": True,
        "protect_content": False,
        "auto_delete": True,
        "delete_time": 600,
        "custom_caption": (
            "<b>🎬 {file_name}</b>\n\n"
            "<b>📦 Size:</b> {file_size}\n\n"
            "<b>⚜️ Powered by {bot_name}</b>"
        ),
        "force_sub_channels": [],
        "custom_button_text": "",
        "custom_button_url": "",
        "fallback_thumbnail": "",
        "stream_mode": True,
        "verification": False,
        "verify_access_hours": 24,
        "verify_token_minutes": 15,
        "shortlink_domain": "",
        "shortlink_api_encrypted": "",
        "tutorial_url": "",
        "support_url": "",
        "updates_url": "",
        "bot_mode": "both",
    }


def _record_text(record):
    return " ".join(
        str(record.get(key) or "")
        for key in ("file_name", "caption")
    )


class CloneDatabase:
    def __init__(self, uri=DATABASE_URI, database_name=DATABASE_NAME):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[database_name]
        self.clones = self.db.clone_bots
        self.media = self.db.clone_media
        self.users = self.db.clone_users
        self.premium = self.db.clone_premium
        self.verification = self.db.clone_verification
        self.referrals = self.db.clone_referrals
        self.system_settings = self.db.clone_system_settings

    async def ensure_indexes(self):
        await self.clones.create_index("bot_id", unique=True)
        await self.clones.create_index("owner_id", unique=True)
        await self.clones.create_index([("active", 1), ("updated_at", -1)])
        await self.media.create_index(
            [("clone_id", 1), ("record_key", 1)],
            unique=True,
        )
        await self.media.create_index(
            [("clone_id", 1), ("file_name", 1)]
        )
        await self.media.create_index(
            [("clone_id", 1), ("created_at", -1)]
        )
        await self.users.create_index(
            [("clone_id", 1), ("user_id", 1)],
            unique=True,
        )
        await self.premium.create_index(
            [("clone_id", 1), ("user_id", 1)],
            unique=True,
        )
        await self.verification.create_index("token_hash", unique=True)
        await self.verification.create_index("expires_at", expireAfterSeconds=0)
        await self.referrals.create_index(
            [("clone_id", 1), ("referred_id", 1)],
            unique=True,
        )

    async def clone_creation_enabled(self, default=True):
        document = await self.system_settings.find_one(
            {"_id": "global"},
            {"clone_creation_enabled": 1},
        )
        if not document or "clone_creation_enabled" not in document:
            return bool(default)
        return bool(document["clone_creation_enabled"])

    async def set_clone_creation_enabled(self, enabled):
        enabled = bool(enabled)
        await self.system_settings.update_one(
            {"_id": "global"},
            {
                "$set": {
                    "clone_creation_enabled": enabled,
                    "updated_at": utcnow(),
                }
            },
            upsert=True,
        )
        return enabled

    async def count_active_clones(self):
        return await self.clones.count_documents({"active": True})

    async def get_active_clones(self, limit):
        cursor = self.clones.find(
            {"active": True, "deleted": {"$ne": True}}
        ).sort("updated_at", 1).limit(int(limit))
        return await cursor.to_list(length=int(limit))

    async def get_clone(self, bot_id):
        return await self.clones.find_one(
            {"bot_id": int(bot_id), "deleted": {"$ne": True}}
        )

    async def get_clone_by_owner(self, owner_id):
        return await self.clones.find_one(
            {"owner_id": int(owner_id), "deleted": {"$ne": True}}
        )

    async def save_clone(
        self,
        *,
        owner_id,
        bot_id,
        username,
        name,
        encrypted_token,
        active=True,
    ):
        now = utcnow()
        existing = await self.get_clone_by_owner(owner_id)
        settings = (
            existing.get("settings", default_clone_settings())
            if existing
            else default_clone_settings()
        )
        await self.clones.update_one(
            {"owner_id": int(owner_id)},
            {
                "$set": {
                    "bot_id": int(bot_id),
                    "username": str(username or ""),
                    "name": str(name or "RDX Clone Bot"),
                    "token": encrypted_token,
                    "active": bool(active),
                    "deleted": False,
                    "settings": settings,
                    "last_error": "",
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                    "plan": "free",
                },
            },
            upsert=True,
        )
        return await self.get_clone(bot_id)

    async def update_runtime(self, bot_id, *, active=None, error=None):
        fields = {"updated_at": utcnow()}
        if active is not None:
            fields["active"] = bool(active)
        if error is not None:
            fields["last_error"] = str(error)[:1000]
        await self.clones.update_one(
            {"bot_id": int(bot_id)},
            {"$set": fields},
        )

    async def update_identity(self, bot_id, username, name):
        await self.clones.update_one(
            {"bot_id": int(bot_id)},
            {
                "$set": {
                    "username": str(username or ""),
                    "name": str(name or "RDX Clone Bot"),
                    "updated_at": utcnow(),
                }
            },
        )

    async def update_settings(self, bot_id, updates):
        updates = dict(updates or {})
        if not updates:
            return await self.get_clone(bot_id)
        fields = {
            f"settings.{key}": value
            for key, value in updates.items()
        }
        fields["updated_at"] = utcnow()
        await self.clones.update_one(
            {"bot_id": int(bot_id)},
            {"$set": fields},
        )
        return await self.get_clone(bot_id)

    async def delete_clone(self, bot_id):
        bot_id = int(bot_id)
        await self.media.delete_many({"clone_id": bot_id})
        await self.users.delete_many({"clone_id": bot_id})
        await self.premium.delete_many({"clone_id": bot_id})
        await self.verification.delete_many({"clone_id": bot_id})
        await self.referrals.delete_many({"clone_id": bot_id})
        await self.clones.delete_one({"bot_id": bot_id})

    async def add_user(self, clone_id, user):
        if user is None:
            return False
        result = await self.users.update_one(
            {"clone_id": int(clone_id), "user_id": int(user.id)},
            {
                "$set": {
                    "first_name": str(user.first_name or ""),
                    "username": str(user.username or ""),
                    "last_seen": utcnow(),
                },
                "$setOnInsert": {"joined_at": utcnow()},
            },
            upsert=True,
        )
        return result.upserted_id is not None

    async def user_count(self, clone_id):
        return await self.users.count_documents({"clone_id": int(clone_id)})

    @staticmethod
    def media_key(clone_id, file_id):
        payload = f"{int(clone_id)}:{file_id}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:18]

    async def save_media(
        self,
        clone_id,
        media,
        source_message,
        file_type=None,
    ):
        file_id = str(media.file_id)
        record_key = self.media_key(clone_id, file_id)
        thumbs = []
        for attribute in (
            "video_cover",
            "cover",
            "covers",
            "video_thumbs",
            "thumbs",
        ):
            value = getattr(media, attribute, None)
            if not value:
                continue
            if isinstance(value, (list, tuple)):
                thumbs.extend(value)
            else:
                thumbs.append(value)
        largest_thumb = None
        if thumbs:
            largest_thumb = max(
                thumbs,
                key=lambda item: (
                    (getattr(item, "width", 0) or 0)
                    * (getattr(item, "height", 0) or 0),
                    getattr(item, "file_size", 0) or 0,
                ),
            )
        file_name = (
            getattr(media, "file_name", None)
            or f"Telegram_File_{record_key}"
        )
        now = utcnow()
        await self.media.update_one(
            {"clone_id": int(clone_id), "record_key": record_key},
            {
                "$set": {
                    "file_id": file_id,
                    "file_name": str(file_name),
                    "original_file_name": str(file_name),
                    "search_name": searchable_file_name(file_name),
                    "file_size": int(getattr(media, "file_size", 0) or 0),
                    "file_type": str(file_type or "document"),
                    "mime_type": str(
                        getattr(media, "mime_type", None) or ""
                    ),
                    "caption": str(
                        getattr(
                            getattr(source_message, "caption", None),
                            "html",
                            getattr(source_message, "caption", None),
                        )
                        or ""
                    ),
                    "source_chat_id": int(source_message.chat.id),
                    "source_message_id": int(source_message.id),
                    "thumb_file_id": (
                        (
                            largest_thumb
                            if isinstance(largest_thumb, str)
                            else getattr(largest_thumb, "file_id", None)
                        )
                        if largest_thumb
                        else None
                    ),
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return record_key

    async def delete_media_by_file_id(self, clone_id, file_id):
        result = await self.media.delete_many(
            {"clone_id": int(clone_id), "file_id": str(file_id)}
        )
        return result.deleted_count

    async def get_media(self, clone_id, record_key):
        return await self.media.find_one(
            {
                "clone_id": int(clone_id),
                "record_key": str(record_key),
            }
        )

    async def media_count(self, clone_id):
        return await self.media.count_documents({"clone_id": int(clone_id)})

    def _mongo_filter(self, clone_id, query):
        pattern = re.compile(
            build_search_pattern(query),
            flags=re.IGNORECASE,
        )
        return {
            "clone_id": int(clone_id),
            "$or": [
                {"file_name": pattern},
                {"original_file_name": pattern},
                {"search_name": pattern},
                {"caption": pattern},
            ],
        }

    async def search_media(self, clone_id, query, offset=0, limit=10):
        query = str(query or "").strip()
        offset = max(0, int(offset or 0))
        limit = max(1, int(limit or 10))
        _, selected = parse_filter_query(query)
        episode_filter = bool(selected.get("episode"))
        candidate_query = (
            make_filter_query(query, episode=None)
            if episode_filter
            else query
        )
        mongo_filter = self._mongo_filter(clone_id, candidate_query)

        if episode_filter:
            cursor = self.media.find(mongo_filter).sort("created_at", -1)
            candidates = await cursor.to_list(
                length=CLONE_SEARCH_SCAN_LIMIT
            )
            records = [
                item
                for item in candidates
                if matches_filter(_record_text(item), query)
            ]
            total = len(records)
            return records[offset:offset + limit], total

        total = await self.media.count_documents(mongo_filter)
        cursor = (
            self.media.find(mongo_filter)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return await cursor.to_list(length=limit), total

    async def all_matching_media(self, clone_id, query):
        cursor = self.media.find(
            self._mongo_filter(clone_id, query)
        ).sort("created_at", -1)
        candidates = await cursor.to_list(length=CLONE_SEARCH_SCAN_LIMIT)
        return [
            item
            for item in candidates
            if matches_filter(_record_text(item), query)
        ]

    async def add_premium(self, clone_id, user_id, days):
        expires_at = utcnow() + timedelta(days=max(1, int(days)))
        await self.premium.update_one(
            {"clone_id": int(clone_id), "user_id": int(user_id)},
            {"$set": {"expires_at": expires_at, "updated_at": utcnow()}},
            upsert=True,
        )
        return expires_at

    async def remove_premium(self, clone_id, user_id):
        await self.premium.delete_one(
            {"clone_id": int(clone_id), "user_id": int(user_id)}
        )

    async def is_premium(self, clone_id, user_id):
        item = await self.premium.find_one(
            {"clone_id": int(clone_id), "user_id": int(user_id)}
        )
        if not item:
            return False
        expires_at = item.get("expires_at")
        if expires_at and expires_at.replace(tzinfo=UTC) > utcnow():
            return True
        await self.remove_premium(clone_id, user_id)
        return False

    async def create_verification(
        self,
        clone_id,
        user_id,
        record_key,
        token_minutes,
    ):
        token = secrets.token_urlsafe(24)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = utcnow() + timedelta(minutes=max(1, int(token_minutes)))
        await self.verification.insert_one(
            {
                "token_hash": token_hash,
                "clone_id": int(clone_id),
                "user_id": int(user_id),
                "record_key": str(record_key),
                "expires_at": expires_at,
                "created_at": utcnow(),
            }
        )
        return token

    async def consume_verification(self, clone_id, user_id, token):
        token_hash = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
        item = await self.verification.find_one_and_delete(
            {
                "token_hash": token_hash,
                "clone_id": int(clone_id),
                "user_id": int(user_id),
                "expires_at": {"$gt": utcnow()},
            }
        )
        return item

    async def grant_verified_access(self, clone_id, user_id, hours):
        await self.users.update_one(
            {"clone_id": int(clone_id), "user_id": int(user_id)},
            {
                "$set": {
                    "verified_until": utcnow()
                    + timedelta(hours=max(1, int(hours)))
                }
            },
            upsert=True,
        )

    async def is_verified(self, clone_id, user_id):
        user = await self.users.find_one(
            {"clone_id": int(clone_id), "user_id": int(user_id)}
        )
        expires = (user or {}).get("verified_until")
        return bool(expires and expires.replace(tzinfo=UTC) > utcnow())

    async def add_referral(self, clone_id, inviter_id, referred_id):
        if int(inviter_id) == int(referred_id):
            return 0
        try:
            await self.referrals.insert_one(
                {
                    "clone_id": int(clone_id),
                    "inviter_id": int(inviter_id),
                    "referred_id": int(referred_id),
                    "created_at": utcnow(),
                }
            )
        except Exception:
            return 0
        count = await self.referrals.count_documents(
            {"clone_id": int(clone_id), "inviter_id": int(inviter_id)}
        )
        return count * 10


clone_db = CloneDatabase()
