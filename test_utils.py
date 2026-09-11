"""
Unit tests for the pure logic in utils.py (no browser needed).
Run: python3 test_utils.py
"""

import os
import subprocess
import sys
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


class TestInstanceIsolation(unittest.TestCase):
    """config.py derives per-instance paths at import time, so these run in a
    subprocess to avoid polluting the already-imported config module."""

    def _paths_for(self, instance_value):
        code = (
            "import config as c; "
            "print(c.BROWSER_PROFILE_DIR.name, c.CSV_LOG.name, c.LOG_FILE.name, repr(c.BOT_LABEL))"
        )
        env = {**os.environ, "INSTANCE": instance_value}
        env.pop("BOT_LABEL", None)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent), env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip().split()

    def test_blank_instance_keeps_original_paths(self):
        profile, csv, log, label = self._paths_for("")
        self.assertEqual(profile, "browser_data")
        self.assertEqual(csv, "applications.csv")
        self.assertEqual(log, "dice_bot.log")
        self.assertEqual(label, "''")

    def test_named_instance_gets_separate_paths(self):
        profile, csv, log, label = self._paths_for("account2")
        self.assertEqual(profile, "browser_data_account2")
        self.assertEqual(csv, "applications_account2.csv")
        self.assertEqual(log, "dice_bot_account2.log")
        self.assertEqual(label, "'account2'")

    def test_path_traversal_is_stripped(self):
        profile, csv, _, _ = self._paths_for("../../etc/passwd")
        self.assertEqual(profile, "browser_data_etcpasswd")
        self.assertEqual(csv, "applications_etcpasswd.csv")


if __name__ == "__main__":
    unittest.main()
