# Roshidere retrieval benchmark v1

`questions.jsonl` contains 20 source-grounded questions: 15 dev from the prologue/chapters 1–8, and 5 test from chapters 9–10, the epilogue and bonus story. Five questions supply section filters (3 dev, 2 test). Both the original extracted page and the prepared page were checked for each evidence quote before any benchmark retrieval.

Evidence quote existence was checked against the selected source pages. This is a convenience sample, with many questions anchored to chapter openings. It is not a representative random sample.

`protocol.json` records sampling, prior activity, scoring, limitations and the selection rule. `gold_verification.json` records the source-existence checks. `freeze.json` was saved before dev retrieval and hashes the questions, protocol, configuration, prepared/raw source pages, model identity and actual database contents. No questions, labels, corpus, chunk settings or model weights were changed between dev and test.

The score is strict: a single retrieved chunk must have the registered document ID and physical PDF page and contain the complete evidence quote after Unicode NFC and whitespace normalization. A correct page alone is insufficient. Quotes split across multiple chunks do not count as main-metric hits. `alternative_evidence` may contain additional records with `gold_source_id`, `gold_page`, and `evidence_quote`; this v1 set has no post-retrieval additions. Automatic scores may undercount valid alternative pages and semantically equivalent wording.

Dev selection prioritizes Evidence Hit@3, then Hit@1, then fewer stored chunks, then alphabetical strategy name. The decision is written before test retrieval. A/B ignore question filters; C uses only the section explicitly supplied in the question. Gold answers and gold pages are never passed to the embedding model or used as filters.

From `starter/`, the original workflow was:

```powershell
.\.venv\Scripts\python.exe -m src.benchmark freeze
.\.venv\Scripts\python.exe -m src.benchmark dev
.\.venv\Scripts\python.exe -m src.benchmark test
```

The original freeze and result directories are retained. Commands refuse to overwrite them. To reproduce against the same frozen database, use a new output directory for both phases:

```powershell
.\.venv\Scripts\python.exe -m src.benchmark dev --output-dir results\roshidere\recheck_01
.\.venv\Scripts\python.exe -m src.benchmark test --output-dir results\roshidere\recheck_01
```

The runner rejects changes to frozen inputs. A changed corpus/configuration/benchmark requires a separately versioned benchmark and corresponding ingestion, not silently replacing the v1 holdout. Future tuning should use dev and a new test set if the current test results influence changes.

Original artifacts are in `starter/results/roshidere/benchmark/`: full top-3 traces, dev/test metrics as JSON/CSV, the dev-only selection, per-phase run metadata, and the retrieval report. These are retrieval metrics, not human coherence/grounding labels or LLM answer accuracy.
