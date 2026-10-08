import asyncio
import unittest

from start_ui import ANIMATION_STYLES, play_start_animation, send_start_welcome


class FakeLoadingMessage:
    def __init__(self, fail_delete=False):
        self.frames = []
        self.fail_delete = fail_delete

    async def edit_text(self, text):
        self.frames.append(text)
        return self

    async def delete(self):
        if self.fail_delete:
            raise RuntimeError("delete failed")


class FakeMessage:
    def __init__(self, photo_failures=0, fail_delete=False):
        self.photo_failures = photo_failures
        self.fail_delete = fail_delete
        self.photo_attempts = []
        self.text_messages = []
        self.loading = None

    async def reply_text(self, text=None, **kwargs):
        self.text_messages.append(text)
        self.loading = FakeLoadingMessage(fail_delete=self.fail_delete)
        return self.loading

    async def reply_photo(self, photo=None, **kwargs):
        self.photo_attempts.append(photo)
        if len(self.photo_attempts) <= self.photo_failures:
            raise RuntimeError("photo failed")
        return {"photo": photo, **kwargs}


class StartUiTests(unittest.IsolatedAsyncioTestCase):
    async def test_animation_cleanup_failure_does_not_raise(self):
        message = FakeMessage(fail_delete=True)
        result = await play_start_animation(
            message,
            style="minimal",
            delay=0,
        )
        self.assertIsNotNone(result)
        self.assertEqual(
            len(result.frames),
            len(ANIMATION_STYLES["minimal"]) - 1,
        )

    async def test_welcome_uses_bundled_fallback_photo(self):
        message = FakeMessage(photo_failures=1)
        result = await send_start_welcome(
            message,
            photo_sources=["broken-photo"],
            caption="Welcome",
            reply_markup="buttons",
            parse_mode="html",
        )
        self.assertEqual(len(message.photo_attempts), 2)
        self.assertIn("rdx-welcome-banner.jpg", result["photo"])

    async def test_welcome_falls_back_to_text(self):
        message = FakeMessage(photo_failures=99)
        result = await send_start_welcome(
            message,
            photo_sources=["broken-photo"],
            caption="Welcome",
            reply_markup="buttons",
            parse_mode="html",
        )
        self.assertIsInstance(result, FakeLoadingMessage)
        self.assertEqual(message.text_messages[-1], "Welcome")


if __name__ == "__main__":
    unittest.main()
