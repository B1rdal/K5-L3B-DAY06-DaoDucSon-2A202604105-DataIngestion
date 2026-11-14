# Retrieval accuracy check

Run date: 14 November 2026 (Asia/Saigon).

**Strategy C was selected on dev before test and retrieved the registered evidence in the top three for 4/5 test questions (80%). It ranked the evidence first for 3/5 (60%).** These are preliminary strict evidence-retrieval scores, not LLM answer accuracy or an independently human-verified evaluation.

## Measured results

| Strategy | Dev Hit@1 | Dev Evidence Hit@3 | Test Hit@1 | Test Evidence Hit@3 |
|---|---:|---:|---:|---:|
| A | 6/15 (40.0%) | 8/15 (53.3%) | 1/5 (20.0%) | 2/5 (40.0%) |
| B | 7/15 (46.7%) | 9/15 (60.0%) | 3/5 (60.0%) | 3/5 (60.0%) |
| C | 8/15 (53.3%) | 9/15 (60.0%) | 3/5 (60.0%) | 4/5 (80.0%) |

- **A:** 500-character fixed windows with 50-character overlap; 865 stored chunks.
- **B:** paragraph groups up to 500 characters, with oversized paragraphs split; 1,012 chunks.
- **C:** identical chunks and embeddings to B, applying a section filter only when the question explicitly supplies one; 1,012 chunks.

**Hit@1** means the first passage contains the full registered evidence on an accepted source page. **Evidence Hit@3** means at least one of the first three passages does. Source document ID and physical PDF page must match. Unicode composition and whitespace differences are normalized; a correct page or high similarity score alone is insufficient.

## Evaluation method

- 20 source-grounded questions: 15 dev from the prologue/chapters 1–8 and 5 test from later chapters, epilogue, and bonus story.
- Questions and evidence were authored/read by the AI assistant. All gold quotes were found in both original extracted pages and the prepared corpus before retrieval. Independent human gold verification remains pending.
- Five questions explicitly supply section filters: 3 dev and 2 test. A/B ignore these filters; C applies the user-supplied value. Gold answers/pages are never used as query input or filters.
- The full question set, protocol, corpus files, model identity and database were hashed and frozen before dev retrieval. Strategy selection was highest dev Hit@3, then Hit@1, then fewer chunks, then strategy name.
- C and B tied at 9/15 dev Hit@3. C won the next criterion, 8/15 dev Hit@1 versus 7/15 for B. The selection was saved before any test retrieval.
- All three strategies were run on test without tuning. Database/input hashes matched before and after both phases.
- Model: BAAI/bge-small-en-v1.5, FastEmbed 0.9.1, 384 dimensions, local ONNX CPU. Search: PostgreSQL + pgvector, exact cosine similarity. Embedding API cost: zero; excludes hardware/power/network costs.
- Working corpus: 227 prepared text pages. Final content-page and permission review are separate submission requirements.

## Section filtering

On questions requesting a section, the number whose entire returned top-three stayed within that section was:

| Strategy | Dev (3 filter questions) | Test (2 filter questions) |
|---|---:|---:|
| A | 1/3 | 1/2 |
| B | 1/3 | 0/2 |
| C | 3/3 | 2/2 |

A/B do not apply filters, so their values above measure incidental compliance. C complied with all five explicit filter requests.

## Concrete successes and failures

- **q17 (test, PDF page 233):** asks why Masachika can miss the assembly, explicitly within Chapter 10. B retrieves pages 219, 168, and 215 and misses. C restricts to Chapter 10 and retrieves pages 233, 233, and 238; one contains the full gold evidence. This is a direct observed benefit of the section filter.
- **q20 (test, PDF page 267):** asks about the meal gifted in the bonus story. C retrieves pages 262, 267, and 264, but the full registered quote is split at a chunk boundary. No single stored chunk in any strategy contains the full quote, so all three receive a strict miss. Relevant meal/gift context was retrieved; multi-chunk or semantic grounding could be assessed separately.
- **q03 (dev, PDF page 20):** the correct page appears in B/C top-three, but the returned chunk from that page lacks the gold evidence. This shows why page-only accuracy would overstate evidence retrieval.
- **q08 (dev, PDF page 90):** C returns pages 29, 99, and 84 rather than the registered evidence on page 90. This is a ranking/location failure under the frozen labels.

## Per-question top-three evidence hits

| Question | Split | Gold PDF page | A | B | C |
|---|---|---:|---|---|---|
| q01 | dev | 14 | yes | yes | yes |
| q02 | dev | 15 | no | no | no |
| q03 | dev | 20 | no | no | no |
| q04 | dev | 42 | yes | yes | yes |
| q05 | dev | 57 | yes | yes | yes |
| q06 | dev | 65 | yes | yes | yes |
| q07 | dev | 77 | yes | yes | yes |
| q08 | dev | 90 | no | no | no |
| q09 | dev | 111 | yes | yes | yes |
| q10 | dev | 120 | no | yes | yes |
| q11 | dev | 137 | no | no | no |
| q12 | dev | 150 | no | yes | yes |
| q13 | dev | 160 | yes | yes | yes |
| q14 | dev | 175 | no | no | no |
| q15 | dev | 185 | yes | no | no |
| q16 | test | 213 | no | yes | yes |
| q17 | test | 233 | no | no | yes |
| q18 | test | 251 | yes | yes | yes |
| q19 | test | 262 | yes | yes | yes |
| q20 | test | 267 | no | no | no |

## Limits and next steps

- Five test questions are a very small sample: one question changes the rate by 20 percentage points. The 80% figure does not establish general accuracy on the book or other documents.
- The question set is a convenience sample with many chapter-opening facts. The same assistant authored it and implemented scoring; independent human review is still needed.
- Exact full-quote scoring is conservative. It can mark useful paraphrases, alternative source pages, or evidence spread over several chunks as misses. No post-retrieval gold changes were made to improve v1 scores.
- q03 should identify the opening scene more precisely in a future benchmark, because Chapter 1 includes language changes. q14 gives little scene context. These annotation-quality concerns are recorded after the run; the frozen v1 labels and scores are preserved.
- Keep C as the current dev-selected baseline. Any further tuning should use dev; if test results influence changes, use a fresh test set for an independent follow-up.
- Human coherence, metadata correctness, and grounding audits, final manifest/permissions, and the individual submission report remain unfinished. These retrieval metrics do not replace them.

## Saved artifacts

Project: `F:\Github\K5-L3B-Day06-DataIngestionEngineering`.

- Benchmark questions/protocol/freeze: `benchmark/roshidere/`.
- Full top-three text, scores, metadata and labels: `starter/results/roshidere/benchmark/dev/traces.jsonl` and `test/traces.jsonl`.
- Metrics JSON/CSV, run metadata, dev selection, `metrics_all.csv` and `error_analysis.csv`: `starter/results/roshidere/benchmark/`.
- Experiment log updated with measured numerators/denominators: `artifacts/experiment_log.csv`.
- Reproduction instructions: `benchmark/roshidere/README.md`.

Original results are preserved. Reproduce with a new output directory; the runner refuses to overwrite the original result folders or accept changed frozen inputs.
