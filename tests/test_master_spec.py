"""Unit tests for the Q111 index checker."""
import unittest

from scripts.check_master_spec import check_index


class MasterIndexTests(unittest.TestCase):
    def test_complete_and_in_order(self):
        text = "\n".join(f"| Q{i} | decision | field |" for i in range(1, 111))
        self.assertEqual(check_index(text), [])

    def test_detects_missing_entry(self):
        text = "\n".join(f"| Q{i} | decision | field |" for i in range(1, 110))
        self.assertIn("Missing Q numbers", "\n".join(check_index(text)))

    def test_detects_duplicates(self):
        text = "\n".join(f"| Q{i} | decision | field |" for i in range(1, 111))
        self.assertIn("Duplicate Q numbers", "\n".join(check_index(text + "\n| Q110 | duplicate | field |")))

    def test_detects_out_of_order(self):
        rows = [f"| Q{i} | decision | field |" for i in range(1, 111)]
        rows[0], rows[1] = rows[1], rows[0]
        self.assertIn("ascending order", "\n".join(check_index("\n".join(rows))))


if __name__ == "__main__":
    unittest.main()
