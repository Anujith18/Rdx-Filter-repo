import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PrimaryButtonTests(unittest.TestCase):
    def test_primary_button_patch_is_enabled_before_bot_start(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn(
            "from button_style import enable_primary_buttons",
            source,
        )
        self.assertIn("enable_primary_buttons()", source)
        self.assertLess(
            source.index("enable_primary_buttons()"),
            source.index("async def rdx_start()"),
        )

    def test_all_repository_inline_buttons_are_covered(self):
        supported_fields = {
            "text",
            "callback_data",
            "url",
            "switch_inline_query",
            "switch_inline_query_current_chat",
        }
        found = 0
        for path in ROOT.rglob("*.py"):
            if "tests" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "id", None) or getattr(
                    node.func,
                    "attr",
                    None,
                )
                if name != "InlineKeyboardButton":
                    continue
                found += 1
                fields = {item.arg for item in node.keywords if item.arg}
                self.assertTrue(
                    fields <= supported_fields,
                    f"Unsupported button type in {path}:{node.lineno}: "
                    f"{sorted(fields - supported_fields)}",
                )
        self.assertGreater(found, 600)

    def test_primary_mtproto_constructors_and_flag_are_present(self):
        source = (ROOT / "button_style.py").read_text(encoding="utf-8")
        self.assertIn("ID = 0x4FDD3430", source)
        self.assertIn("ID = 0xE62BC960", source)
        self.assertIn("ID = 0xD80C25EC", source)
        self.assertIn("ID = 0x991399FC", source)
        self.assertIn("_STYLE_FLAG = 1 << 10", source)
        self.assertIn("InlineKeyboardButton.write = _write_primary_button", source)


if __name__ == "__main__":
    unittest.main()
