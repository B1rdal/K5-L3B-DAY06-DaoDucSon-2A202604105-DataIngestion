import unittest

from src.chunking import sentence_windows
from src.models import DocumentPage
from src.retrieval import reciprocal_rank_fusion


class ImprovedRetrievalTests(unittest.TestCase):
    def test_windows_preserve_all_characters_and_offsets(self):
        for text in ["", "  ", "Short.", "One sentence. Another sentence! " * 30,
                     "z" * 250, "Long sentence without punctuation " * 40,
                     "  Café.\n\nNext paragraph?\n" * 20]:
            page = DocumentPage("doc", "file.pdf", 9, text, {"section": "test"})
            chunks = sentence_windows(page, 80, 20)
            covered = set()
            starts = []
            for chunk in chunks:
                start, end = chunk.metadata["char_start"], chunk.metadata["char_end"]
                self.assertEqual(chunk.text, text[start:end])
                self.assertLessEqual(len(chunk.text), 80)
                self.assertEqual(chunk.metadata["section"], "test")
                covered.update(range(start, end))
                starts.append(start)
            self.assertEqual(starts, sorted(set(starts)))
            self.assertTrue(all(i in covered for i, char in enumerate(text) if not char.isspace()))

    def test_windows_overlap_and_keep_sentence_boundaries(self):
        page = DocumentPage("doc", "file.pdf", 9, "First sentence ends. Second sentence ends. Third sentence ends.")
        chunks = sentence_windows(page, 45, 20)
        self.assertTrue(len(chunks) > 1)
        self.assertTrue(all(chunk.text.endswith(".") for chunk in chunks))
        self.assertLess(chunks[1].metadata["char_start"], chunks[0].metadata["char_end"])
        self.assertEqual([c.chunk_id for c in chunks], [c.chunk_id for c in sentence_windows(page, 45, 20)])

    def test_invalid_window_settings_fail(self):
        page = DocumentPage("doc", "file.pdf", 1, "text")
        for size, overlap in [(0, 0), (10, 10), (10, -1)]:
            with self.assertRaises(ValueError):
                sentence_windows(page, size, overlap)

    def test_fusion_uses_ranks_and_does_not_double_count_duplicates(self):
        def hit(key, score):
            return {"chunk_id": key, "score": score, "text": key}
        dense = [hit("a", 0.99), hit("b", 0.2), hit("b", 0.1)]
        lexical = [hit("b", 1000), hit("c", 900)]
        fused = reciprocal_rank_fusion([dense, lexical], 3)
        self.assertEqual(fused[0]["chunk_id"], "b")
        self.assertAlmostEqual(fused[0]["score"], 1/62 + 1/61)
        self.assertEqual(fused[0]["retriever_ranks"], {"0": 2, "1": 1})
