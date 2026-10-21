"""P1-02: synthetic tests for offline development environment diagnostics."""
import unittest
from pathlib import Path

from scripts.doctor_development_environment import (
    ROOT,
    missing_repository_paths,
    probe_temp_directory,
)


class DevelopmentEnvironmentTests(unittest.TestCase):
    def test_current_repo_has_required_paths(self):
        self.assertEqual(missing_repository_paths(ROOT), [])

    def test_nonexistent_repository_reports_expected_missing_paths(self):
        absent = ROOT / "not-a-repository-for-p1-02"
        self.assertFalse(absent.exists())
        missing = missing_repository_paths(absent)
        self.assertIn("README.md", missing)
        self.assertIn("tests/", missing)

    def test_writable_directory_probe_creates_and_cleans_up(self):
        # Use the checked-out tests directory, not an unreliable default TEMP.
        base = Path(__file__).resolve().parent
        before = set(base.glob("fx-p102-*"))
        self.assertTrue(probe_temp_directory(base))
        self.assertEqual(set(base.glob("fx-p102-*")), before)

    def test_missing_temporary_directory_fails_closed(self):
        absent = Path(__file__).resolve().parent / "no-such-fx-p1-02-temp-directory"
        self.assertFalse(probe_temp_directory(absent))


if __name__ == "__main__":
    unittest.main()
