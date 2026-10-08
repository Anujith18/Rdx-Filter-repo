import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PrivateSearchDeliveryTests(unittest.TestCase):
    def test_private_settings_force_callback_file_buttons(self):
        source = (ROOT / "utils.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "get_settings"
        )
        function_source = ast.get_source_segment(source, function)
        self.assertIn("int(group_id) > 0", function_source)
        self.assertIn("settings['button'] = True", function_source)

    def test_private_file_callback_reuses_start_delivery_flow(self):
        source = (ROOT / "plugins" / "pmfilter.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("class _PrivateStartMessage", source)
        self.assertIn("from .commands import start", source)
        self.assertIn("f\"{ident}_{file_id}\"", source)
        self.assertIn("enums.ChatType.PRIVATE", source)

    def test_private_send_all_uses_direct_delivery_flow(self):
        source = (ROOT / "plugins" / "pmfilter.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('f"allfiles_{key}"', source)
        self.assertIn('(clicked, "allfiles", key)', source)

    def test_private_delivery_has_duplicate_tap_guard(self):
        source = (ROOT / "plugins" / "pmfilter.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("PM_FILE_DELIVERIES.add(delivery_key)", source)
        self.assertIn("PM_FILE_DELIVERIES.discard(delivery_key)", source)


if __name__ == "__main__":
    unittest.main()
