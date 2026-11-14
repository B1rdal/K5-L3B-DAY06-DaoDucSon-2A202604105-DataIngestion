"""Persistent pgvector storage with exact cosine search and metadata filters."""
import math
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import Chunk


class PgVectorStore:
    FILTER_KEYS = {"document_id", "source", "page", "section", "chapter", "language",
                   "document_type", "year", "version", "category", "audience"}

    def __init__(self, database_url: str, dimensions: int,
                 model_name: str = "unspecified", table_name: str = "day6_chunks") -> None:
        if not isinstance(dimensions, int) or not 1 <= dimensions <= 16000:
            raise ValueError("dimensions must be an integer between 1 and 16000")
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", table_name):
            raise ValueError("Invalid table name; use a simple lowercase SQL identifier")
        self.database_url = database_url
        self.dimensions = dimensions
        self.model_name = model_name
        self.table_name = table_name

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                # dimensions is a validated integer; values use bound parameters.
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        strategy text NOT NULL,
                        chunk_id text NOT NULL,
                        document_id text NOT NULL,
                        source text NOT NULL,
                        page integer NOT NULL CHECK (page > 0),
                        text text NOT NULL,
                        metadata jsonb NOT NULL,
                        embedding_model text NOT NULL,
                        embedding vector({self.dimensions}) NOT NULL,
                        PRIMARY KEY (strategy, chunk_id)
                    )
                """)
                cursor.execute("""
                    SELECT format_type(atttypid, atttypmod) FROM pg_attribute
                    WHERE attrelid = to_regclass(%s) AND attname = 'embedding'
                """, (self.table_name,))
                if cursor.fetchone()[0] != f"vector({self.dimensions})":
                    raise ValueError("Existing database uses different embedding dimensions")
                cursor.execute(f"SELECT DISTINCT embedding_model FROM {self.table_name}")
                if any(row[0] != self.model_name for row in cursor.fetchall()):
                    raise ValueError("Existing database uses a different embedding model")
                prefix = "day6" if self.table_name == "day6_chunks" else self.table_name
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {prefix}_document_idx ON {self.table_name} (strategy, document_id)")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {prefix}_metadata_idx ON {self.table_name} USING gin (metadata)")

    def enable_keyword_search(self) -> None:
        """Create an English full-text index in this collection only."""
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            connection.execute(f"CREATE INDEX IF NOT EXISTS {self.table_name}_text_idx ON {self.table_name} USING gin (to_tsvector('english', text))")

    def _vector(self, vector: list[float]) -> str:
        if len(vector) != self.dimensions:
            raise ValueError(f"Expected a {self.dimensions}-dimensional vector")
        values = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in values) or not any(values):
            raise ValueError("Vectors must be finite and nonzero for cosine search")
        return "[" + ",".join(str(value) for value in values) + "]"

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]],
               document_ids: list[str] | None = None) -> None:
        """Atomically replace the specified documents in this strategy.

        This removes obsolete chunks when documents change. Pass document_ids
        explicitly to remove a document whose new version has no chunks.
        """
        if not strategy.strip() or len(chunks) != len(vectors):
            raise ValueError("A strategy and one vector per chunk are required")
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise ValueError("Duplicate chunk IDs in input")
        documents = sorted(set(document_ids if document_ids is not None else
                               [chunk.document_id for chunk in chunks]))
        if not documents or any(chunk.document_id not in documents for chunk in chunks):
            raise ValueError("Explicit document scope must include every input chunk")
        rows = [
            (strategy, chunk.chunk_id, chunk.document_id, chunk.source, chunk.page,
             chunk.text, Jsonb(chunk.metadata), self.model_name, self._vector(vector))
            for chunk, vector in zip(chunks, vectors)
        ]
        with psycopg.connect(self.database_url, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {self.table_name} WHERE strategy = %s AND document_id = ANY(%s)",
                    (strategy, documents),
                )
                cursor.executemany(f"""
                    INSERT INTO {self.table_name}
                    (strategy, chunk_id, document_id, source, page, text, metadata, embedding_model, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                """, rows)

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        clauses, parameters = self._where(strategy, filters)
        parameters = [self._vector(query_vector), *parameters, top_k]
        query = f"""
            SELECT chunk_id, document_id, source, page, text, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM {self.table_name} WHERE """ + " AND ".join(clauses) + " ORDER BY score DESC, chunk_id LIMIT %s"
        with psycopg.connect(self.database_url, connect_timeout=5, row_factory=dict_row) as connection:
            return connection.execute(query, parameters).fetchall()

    def _where(self, strategy: str, filters: dict[str, Any] | None) -> tuple[list[str], list[Any]]:
        filters = filters or {}
        if set(filters) - self.FILTER_KEYS:
            raise ValueError(f"Unsupported filters: {sorted(set(filters) - self.FILTER_KEYS)}")
        clauses = ["strategy = %s", "embedding_model = %s"]
        parameters: list[Any] = [strategy, self.model_name]
        metadata_filters = {}
        for key, value in filters.items():
            if not isinstance(value, (str, int, float, bool)):
                raise ValueError("Filter values must be scalar strings, numbers, or booleans")
            if key in {"document_id", "source", "page"}:
                clauses.append(f"{key} = %s")
                parameters.append(value)
            else:
                metadata_filters[key] = value
        if metadata_filters:
            clauses.append("metadata @> %s")
            parameters.append(Jsonb(metadata_filters))
        return clauses, parameters

    def keyword_search(self, strategy: str, question: str, top_k: int = 30,
                       filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Rank OR-matched English lexemes, retaining the same section filters.

        PostgreSQL quotes each parsed lexeme; question text is always a bound
        value. OR matching avoids requiring every natural-language question word
        to appear in a passage. Full-text scores are used only as ranks in fusion.
        """
        if not isinstance(top_k, int) or top_k <= 0 or not question.strip():
            raise ValueError("A question and positive top_k are required")
        clauses, parameters = self._where(strategy, filters)
        query = f"""
            WITH lexemes AS (
                SELECT unnest(tsvector_to_array(to_tsvector('english', %s))) AS term
            ), query AS (
                SELECT string_agg(quote_literal(term), ' | ')::tsquery AS value FROM lexemes
            )
            SELECT chunk_id, document_id, source, page, text, metadata,
                   ts_rank_cd(to_tsvector('english', text), query.value, 32) AS score
            FROM {self.table_name} CROSS JOIN query WHERE """ + " AND ".join(clauses) + " AND to_tsvector('english', text) @@ query.value ORDER BY score DESC, chunk_id LIMIT %s"
        with psycopg.connect(self.database_url, connect_timeout=5, row_factory=dict_row) as connection:
            return connection.execute(query, [question, *parameters, top_k]).fetchall()
