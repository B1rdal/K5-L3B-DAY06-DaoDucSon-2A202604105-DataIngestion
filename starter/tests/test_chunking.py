"""Chunk coverage, boundaries, stable identity, and page metadata contracts."""
import unittest

from src.chunking import by_paragraph, fixed_size
from src.models import DocumentPage


class ChunkingTests(unittest.TestCase):
    def page(self, text):
        return DocumentPage("sample", "source.pdf", 17, text,
                            {"section": "chapter_1", "nested": {"value": 1}})

    def assert_traceable(self, page, chunks):
        for chunk in chunks:
            self.assertEqual(chunk.text, page.text[chunk.metadata["char_start"]:chunk.metadata["char_end"]])
            self.assertEqual((chunk.document_id, chunk.source, chunk.page),
                             (page.document_id, page.source, page.page))
            self.assertEqual(chunk.metadata["section"], "chapter_1")

    def test_fixed_overlap_and_no_redundant_tail(self):
        page = self.page("abcdefghijkl")
        chunks = fixed_size(page, 5, 2)
        self.assertEqual([chunk.text for chunk in chunks], ["abcde", "defgh", "ghijk", "jkl"])
        self.assert_traceable(page, chunks)
        self.assertEqual([chunk.text for chunk in fixed_size(self.page("abcdefgh"), 5, 2)],
                         ["abcde", "defgh"])

    def test_paragraph_boundaries_are_preferred(self):
        page = self.page("Alpha one.\n\nBeta two.\n\nGamma three.")
        chunks = by_paragraph(page, 22)
        self.assertEqual([chunk.text for chunk in chunks],
                         ["Alpha one.\n\nBeta two.", "Gamma three."])
        self.assert_traceable(page, chunks)

    def test_long_paragraph_uses_words_and_long_words_still_progress(self):
        page = self.page("alpha beta gamma delta " + "z" * 30 + "\n\nSecond paragraph.\n")
        chunks = by_paragraph(page, 10)
        self.assertTrue(all(0 < len(chunk.text) <= 10 for chunk in chunks))
        self.assertEqual("".join("".join(chunk.text.split()) for chunk in chunks),
                         "".join(page.text.split()))
        self.assert_traceable(page, chunks)

    def test_empty_input_and_invalid_parameters(self):
        self.assertEqual(fixed_size(self.page(" \n\t"), 5, 1), [])
        self.assertEqual(by_paragraph(self.page(" \n\t"), 5), [])
        for size, overlap in [(0, 0), (5, -1), (5, 5), (5, 6)]:
            with self.assertRaises(ValueError):
                fixed_size(self.page("text"), size, overlap)
        with self.assertRaises(ValueError):
            by_paragraph(self.page("text"), 0)

    def test_ids_are_stable_but_change_when_source_content_changes(self):
        first = fixed_size(self.page("original"), 5, 1)
        again = fixed_size(self.page("original"), 5, 1)
        changed = fixed_size(self.page("modified"), 5, 1)
        self.assertEqual([c.chunk_id for c in first], [c.chunk_id for c in again])
        self.assertNotEqual(first[0].chunk_id, changed[0].chunk_id)
        first[0].metadata["nested"]["value"] = 99
        self.assertEqual(first[1].metadata["nested"]["value"], 1)

    def test_whitespace_and_unicode_do_not_lose_content(self):
        for text in ["A", "  A\n", "A  \n\nB\t\n", "\n\nCafé đẹp.\n\nEnd.", "word " * 40]:
            page = self.page(text)
            chunks = by_paragraph(page, 9)
            self.assertEqual("".join("".join(chunk.text.split()) for chunk in chunks),
                             "".join(text.split()))
            self.assert_traceable(page, chunks)
