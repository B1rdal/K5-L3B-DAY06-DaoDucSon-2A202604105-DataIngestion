import unittest

from src.evaluation import evaluate_query, summarize


class EvaluationTests(unittest.TestCase):
    def question(self):
        return {"id": "q1", "split": "dev", "question": "What is required?",
                "expected_answer": "A complete evidence quote", "gold_source_id": "doc",
                "gold_page": 7, "evidence_quote": "Complete evidence is required."}

    def hit(self, text="Complete evidence is required.", page=7, document="doc"):
        return {"chunk_id": "c", "document_id": document, "page": page,
                "text": text, "metadata": {"section": "one"}, "score": 0.8}

    def test_source_and_page_are_required_not_just_similarity_or_text(self):
        for hit in [self.hit(page=8), self.hit(document="other"), self.hit("Complete evidence")]:
            trace = evaluate_query(self.question(), [hit])
            self.assertFalse(trace["hit_at_1"])
            self.assertFalse(trace["evidence_hit_at_3"])

    def test_rank_three_counts_but_rank_four_does_not(self):
        miss = self.hit("unrelated")
        self.assertTrue(evaluate_query(self.question(), [miss, miss, self.hit()])["evidence_hit_at_3"])
        trace = evaluate_query(self.question(), [miss, miss, miss, self.hit()])
        self.assertFalse(trace["evidence_hit_at_3"])
        self.assertEqual(len(trace["hits"]), 3)

    def test_evidence_split_across_chunks_is_not_a_main_metric_hit(self):
        trace = evaluate_query(self.question(), [self.hit("Complete evidence"), self.hit("is required.")])
        self.assertFalse(trace["evidence_hit_at_3"])

    def test_alternative_gold_and_accepted_page_list(self):
        question = self.question()
        question["alternative_evidence"] = [{"gold_source_id": "doc", "gold_page": [8, 9],
                                              "evidence_quote": "An equivalent statement."}]
        trace = evaluate_query(question, [self.hit("An equivalent statement.", page=9)])
        self.assertTrue(trace["hit_at_1"])
        self.assertEqual(trace["hits"][0]["matching_gold_records"], [1])

    def test_unicode_and_whitespace_normalization(self):
        question = self.question()
        question["evidence_quote"] = "Café is open."
        self.assertTrue(evaluate_query(question, [self.hit("Cafe\u0301\n is   open.")])["hit_at_1"])

    def test_summary_counts_questions_and_checks_filter_compliance(self):
        question = self.question()
        question["filter"] = {"section": "one"}
        first = {**evaluate_query(question, [self.hit()]), "strategy": "C"}
        question = {**question, "id": "q2"}
        second = {**evaluate_query(question, []), "strategy": "C"}
        metric = summarize([first, second])["metrics"][0]
        self.assertEqual(metric["questions"], 2)
        self.assertEqual(metric["hit_at_1_count"], 1)
        self.assertEqual(metric["hit_at_1"], 0.5)
        self.assertEqual(metric["filter_compliant_count"], 1)
        with self.assertRaises(ValueError):
            summarize([first, first])
