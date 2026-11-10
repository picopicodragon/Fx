"""CI regression: prevent a false-green Linux job when unittest is skipped.

Under bash -o pipefail, a pipeline of find | grep -q can return 141
because grep exits before find finishes writing a large test directory.
"""
import unittest
from pathlib import Path


class GitHubCiDiscoveryTests(unittest.TestCase):
    def test_linux_workflow_must_run_unit_tests_not_sigpipe_skip(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("python -m unittest discover -s tests", source)
        self.assertIn("-print -quit", source)
        self.assertNotIn("find tests -type f -name 'test*.py' | grep -q .", source)
        self.assertIn("Refusing a false-green check.", source)
        self.assertIn("exit 1", source)

    def test_windows_workflow_still_tests_all(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn('python -m unittest discover -s tests -p "test*.py"', source)


if __name__ == "__main__":
    unittest.main()
