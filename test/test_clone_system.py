import importlib.util
import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


security = load_module(
    "rdx_clone_security_test",
    ROOT / "clone_system" / "security.py",
)
class CloneSystemTests(unittest.TestCase):
    def test_bot_tokens_are_encrypted_at_rest(self):
        token = "1234567890:" + ("A" * 35)
        encrypted = security.TokenCipher().encrypt(token)
        self.assertNotIn(token, encrypted)
        self.assertEqual(
            security.TokenCipher().decrypt(encrypted),
            token,
        )

    def test_permanent_media_links_are_signed(self):
        signature = security.sign_media(1234567890, "abc123record")
        self.assertTrue(
            security.valid_media_signature(
                1234567890,
                "abc123record",
                signature,
            )
        )
        self.assertFalse(
            security.valid_media_signature(
                1234567891,
                "abc123record",
                signature,
            )
        )

    def test_private_media_keys_are_tenant_specific(self):
        source = (ROOT / "clone_system" / "database.py").read_text()
        self.assertIn('f"{int(clone_id)}:{file_id}"', source)
        self.assertIn("hexdigest()[:18]", source)
        self.assertIn('"clone_id": int(clone_id)', source)

    def test_clone_defaults_are_private_and_safe(self):
        tree = ast.parse(
            (ROOT / "clone_system" / "database.py").read_text()
        )
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "default_clone_settings"
        )
        settings = ast.literal_eval(function.body[0].value)
        self.assertEqual(settings["index_channels"], [])
        self.assertEqual(settings["admins"], [])
        self.assertFalse(settings["protect_content"])
        self.assertTrue(settings["auto_delete"])
        self.assertTrue(settings["stream_mode"])
        self.assertIn(
            "Your personal movie and series library is ready!",
            settings["start_message"],
        )
        self.assertIn(
            "Simply send the name of your desired movie or series",
            settings["start_message"],
        )
        self.assertEqual(settings["start_message"].count("{bot_name}"), 2)
        self.assertIn("{user}", settings["start_message"])

    def test_clone_start_fallback_matches_the_new_default_copy(self):
        source = (ROOT / "clone_system" / "ui.py").read_text()
        self.assertIn(
            "Your personal movie and series library is ready!",
            source,
        )
        self.assertIn(
            "Simply send the name of your desired movie or series",
            source,
        )

    def test_botfather_forward_token_pattern_is_present(self):
        source = (ROOT / "clone_system" / "manager.py").read_text()
        self.assertIn("TOKEN_RE", source)
        self.assertIn("extract_token", source)
        self.assertIn("Invalid BotFather token format", source)

    def test_callbacks_fit_telegram_limit(self):
        sources = "\n".join(
            (ROOT / "clone_system" / name).read_text()
            for name in ("ui.py", "handlers.py", "search.py")
        )
        literals = re.findall(
            r"""callback_data\s*=\s*["']([^"'{}]+)["']""",
            sources,
        )
        self.assertTrue(literals)
        for value in literals:
            self.assertLessEqual(len(value.encode()), 64)

    def test_clone_web_routes_precede_generic_catch_all(self):
        route_source = (ROOT / "plugins" / "route.py").read_text()
        clone_position = route_source.index('"/clone/file/')
        catch_all_position = route_source.index('@routes.get(r"/{path:')
        self.assertLess(clone_position, catch_all_position)

    def test_token_is_redacted_from_start_failure(self):
        source = (ROOT / "clone_system" / "manager.py").read_text()
        self.assertIn('.replace(token, "[REDACTED]")', source)
        self.assertNotIn("logger.info(token", source)
        self.assertNotIn("logger.error(token", source)

    def test_long_clone_auto_delete_does_not_block_workers(self):
        source = (ROOT / "clone_system" / "handlers.py").read_text()
        self.assertIn("background(delete_later(", source)
        self.assertNotRegex(
            source,
            r"await\s+asyncio\.sleep\(\s*settings\.get\(\"delete_time\"",
        )

    def test_owner_guard_is_used_for_management_callbacks(self):
        source = (ROOT / "clone_system" / "handlers.py").read_text()
        self.assertIn(
            "Only the clone owner or an authorized admin can use this.",
            source,
        )
        self.assertIn("if not privileged(config, query.from_user.id)", source)

    def test_clone_admin_toggle_is_persistent_and_admin_only(self):
        commands = (ROOT / "plugins" / "commands.py").read_text()
        manager = (ROOT / "plugins" / "clone_manager.py").read_text()
        database = (ROOT / "clone_system" / "database.py").read_text()
        self.assertIn(
            "'👨‍💻 CREATE / MANAGE OWN CLONE 👨‍💻'",
            commands,
        )
        self.assertIn("🤖 CLONE SYSTEM:", commands)
        self.assertIn("cloneadmin:toggle:", commands)
        self.assertIn("filters.regex(r\"^cloneadmin:\")", manager)
        self.assertIn(
            "query.from_user.id not in {int(value) for value in ADMINS}",
            manager,
        )
        self.assertIn("clone_creation_enabled", database)
        self.assertIn("set_clone_creation_enabled", database)

    def test_clone_results_are_text_links_with_full_names(self):
        source = (ROOT / "clone_system" / "search.py").read_text()
        self.assertIn("<a href='{file_url}'>", source)
        self.assertIn('record.get("original_file_name")', source)
        self.assertNotIn("text[:55] + \"...\"", source)


if __name__ == "__main__":
    unittest.main()
