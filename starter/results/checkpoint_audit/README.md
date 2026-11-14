# Checkpoint audit review

Start with `REPORT.md`. All current subjective ratings were assigned by the Codex AI assistant, which also implemented the pipeline and saw earlier retrieval results. They are explicitly AI-assisted and are not an independent human review.

The sample protocol and source evidence are frozen in `sample_freeze.json`. Sampling was deterministic: the same ten source locations for A/B/C/F, the five original test questions for A/B/C, and the first five fresh holdout questions for C/F. Original and fresh cohorts are summarized separately.

To perform an actual human review:

1. Read each chunk in `coherence_samples.jsonl` and apply the 0–2 coherence rubric in `protocol.json`. Compare against the source only to verify its location; evaluate whether the chunk itself carries a complete local idea.
2. Read each three-passage case in `grounding_cases.jsonl` and judge whether the requested facts and conditions are supported. Do not copy the strict Hit@3 label as a grounding score.
3. Compare the 75 metadata records with the actual PDF and verified section headings. Field correctness and requested-filter compliance are separate questions.
4. Enter a real reviewer's score, reason, name and actual review date in the `human_*` columns of the corresponding CSV files. Those columns are blank until a person performs the review. The current aggregation command summarizes AI scores only.
5. Review `equivalent_evidence_review.csv`: A/q16 contains valid alternative source evidence that the original strict registered-quote metric did not recognize. The finding is supplemental and does not rewrite the frozen benchmark.

Run `python -m src.audit summarize` from `starter/` to recheck frozen inputs and aggregate the existing AI label means/counts and filter compliance. Preparation refuses to overwrite this frozen sample set.

The source excerpts are derived from the novel. Keep them local unless you have permission to share them. Final dataset permissions and the individual submission report are outside this checkpoint audit.
