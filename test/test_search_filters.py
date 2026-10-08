import re
import unittest
import warnings

from search_filters import (
    build_search_pattern,
    display_filter_query,
    extract_episode_numbers,
    make_filter_query,
    matches_filter,
)


class SearchFilterTests(unittest.TestCase):
    def test_dual_and_multi_audio_aliases(self):
        multi = make_filter_query("Pallichattambi", language="multi")
        dual = make_filter_query("Pallichattambi", language="dual")

        self.assertTrue(
            matches_filter(
                "Pallichattambi 2026 1080p WEB DL MULTi DDP5 1 Atmos.mkv",
                multi,
            )
        )
        self.assertTrue(
            matches_filter(
                "Pallichattambi 2026 1080p WEB DL DUAL DDP5 1.mkv",
                dual,
            )
        )
        self.assertFalse(
            matches_filter(
                "Pallichattambi 2026 1080p WEB DL DUAL DDP5 1.mkv",
                multi,
            )
        )

    def test_language_abbreviation_and_full_name(self):
        hindi = make_filter_query("Movie", language="hindi")
        english = make_filter_query("Movie", language="english")

        for filename in ("Movie HIN 720p.mkv", "Movie Hindi 1080p.mkv"):
            self.assertTrue(matches_filter(filename, hindi))
        for filename in ("Movie ENG 720p.mkv", "Movie English 1080p.mkv"):
            self.assertTrue(matches_filter(filename, english))

        self.assertFalse(matches_filter("Movie Behind The Story.mkv", hindi))
        self.assertFalse(matches_filter("Movie Engineer 2026.mkv", english))

    def test_episode_formats_are_equivalent(self):
        filenames = (
            "Elite Force S01E01 1080p.mkv",
            "Elite Force S01 E01 720p.mkv",
            "Elite Force S01-E1 480p.mkv",
            "Elite Force Season 01 Episode 01.mkv",
        )
        for query in (
            "Elite Force S01E01",
            "Elite Force S01 E01",
            "Elite Force S01-E1",
        ):
            for filename in filenames:
                self.assertTrue(
                    bool(re.search(build_search_pattern(query), filename, re.I)),
                    (query, filename),
                )

    def test_episode_button_replaces_old_episode_constraint(self):
        query = make_filter_query("Elite Force S01E09", episode=1)
        self.assertTrue(matches_filter("Elite Force S01 E01 720p.mkv", query))
        self.assertFalse(matches_filter("Elite Force S01 E09 720p.mkv", query))
        self.assertEqual(display_filter_query(query), "Elite Force S01 • E01")

    def test_combined_language_and_episode_filters(self):
        query = make_filter_query("Elite Force S01E01", language="hindi")
        self.assertTrue(
            matches_filter("Elite Force S01 E01 Hindi 1080p.mkv", query)
        )
        self.assertTrue(matches_filter("Elite Force S01-E1 HIN 720p.mkv", query))
        self.assertFalse(
            matches_filter("Elite Force S01 E01 English 1080p.mkv", query)
        )

    def test_combined_episode_ranges_include_every_covered_episode(self):
        filenames = (
            "Show S02E13-E16 1080p Hindi.mkv",
            "Show S02 EP13 to 16 1080p Hindi.mkv",
            "Show S02 E13 16 COMBINED 1080p Hindi.mkv",
        )
        query = make_filter_query("Show S02", episode=16)
        for filename in filenames:
            self.assertIn(16, extract_episode_numbers(filename))
            self.assertTrue(matches_filter(filename, query), filename)

        self.assertFalse(
            matches_filter("Show S02 E13-E15 1080p Hindi.mkv", query)
        )

    def test_all_four_filters_can_be_combined_and_replaced(self):
        query = make_filter_query(
            "Show S01E01 720p English",
            season=2,
            episode=16,
            language="hindi",
            quality="1080p",
        )
        self.assertTrue(
            matches_filter("Show S02E16 Hindi 1080p WEB-DL.mkv", query)
        )
        self.assertTrue(
            matches_filter("Show S02 E13-16 HIN 1080P COMBINED.mkv", query)
        )
        self.assertFalse(
            matches_filter("Show S02E16 English 1080p WEB-DL.mkv", query)
        )
        self.assertFalse(
            matches_filter("Show S02E16 Hindi 720p WEB-DL.mkv", query)
        )
        self.assertEqual(
            display_filter_query(query),
            "Show • Hindi • Season 02 • E16 • 1080P",
        )

    def test_quality_aliases(self):
        four_k = make_filter_query("Movie", quality="2160p")
        two_k = make_filter_query("Movie", quality="1440p")
        self.assertTrue(matches_filter("Movie 4K UHD.mkv", four_k))
        self.assertTrue(matches_filter("Movie 2160P.mkv", four_k))
        self.assertTrue(matches_filter("Movie 2K WEB-DL.mkv", two_k))
        self.assertFalse(matches_filter("Movie 1080P.mkv", four_k))

    def test_combined_files_filter_matches_labels_and_ranges(self):
        query = make_filter_query("Show", combined=True)
        combined_files = (
            "Show S01 E01-E04 1080p.mkv",
            "Show S01 EP01 to EP04 720p.mkv",
            "Show S01 E01 04 COMBINED 480p.mkv",
            "Show Complete Season Pack Hindi.mkv",
        )
        for filename in combined_files:
            self.assertTrue(matches_filter(filename, query), filename)
        self.assertFalse(matches_filter("Show S01E04 1080p.mkv", query))
        self.assertEqual(display_filter_query(query), "Show • Combined Files")

    def test_combined_files_stacks_with_other_filters_and_clears(self):
        query = make_filter_query(
            "Show",
            season=2,
            language="hindi",
            quality="720p",
            combined=True,
        )
        self.assertTrue(
            matches_filter("Show S02 E01-E04 HIN 720P WEB-DL.mkv", query)
        )
        self.assertFalse(
            matches_filter("Show S02 E04 HIN 720P WEB-DL.mkv", query)
        )
        self.assertFalse(
            matches_filter("Show S02 E01-E04 ENG 720P WEB-DL.mkv", query)
        )
        cleared = make_filter_query(query, combined=None)
        self.assertTrue(matches_filter("Show S02 E04 HIN 720P WEB-DL.mkv", cleared))
        self.assertNotIn("[[combined:", cleared)

    def test_generated_patterns_have_no_future_warnings(self):
        queries = (
            "Movie [[language:multi]]",
            "Movie [[language:dual]]",
            "Elite Force S01E01",
            "Elite Force S01 E01",
            "Elite Force [[season:1]] [[episode:1]]",
            "Elite Force [[quality:1080p]]",
            "Elite Force [[combined:1]]",
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", FutureWarning)
            for query in queries:
                re.compile(build_search_pattern(query), re.I)
        self.assertEqual(caught, [])


if __name__ == "__main__":
    unittest.main()
