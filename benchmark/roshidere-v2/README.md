# Retrieval improvement experiment v2

This experiment preserves the original corpus, model, benchmark and A/B/C database table. It reuses the original 15 dev questions unchanged and adds ten new holdout questions about different facts on different pages. The original five test questions were already viewed and were not used for tuning or for the new improvement claim.

`question_freeze.json` hashes the question set and protocol before candidate development. `promotion_gate.json` records the predeclared deployment gate. The question set is AI-authored and source-checked, with independent human verification pending. It is a small convenience sample rather than a representative random evaluation.

## Predeclared candidates

| Candidate | Chunking | Retrieval |
|---|---|---|
| baseline_C | Original paragraph chunks, max 500 characters | Dense cosine, optional user-provided section filter |
| D | Sentence-aware windows, max 1,000 characters and target overlap 250 | Same dense embedding model and optional section filter |
| E | Same chunks/vectors as D | Dense top-30 plus PostgreSQL English full-text top-30; reciprocal-rank fusion, k=60 |
| F | Same candidates as E | Local MiniLM cross-encoder reranks the top 30 fused candidates |

Window boundaries prefer sentence punctuation; overlap can vary because it follows sentence boundaries. Oversized sentences fall back to word/character boundaries. Windows stay on their original PDF page and preserve exact offsets. The largest measured embedding input was 281 tokens, below the 512-token limit.

PostgreSQL full-text query terms are parsed as English lexemes and OR-combined with database quoting. This allows keyword matches without requiring every word of a natural-language question. Dense and keyword paths receive exactly the same explicit section filter. No expected answer, evidence quote, or gold page is a retrieval input.

The embedding model remains `BAAI/bge-small-en-v1.5`. The local reranker is `Xenova/ms-marco-MiniLM-L-6-v2`. Both run on CPU with model files on F:. Their actual file hashes are recorded in `starter/results/roshidere-v2/setup.json`. Document text is processed locally.

## Selection and holdout

The dev-only selection rule is highest strict Evidence Hit@3, then Hit@1, then the fixed simplicity order baseline_C/D/E/F. F won dev selection. Its selection file predates fresh-test retrieval.

Only baseline_C and the locked winner were evaluated on the same ten new holdout questions. The predeclared gate allows deployment only when the chosen method does not regress on either test metric. The strict original document/page/full-quote scoring code and frozen gold labels were retained. No evidence alternatives were added after retrieval.

## Files and commands

From `starter/`, the original workflow was:

```powershell
.\.venv\Scripts\python.exe -m src.improvement prepare
.\.venv\Scripts\python.exe -m src.improvement dev
.\.venv\Scripts\python.exe -m src.improvement test
```

The existing setup and phase directories are retained, and the commands refuse to overwrite a completed setup or existing phase directory. To reproduce, use a clean checkout/configured copy of the same frozen sources and indexes, preserving the original run as evidence. The scripts verify the original baseline, question/protocol hashes, corpus, candidate index and model hashes before evaluation.

Improved chunks are stored once as strategy D in the separate `day6_chunks_v2` table. E/F share those chunks and vectors and change retrieval only. The original `day6_chunks` table remains unchanged; its original freeze still validates.

Measured summaries, complete traces, selection and promotion records are under `starter/results/roshidere-v2/`. `configs/active.json` points normal searches at the promoted method. Original A/B/C remain available through `--strategy A`, `--strategy B` and `--strategy C`.

Further tuning informed by this fresh holdout makes it a development diagnostic; use another unseen holdout for a subsequent independent comparison.

## References

- [PostgreSQL full-text query parsing and ranking](https://www.postgresql.org/docs/16/textsearch-controls.html)
- [FastEmbed cross-encoder implementation](https://github.com/qdrant/fastembed/blob/main/fastembed/rerank/cross_encoder/text_cross_encoder.py)
- [Local reranker model card](https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2)
