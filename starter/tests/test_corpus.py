import unittest

from src.corpus import prepare_pages
from src.models import DocumentPage


class CorpusTests(unittest.TestCase):
    def test_selection_preserves_short_prose_and_removes_exact_footer(self):
        pages = [DocumentPage("doc", "source.pdf", number, text) for number, text in [
            (1, "Credits"), (2, "Chapter 1 - Start\n\nHello.\n\nGlucose Translations 2"),
            (3, "Glucose Translations 3"), (4, "A short sentence."),
            (5, "[1]: Translator commentary."),
        ]]
        config = {"document_id": "doc", "section_source": "fixture contents",
                  "sections": [{"name": "chapter_1", "start_page": 2, "end_page": 5,
                                "heading_prefix": "Chapter 1 -"}]}
        prepared, audit = prepare_pages(pages, config)
        self.assertEqual([page.page for page in prepared], [2, 4])
        self.assertNotIn("Glucose Translations", prepared[0].text)
        self.assertIn("Glucose Translations", pages[1].text)
        self.assertEqual(prepared[0].metadata["section"], "chapter_1")
        self.assertEqual(len(audit), 5)
        config["sections"][0]["heading_prefix"] = "Wrong heading"
        with self.assertRaisesRegex(ValueError, "heading could not be verified"):
            prepare_pages(pages, config)
