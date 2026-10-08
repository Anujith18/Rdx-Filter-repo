import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OriginalFilenameTests(unittest.TestCase):
    def test_main_index_keeps_exact_name_and_separate_search_name(self):
        source = (ROOT / "database" / "ia_filterdb.py").read_text()
        self.assertIn("file_name = str(media.file_name or '').strip()", source)
        self.assertIn("original_file_name=file_name", source)
        self.assertIn("search_name=search_name", source)
        self.assertIn("{'search_name': regex}", source)
        self.assertNotIn(
            "file_name = clean_index_name(media.file_name)",
            source,
        )

    def test_main_result_does_not_truncate_or_strip_original_name(self):
        source = (ROOT / "plugins" / "pmfilter.py").read_text()
        self.assertIn('getattr(file, "original_file_name", None)', source)
        self.assertNotIn("clean_name[:67]", source)

    def test_clone_index_keeps_exact_and_searchable_names(self):
        source = (ROOT / "clone_system" / "database.py").read_text()
        self.assertIn('"original_file_name": str(file_name)', source)
        self.assertIn('"search_name": searchable_file_name(file_name)', source)
        self.assertIn('{"search_name": pattern}', source)


if __name__ == "__main__":
    unittest.main()
