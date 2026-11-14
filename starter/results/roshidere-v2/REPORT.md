# Retrieval improvement comparison

Run date: 14 November 2026 (Asia/Saigon).

**The improved method is now the default. On the same ten fresh holdout questions, top-three evidence retrieval increased from 4/10 (40%) to 10/10 (100%), and first-result success increased from 2/10 (20%) to 8/10 (80%).**

This is a small AI-authored convenience sample. The earlier 80% figure used five different questions; the paired ten-question comparison below measures this change.

## Paired fresh-holdout results

| Method | First-result Hit@1 | Evidence Hit@3 | Section filter compliance |
|---|---:|---:|---:|
| Original C | 2/10 (20.0%) | 4/10 (40.0%) | 3/3 |
| Improved F | 8/10 (80.0%) | 10/10 (100.0%) | 3/3 |

Both methods were tested on exactly the same questions, source pages, embedding model, top-three limit, explicit filters, and strict source/page/full-evidence-quote metric. The improved method was selected on dev before the fresh test was run. No gold quotes or scoring thresholds were relaxed.

## What changed

1. **More context:** sentence-aware page-local windows up to 1,000 characters, with a 250-character target overlap. Sentence boundaries can change the actual overlap. This reduces evidence fragmentation while preserving original PDF page numbers and exact prepared-text offsets.
2. **Two retrieval signals:** semantic pgvector search plus PostgreSQL English full-text search, each retrieving up to 30 candidates with the same optional section filter.
3. **Fusion:** reciprocal-rank fusion (k=60) combines the two ranked lists without treating incompatible raw scores as comparable.
4. **Local reranking:** Xenova/ms-marco-MiniLM-L-6-v2 scores the question together with up to 30 candidate passages, then returns the top three.

The embedding model remains BAAI/bge-small-en-v1.5 (384 dimensions). The prepared 227-page working corpus is unchanged. The improved table stores 535 chunks, shared by methods D/E/F. Model files remain on F:, and inference is local. There are no embedding/reranking API charges.

The largest measured embedding input is 281 tokens, below the embedding model limit of 512 tokens. This is a measurement of the configured corpus and model tokenizer.

## Dev-only candidate selection

| Candidate | Change | Dev Hit@1 | Dev Evidence Hit@3 |
|---|---|---:|---:|
| baseline_C | Original 500-character paragraph baseline | 8/15 (53.3%) | 9/15 (60.0%) |
| D | Larger sentence-aware overlapping windows, dense only | 6/15 (40.0%) | 9/15 (60.0%) |
| E | D plus dense/keyword rank fusion | 8/15 (53.3%) | 9/15 (60.0%) |
| F | E plus local cross-encoder reranking | 10/15 (66.7%) | 11/15 (73.3%) |

Only one context size/overlap, one fusion configuration and one reranker were tried, as predeclared. Larger chunks and keyword fusion alone did not beat the original dev selection score. F won with 11/15 Hit@3 and 10/15 Hit@1. The selection rule preferred Hit@3, then Hit@1, then the fixed simplicity order baseline_C/D/E/F.

## Holdout discipline and preserved baseline

- The original 15 dev questions were reused unchanged. Ten new test questions about different facts/pages were written, source-verified and hashed before candidate development.
- The original five-question test was already seen and was not reused for the new improvement claim.
- Questions, protocol, promotion gate, source text, original database, candidate database and actual model files were checked by hash.
- The selected method and selection timestamp were saved before fresh-test retrieval.
- The predeclared deployment gate required no regression on either test metric; F passed and was promoted. No alternate method was selected using holdout results.
- The original day6_chunks table, A/B/C results and original freeze are intact. The candidate data lives in the separate day6_chunks_v2 table.

## Concrete retrieval changes

- **h01, page 217:** the original method returned pages 213, 220 and 213, missing the registered sound/lighting evidence. F put page 217 first.
- **h03, page 228:** the original method retrieved the correct page but its returned chunk lacked the complete evidence. F returned a larger passage containing the complete registered explanation first.
- **h07, page 246:** the original method returned pages 235, 244 and 183. F put the correct source page 246 first.
- **h04 and h10:** F found the full evidence within its top three, but did not rank it first. First-result ranking still has room to improve.

## Speed and resource trade-off

On the paired fresh test, average retrieval/ranking time was **27.0 ms** for original C and **969.6 ms** for F. These warm measurements exclude query embedding, process startup and model initialization. A new command also loads local model sessions.

F uses more CPU time per question in return for improved rankings on this sample. It stores fewer vectors for the new collection (535 versus 1,012 in original C), while passages are longer and overlap. The original database is retained rather than overwritten.

## How to use it

The existing search command automatically follows configs/active.json:

```powershell
cd "F:\Github\K5-L3B-Day06-DataIngestionEngineering\starter"
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION"
```

Add `--section chapter_5` only when the question or user context supplies that section. Add `--strategy C` to compare with the original method; A/B remain available as well. Improved search returns ranking logits with a score_type field; those values are not confidence percentages.

## Verification and limitations

- All 27 code/database checks passed, including table isolation, parameterized keyword queries, metadata filters, rollback and chunk coverage. After promotion, both default F and explicit original C were checked through the real command with a generic infrastructure smoke query.
- All 10 fresh questions have complete top-three traces for both methods. Strict metrics were recomputed from those saved traces and matched the stored summaries.
- Ten questions are a small sample, with one question changing the rate by ten percentage points.
- Strict quote matching can undercount semantically equivalent evidence and evidence split across chunks. No human coherence, metadata correctness or grounding scores are implied.
- Final data permissions, source manifest and individual report remain separate lab requirements. Keep restricted novel text and derivative passages local unless sharing is permitted.
- The fresh holdout has now been viewed. Any further tuning informed by it needs another fresh holdout for an independent subsequent comparison.

## Artifact locations

- Questions, pre-tuning freeze, protocol and deployment gate: `benchmark/roshidere-v2/`.
- Candidate setup/model hashes, D chunks, dev/test traces, metrics, selection and promotion records: `starter/results/roshidere-v2/`.
- Improved parameters: `starter/configs/roshidere-v2.json`; active pointer: `starter/configs/active.json`.
- Separate measured experiment log: `artifacts/improvement_log.csv`. The original A/B/C experiment log is preserved.
- Source reproduction instructions: `benchmark/roshidere-v2/README.md`.

## Technical references

- [PostgreSQL text-search parsing and ranking](https://www.postgresql.org/docs/16/textsearch-controls.html)
- [FastEmbed cross-encoder implementation](https://github.com/qdrant/fastembed/blob/main/fastembed/rerank/cross_encoder/text_cross_encoder.py)
- [Reranker model card](https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2)
