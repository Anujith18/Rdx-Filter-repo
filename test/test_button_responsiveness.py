import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ButtonResponsivenessTests(unittest.TestCase):
    def test_long_auto_delete_waits_do_not_block_update_workers(self):
        for relative_path in ("plugins/commands.py", "plugins/pmfilter.py"):
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            blocking_waits = re.findall(
                r"await\s+asyncio\.sleep\((?:DELETE_TIME|300|600)\)",
                source,
            )
            self.assertEqual(
                blocking_waits,
                [],
                f"{relative_path} still blocks a worker during auto-delete",
            )

    def test_all_text_mode_filter_results_use_media_safe_edit(self):
        source = (ROOT / "plugins" / "pmfilter.py").read_text(encoding="utf-8")

        self.assertGreaterEqual(source.count("await safe_edit("), 7)
        self.assertIn("await msg.edit_caption(", source)
        self.assertIn("replacement = await msg.reply_text(", source)

    def test_filter_caption_uses_callback_query_not_undefined_message(self):
        source = (ROOT / "utils.py").read_text(encoding="utf-8")
        start = source.index("async def get_cap(")
        end = source.index("\n\nasync def log_error", start)
        get_cap_source = source[start:end]

        self.assertNotIn("message.from_user", get_cap_source)
        self.assertNotIn("{message.chat", get_cap_source)
        self.assertIn("query.from_user", get_cap_source)
        self.assertIn("query.message.chat", get_cap_source)


if __name__ == "__main__":
    unittest.main()
