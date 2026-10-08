import os
import sys
import types
import unittest
from unittest.mock import patch


if "pyrogram" not in sys.modules:
    pyrogram_module = types.ModuleType("pyrogram")
    errors_module = types.ModuleType("pyrogram.errors")

    class FloodWait(Exception):
        value = 0

    errors_module.FloodWait = FloodWait
    pyrogram_module.errors = errors_module
    sys.modules["pyrogram"] = pyrogram_module
    sys.modules["pyrogram.errors"] = errors_module

from media_delivery import send_media_preserve_thumb


class Record:
    file_name = "Yumis Cells S03 E06 Hindi Korean WEB DL x265 720p RDX mkv"
    file_size = 340400000
    file_type = "video"
    source_chat_id = -100123
    source_message_id = 77
    thumb_file_id = "stored-thumb"


class LegacyRecord:
    file_name = "Yumis Cells S03 E06 Hindi Korean WEB DL x265 720p RDX mkv"
    file_size = 340400000
    file_type = "video"
    source_chat_id = None
    source_message_id = None
    thumb_file_id = None


class FakeClient:
    def __init__(self, copy_fails=False, search_results=None):
        self.copy_fails = copy_fails
        self.search_results = search_results or []
        self.calls = []

    async def forward_messages(self, **kwargs):
        self.calls.append(("forward_messages", kwargs))
        if self.copy_fails:
            raise RuntimeError("raw copy failed")
        return {"method": "raw-copy", **kwargs}

    async def copy_message(self, **kwargs):
        self.calls.append(("copy_message", kwargs))
        if self.copy_fails:
            raise RuntimeError("copy failed")
        return {"method": "copy", **kwargs}

    async def get_messages(self, *args):
        self.calls.append(("get_messages", args))
        return type(
            "Message",
            (),
            {
                "empty": True,
                "media": None,
            },
        )()

    async def download_media(self, message, file_name):
        self.calls.append(("download_media", message))
        with open(file_name, "wb") as output:
            output.write(b"jpeg")
        return file_name

    async def send_video(self, **kwargs):
        self.calls.append(("send_video", kwargs))
        return {"method": "video", **kwargs}

    async def send_cached_media(self, **kwargs):
        self.calls.append(("send_cached_media", kwargs))
        return {"method": "cached", **kwargs}

    async def search_messages(self, chat_id, query, limit):
        self.calls.append((
            "search_messages",
            {"chat_id": chat_id, "query": query, "limit": limit},
        ))
        for message in self.search_results:
            yield message


class MediaDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_message_copy_is_always_first(self):
        client = FakeClient()
        result = await send_media_preserve_thumb(
            client,
            chat_id=123,
            file_id="file-id",
            media_record=Record(),
            caption="caption",
        )
        self.assertEqual(result["method"], "raw-copy")
        self.assertEqual(client.calls[0][0], "forward_messages")
        self.assertEqual(result["from_chat_id"], -100123)
        self.assertEqual(result["message_ids"], 77)
        self.assertTrue(result["drop_author"])

    async def test_copy_failure_uses_fresh_stored_thumbnail(self):
        client = FakeClient(copy_fails=True)
        result = await send_media_preserve_thumb(
            client,
            chat_id=123,
            file_id="file-id",
            media_record=Record(),
            caption="caption",
        )
        self.assertEqual(result["method"], "video")
        self.assertEqual(
            os.path.basename(result["video_cover"]),
            "thumb.jpg",
        )
        methods = [method for method, _ in client.calls]
        self.assertEqual(methods[0], "forward_messages")
        self.assertIn("copy_message", methods)
        self.assertIn("download_media", methods)
        self.assertIn("send_video", methods)

    async def test_old_database_row_recovers_and_copies_hd_source(self):
        source_video = types.SimpleNamespace(
            file_id="file-id",
            file_name="Yumis.Cells.S03.E06.Hindi.Korean.WEB-DL.x265.720p.RDX.mkv",
            file_size=340400000,
            thumbs=[types.SimpleNamespace(
                file_id="source-thumb",
                width=1280,
                height=720,
                file_size=90000,
            )],
        )
        source_message = types.SimpleNamespace(
            id=606,
            chat=types.SimpleNamespace(id=-100555),
            empty=False,
            media=types.SimpleNamespace(value="video"),
            video=source_video,
        )
        client = FakeClient(search_results=[source_message])
        legacy_record = LegacyRecord()
        remembered = []

        fake_db = types.ModuleType("database.ia_filterdb")

        async def get_file_details(_file_id):
            return [legacy_record]

        async def update_file_source(file_id, message):
            remembered.append((file_id, message.chat.id, message.id))
            return True

        fake_db.get_file_details = get_file_details
        fake_db.update_file_source = update_file_source
        fake_db.unpack_new_file_id = lambda value: (value, "")

        with patch.dict(sys.modules, {"database.ia_filterdb": fake_db}):
            result = await send_media_preserve_thumb(
                client,
                chat_id=123,
                file_id="file-id",
                media_record=legacy_record,
                caption="caption",
            )

        self.assertEqual(result["method"], "raw-copy")
        self.assertEqual(result["from_chat_id"], -100555)
        self.assertEqual(result["message_ids"], 606)
        self.assertEqual(remembered, [("file-id", -100555, 606)])
        methods = [method for method, _ in client.calls]
        self.assertIn("search_messages", methods)
        self.assertNotIn("send_video", methods)
        self.assertNotIn("send_cached_media", methods)


if __name__ == "__main__":
    unittest.main()
