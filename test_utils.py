"""
Unit tests for the pure logic in utils.py (no browser needed).
Run: python3 test_utils.py
"""

import tempfile
import unittest
from pathlib import Path

from utils import ApplicationTracker, match_screening_answer


class TestMatchScreeningAnswer(unittest.TestCase):
    def test_matches_case_insensitive_substring(self):
        answers = {"authorized to work": "Yes"}
        self.assertEqual(
            match_screening_answer("Are you AUTHORIZED TO WORK in the US?", answers),
            "Yes",
        )

    def test_no_match_returns_none(self):
        answers = {"authorized to work": "Yes"}
        self.assertIsNone(match_screening_answer("What is your favorite color?", answers))

    def test_empty_question_returns_none(self):
        self.assertIsNone(match_screening_answer("", {"salary": "120000"}))
        self.assertIsNone(match_screening_answer(None, {"salary": "120000"}))


class TestApplicationTracker(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.tmpdir.name) / "applications.csv"
        self.tracker = ApplicationTracker(csv_path=self.csv_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_log_and_dedup(self):
        self.tracker.log("Python Dev", "Acme", "Remote", "https://dice.com/job/1", "applied")
        urls = self.tracker.get_all_applied_urls()
        self.assertIn("https://dice.com/job/1", urls)

    def test_needs_review_not_counted_as_applied(self):
        self.tracker.log("Java Dev", "", "", "https://dice.com/job/2", "needs_review", "unanswered question")
        urls = self.tracker.get_all_applied_urls()
        self.assertNotIn("https://dice.com/job/2", urls)

    def test_summary_counts(self):
        self.tracker.log("A", "", "", "u1", "applied")
        self.tracker.log("B", "", "", "u2", "skipped")
        self.tracker.log("C", "", "", "u3", "failed")
        summary = self.tracker.summary()
        self.assertEqual(summary, {"applied": 1, "skipped": 1, "failed": 1})


if __name__ == "__main__":
    unittest.main()
