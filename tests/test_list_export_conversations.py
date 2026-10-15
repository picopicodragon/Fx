"""Local export conversation list tests."""
import unittest

from scripts.list_export_conversations import list_conversations


class ConversationListingTests(unittest.TestCase):
    def test_filter_case_insensitive(self):
        data = [{"id": "id1", "title": "FX設計"}, {"id": "id2", "title": "Music"}]
        self.assertEqual(list_conversations(data, "fx"), [("id1", "FX設計")])

    def test_no_broad_guess(self):
        self.assertEqual(list_conversations([], "fx"), [])

    def test_export_not_list(self):
        with self.assertRaises(ValueError):
            list_conversations({"unrecognized": []})


if __name__ == "__main__":
    unittest.main()
