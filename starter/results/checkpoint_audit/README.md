# Checkpoint audit

See `REPORT.md` for coverage, results and strategy comparisons.

The sample protocol and source evidence are frozen in `sample_freeze.json`. Sampling uses the same ten source locations for A/B/C/F, the five original test questions for A/B/C, and the first five fresh holdout questions for C/F. Original and fresh cohorts are summarized separately.

- `protocol.json`: sampling rules and 0–2 rubrics.
- `coherence_labels.csv`, `metadata_labels.csv`, `grounding_labels.csv`: labels, reviewer attribution and reasons.
- `equivalent_evidence_review.csv`: supplementary alternative-source evidence; strict benchmark scores are unchanged.
- `source_verification.json`: PDF page and section-heading checks.
- `summary.json`, `summary.csv`: cohort-separated metrics.

Run `python -m src.audit summarize` from `starter/` to verify frozen inputs and recompute summaries. Preparation refuses to overwrite frozen samples. Full-text evidence is restored locally using `scripts/submission.py restore`.
