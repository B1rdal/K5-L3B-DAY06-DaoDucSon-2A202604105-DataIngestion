"""Optional live PostgreSQL tests isolated in a temporary, uniquely named schema."""
import os
import unittest
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from src.models import Chunk
from src.store import PgVectorStore


@unittest.skipUnless(os.getenv("DAY6_TEST_DATABASE_URL"), "Set DAY6_TEST_DATABASE_URL for live DB tests")
class StoreTests(unittest.TestCase):
    def setUp(self):
        self.url = os.environ["DAY6_TEST_DATABASE_URL"]
        self.schema = "day6_test_" + uuid.uuid4().hex
        with psycopg.connect(self.url) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.scoped_url = make_conninfo(self.url, options=f"-c search_path={self.schema},public")
        self.store = PgVectorStore(self.scoped_url, 3, "synthetic-test-fixture")
        self.store.create_schema()

    def tearDown(self):
        with psycopg.connect(self.url) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))

    def chunk(self, key, document="doc", section="one", page=1):
        return Chunk(key, document, "fixture.pdf", page, "Fixture text " + key, {"section": section})

    def rows(self):
        with psycopg.connect(self.scoped_url) as connection:
            return connection.execute("SELECT strategy, chunk_id FROM day6_chunks ORDER BY strategy, chunk_id").fetchall()

    def test_reload_removes_stale_chunks_without_touching_other_documents(self):
        self.store.upsert("A", [self.chunk("old"), self.chunk("keep", "other")], [[1, 0, 0], [0, 1, 0]])
        self.store.upsert("A", [self.chunk("new")], [[1, 0, 0]])
        self.store.upsert("A", [self.chunk("new")], [[1, 0, 0]])
        self.assertEqual(self.rows(), [("A", "keep"), ("A", "new")])
        self.store.upsert("A", [], [], document_ids=["doc"])
        self.assertEqual(self.rows(), [("A", "keep")])

    def test_cosine_ranking_metadata_filter_and_parameterized_values(self):
        self.store.upsert("C", [self.chunk("first"), self.chunk("second", section="two")],
                          [[1, 0, 0], [0.8, 0.2, 0]])
        hits = self.store.search("C", [1, 0, 0])
        self.assertEqual(hits[0]["chunk_id"], "first")
        self.assertAlmostEqual(hits[0]["score"], 1.0)
        filtered = self.store.search("C", [1, 0, 0], filters={"section": "two", "page": 1})
        self.assertEqual([hit["chunk_id"] for hit in filtered], ["second"])
        self.assertEqual(self.store.search("C", [1, 0, 0], filters={"section": "two' OR true --"}), [])
        with self.assertRaises(ValueError):
            self.store.search("C", [1, 0, 0], filters={"arbitrary_sql": "value"})

    def test_invalid_vectors_fail_before_replacing_existing_data(self):
        self.store.upsert("A", [self.chunk("original")], [[1, 0, 0]])
        for vector in ([1, 0], [0, 0, 0], [float("nan"), 0, 1], [float("inf"), 0, 1]):
            with self.assertRaises(ValueError):
                self.store.upsert("A", [self.chunk("replacement")], [vector])
        self.assertEqual(self.rows(), [("A", "original")])

    def test_failed_insert_rolls_back_the_document_replacement(self):
        self.store.upsert("A", [self.chunk("original")], [[1, 0, 0]])
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.store.upsert("A", [self.chunk("invalid", page=0)], [[1, 0, 0]])
        self.assertEqual(self.rows(), [("A", "original")])
        with self.assertRaisesRegex(ValueError, "different embedding model"):
            PgVectorStore(self.scoped_url, 3, "another-model").create_schema()
        with self.assertRaisesRegex(ValueError, "different embedding dimensions"):
            PgVectorStore(self.scoped_url, 4, "synthetic-test-fixture").create_schema()

    def test_separate_collection_and_keyword_filters(self):
        other = PgVectorStore(self.scoped_url, 3, "synthetic-test-fixture", "day6_new_collection")
        other.create_schema()
        other.enable_keyword_search()
        first = self.chunk("first", section="one")
        second = self.chunk("second", section="two")
        first.text = "The curious gardener grows roses and tomatoes."
        second.text = "A gardener repairs a piano."
        other.upsert("D", [first, second], [[1,0,0], [0,1,0]])
        hits = other.keyword_search("D", "gardener tomatoes", filters={"section":"one"})
        self.assertEqual([hit["chunk_id"] for hit in hits], ["first"])
        self.assertEqual(other.keyword_search("D", "the and a"), [])
        self.assertEqual(other.keyword_search("D", "' OR true --", filters={"section":"absent"}), [])
        self.assertEqual(self.rows(), [])
        with self.assertRaises(ValueError):
            PgVectorStore(self.scoped_url, 3, "fixture", "chunks; DROP TABLE x")
