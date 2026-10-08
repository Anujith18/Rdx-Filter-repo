import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from verification_ui import (
    verification_expired_text,
    verification_owner_mismatch_text,
    verification_required_text,
    verification_success_text,
)


class VerificationUiTests(unittest.TestCase):
    def test_required_card_is_english_and_contains_requested_copy(self):
        text = verification_required_text("RDX User", 24, 15)

        self.assertIn(
            "To download your requested file, complete one quick verification.",
            text,
        )
        self.assertIn("15 Minutes", text)
        self.assertIn("24 Hours", text)
        self.assertNotRegex(text, r"[\u0900-\u097f]")
        self.assertNotRegex(text, r"[\u0980-\u09ff]")

    def test_user_name_is_html_escaped(self):
        text = verification_required_text("<RDX & User>", 24, 15)
        self.assertIn("&lt;RDX &amp; User&gt;", text)

    def test_success_card_displays_expiry(self):
        expiry = datetime(2026, 7, 30, 21, 45, tzinfo=ZoneInfo("Asia/Kolkata"))
        text = verification_success_text("RDX User", expiry)

        self.assertIn("VERIFICATION COMPLETED", text)
        self.assertIn("30 Jul 2026, 09:45 PM", text)
        self.assertIn("GET REQUESTED FILE", text)

    def test_invalid_cards_are_clear_english(self):
        self.assertIn("expired or was already used", verification_expired_text())
        self.assertIn(
            "belongs to another user",
            verification_owner_mismatch_text(),
        )

    def test_old_mixed_language_verification_copy_was_removed(self):
        commands = (
            Path(__file__).resolve().parents[1] / "plugins" / "commands.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("YOU ARE NOT VERIFIED", commands)
        self.assertNotIn("Invalid link or Expired link", commands)
        self.assertNotIn("इस BOT से MOVIE", commands)
        self.assertEqual(
            commands.count("await _send_verification_required(client"),
            3,
        )


if __name__ == "__main__":
    unittest.main()
