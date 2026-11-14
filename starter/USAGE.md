# Using the local document search pipeline

Start Docker/PostgreSQL first. On this computer, double-click `F:\CodexTools\Start Day6.cmd`.
Open PowerShell in `starter/` and use the project's Python:

```powershell
cd "F:\Github\K5-L3B-Day06-DataIngestionEngineering\starter"
```

## Prepare the chunks

```powershell
.\.venv\Scripts\python.exe -m src.run chunk
```

The default configuration is `configs/roshidere.json`. It reads the existing page JSONL, verifies section opening headings, selects the story sections, removes exact page footers, and excludes footer-only/non-prose pages and standalone translator-note pages. Original extracted files are retained. `results/roshidere/page_selection.json` records each inclusion/exclusion.

Prepared text is saved to `results/roshidere/prepared_pages.jsonl`. Chunk offsets refer to that text, with original physical PDF page numbers preserved.

| Strategy | Chunking | Filtering |
|---|---|---|
| A | 500 characters, 50-character overlap | None |
| B | Paragraph groups up to 500 characters; long paragraphs split at whitespace where possible | None |
| C | Exactly the same chunks and vectors as B | Optional user-provided section filter |

Chunks never cross page boundaries. Paragraph boundaries are inferred from blank lines in the extracted layout, so PDF layout artifacts can still affect coherence. Extremely long words may require a character split. The pipeline does not remove all inline translator notes or guarantee complete sentences. Inspect the chunks during the manual audit.

## Embed and store

```powershell
.\.venv\Scripts\python.exe -m src.run ingest
```

This prepares chunks, loads the real `BAAI/bge-small-en-v1.5` embedding model using FastEmbed, and writes text, source pages, metadata, and 384-dimensional vectors into the PostgreSQL `day6_chunks` table. Model downloads and caches are on F:. Inference runs locally on CPU, and document text is not sent to an embedding API. The model is intended for English and has a 512-token input limit; the configured chunks are limited to 500 characters. Query and document processing use FastEmbed's paired methods without additional prefixes.

Rerunning replaces the configured document's rows in each strategy inside a transaction, removing stale chunks and avoiding duplicates. Other documents are retained. B and C reuse the same embeddings. Model/hash or dimension mismatches are rejected to avoid mixing incompatible vectors.

The database uses exact cosine search. Timing, character-length distributions, row counts, software versions, weight/tokenizer hashes, and API cost (zero for local inference) are saved to `results/roshidere/ingest_stats.json`. Hardware, power and internet costs are excluded. The separate retrieval benchmark has now been run; see below.

## Search

The normal search command now uses the dev-selected improved method F, through `configs/active.json`. It uses overlapping sentence-aware passages, dense/keyword fusion, and a local cross-encoder reranker. Original A/B/C and their measured results are preserved. See `results/roshidere-v2/REPORT.md` and `../benchmark/roshidere-v2/README.md` for the paired fresh-holdout comparison.

```powershell
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION"
```

This displays the top three passages in readable terminal cards, with chapter, physical PDF page, source filename and total time including model loading. Text wraps to the terminal width and colors are enabled when supported. It retrieves evidence; it does not generate an LLM answer.

Add `--details` for ranking scores and chunk IDs, `--json` for the original complete JSON result list, or `--no-color` for plain output. Color is also disabled when output is redirected or `NO_COLOR` is set. Raw JSON includes the full metadata; progress and library messages use stderr so stdout can be parsed or saved directly.

To restrict the active method to a section explicitly supplied in the question/context:

```powershell
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION" --section chapter_5
```

Valid sections include `prologue`, `chapter_1` through `chapter_10`, `epilogue`, and `bonus_story`. Improved D/E/F and original C apply a section filter only when explicitly provided. With no filter, original C behaves like original B. `--strategy A`, `--strategy B` and `--strategy C` search the original table, even when improved F is the active default. A/B reject section filters. Never derive a benchmark filter from a gold source or answer.

Improved search scores identify their `score_type`: F returns cross-encoder ranking logits, which may be negative or greater than one. They are ranking values rather than probability/confidence percentages. Source, physical PDF page and character offsets are retained in every result. Reranking adds local CPU work, and each new command also loads the model sessions.

The existing `chunk` and `ingest` commands still target the original A/B/C setup unless a configuration is explicitly supplied. Improved collection preparation uses `python -m src.improvement prepare`; completed experiments are retained rather than overwritten. No embedding API key is needed.

## Evaluation artifacts

A 20-question, 15-dev/5-test retrieval benchmark has been authored, source-checked, frozen and run. See `../benchmark/roshidere/README.md` for the original method and results. The subsequent improvement experiment reused dev and prepared ten fresh holdout questions before candidate development; see `../benchmark/roshidere-v2/README.md` and `results/roshidere-v2/REPORT.md`. Strict source/page/quote matching was retained. Both tests are small convenience samples.

The checkpoint audit package is now in `results/checkpoint_audit/REPORT.md`: 40 coherence labels, 75 source-checked metadata records and 25 grounding cases. Labels include rubric-based reasons. Original A/B/C are compared on the same original five test questions; C/F are compared separately on the same first five fresh holdout questions.



## References

- [FastEmbed documentation](https://qdrant.github.io/fastembed/Getting%20Started/)
- [pgvector documentation](https://github.com/pgvector/pgvector)
