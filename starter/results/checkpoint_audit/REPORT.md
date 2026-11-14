# Checkpoint 3:30 — benchmark and audit

**The AI-assisted audit artifacts are complete. Independent human validation remains pending.** The labels below were assigned by the Codex AI assistant after reading the sampled chunks and retrieved evidence. They are not presented as judgments made by the student or an independent human reviewer.

## Coverage and method

- **40 coherence labels:** the same ten source locations for A/B/C/F. The source pages are 14, 15, 16, 17, 20, 21, 22, 23, 24 and 25. The midpoint character is the target, and the earliest-starting containing chunk is selected. B/C use identical chunks and share identical ratings, so the 40 labels cover 30 distinct chunk IDs.
- **25 grounding labels:** A/B/C each on original test questions q16–q20 (15 cases); C/F each on the first five fresh holdout questions h01–h05 (10 cases). Cohorts are kept separate.
- **75 metadata record checks:** top three passages for each of those 25 cases. Repeated chunks are counted as record instances. Thirty-nine distinct physical PDF pages were re-extracted from the original PDF, and all 13 section opening headings were checked.
- Coherence and grounding were explicitly judged from the text using the published 0–2 rubric. They were not calculated from Hit@3 or quote matching.
- Original numerical retrieval scores and automatic evidence-hit flags were omitted from the audit case view. The assistant had already seen aggregate results and some failure cases, so this is not a fully blinded evaluation.
- Each subjective label has its own reason and reviewer attribution. Blank human-review columns are reserved for a real subsequent review.

## 1. Retrieval accuracy already measured

The existing benchmark traces, dev/test metrics and dev-only strategy selections are preserved. Original A/B/C were evaluated on the original 15-dev/5-test set. Improved F was selected on the unchanged dev set and compared with original C on ten newly frozen holdout questions.

On the paired fresh holdout, C achieved 2/10 first-result and 4/10 top-three strict evidence hits. F achieved 8/10 and 10/10 respectively. The small, AI-authored convenience sample limits generalization.

**New audit finding:** original A/q16 retrieves valid answer evidence on PDF pages 165 and 180 about the membership rule and the piano club falling below the threshold. The frozen strict metric only registered page 213 and marked this a miss. The reviewed alternative would raise A's original-test evidence Hit@3 from 2/5 to 3/5 if accepted by a human reviewer. This is a disclosed AI-supported equivalence note, not a silent gold-label change; original frozen metrics remain intact. It is not an exhaustive equivalence adjudication of every benchmark result.

## 2. Chunk coherence

0 = the local idea is not understandable because of fragmentation/missing subject; 1 = partly understandable but missing context or cut boundaries; 2 = complete local idea and actors/actions understandable within the chunk.

| Strategy | Mean /2 | Samples | Score 0 / 1 / 2 counts |
|---|---:|---:|---|
| A | 1.0 | 10 | 0 / 10 / 0 |
| B | 1.1 | 10 | 1 / 7 / 2 |
| C | 1.1 | 10 | 1 / 7 / 2 |
| F | 1.7 | 10 | 0 / 3 / 7 |

Original fixed windows often start/end inside words or clauses. Paragraph-based B is only slightly better on this sample because oversized PDF paragraphs are still split at the 500-character limit. C has the same coherence as B because filtering does not change the chunks.

Improved F gives more standalone context, but still has defects. On page 21, its sampled chunk announces a forthcoming declaration and stops before the declaration. On page 22, punctuation-based sentence detection ends at an unclosed Yes reply inside a longer spoken turn. These are concrete remaining limits of the sentence-boundary heuristic. No chunking settings were changed during the audit.

The sample intentionally follows a deterministic first-ten-page rule, which emphasizes early scenes and cannot establish corpus-wide coherence.

## 3. Metadata correctness and usefulness

Checks covered document/source identity, physical PDF page, text on the actual PDF page, prepared-text character offsets, and the recorded section. All required source/page/section fields were present and consistent in the sampled records.

| Cohort | Strategy | Complete and correct records | Requested-filter compliance |
|---|---|---:|---:|
| original_test | A | 15/15 | 1/2 |
| original_test | B | 15/15 | 0/2 |
| original_test | C | 15/15 | 2/2 |
| fresh_test_subset | C | 15/15 | 1/1 |
| fresh_test_subset | F | 15/15 | 1/1 |

**Usefulness:** the section field distinguishes chapter ranges that share characters and repeated topics. In q17, applying Chapter 10 retrieves Masachika's direct reassurance on page 233; the unfiltered A/B results mostly come from other chapters. Source/page fields make the passage verifiable in the PDF, while offsets locate it in prepared text.

**Limits:** accurate metadata does not guarantee a relevant passage. A/B correctly describe their returned pages even when those pages violate a requested section. Their filter-compliance values reflect that filtering is disabled by design. C/F can enforce scope but cannot supply missing evidence from a truncated chunk. Source paths are local F: paths and need a manifest/access instructions for another computer. No document rights were inferred from those paths.

## 4. Grounding: evidence sufficiency

0 = no question-responsive evidence; 1 = relevant but missing a required fact, condition, identity or connection; 2 = the top three jointly contain sufficient evidence and traceable context. Valid alternative pages and evidence spanning several chunks can support a grounding label even when the stricter single-quote metric misses.

### Original five test questions — matched A/B/C comparison

| Strategy | Mean /2 | Cases | Score 0 / 1 / 2 counts |
|---|---:|---:|---|
| A | 1.6 | 5 | 0 / 2 / 3 |
| B | 1.6 | 5 | 0 / 2 / 3 |
| C | 1.8 | 5 | 0 / 1 / 4 |

- **q16:** A is sufficient because its alternative source pages state the relevant membership/grace-period rule; B/C directly retrieve the registered explanation.
- **q17:** A/B supply some absence/assembly context but miss the requested Chapter-10 reliable-partner reassurance. C contains the complete reassurance in its second passage.
- **q18 and q19:** all three configurations have enough named-person or explicit-negation/technique evidence in their top three.
- **q20:** A/B omit the meal identity. C adds a separate bento-preparation fragment, but the returned passages still do not explicitly identify the item handed over in the bag. A conservative partial score is assigned to all three; the missing link should not be assumed.

### First five fresh holdout questions — matched C/F comparison

| Strategy | Mean /2 | Cases | Score 0 / 1 / 2 counts |
|---|---:|---:|---|
| C | 0.8 | 5 | 2 / 2 / 1 |
| F | 2.0 | 5 | 0 / 0 / 5 |

C has no responsive evidence for h01/h02, partial context for h03/h04, and a full answer for h05. F supplies the required facts and conditions for all five, sometimes using a lower-ranked passage. These are AI-assisted evidence-sufficiency labels on five cases, not a general answer-accuracy percentage. The two cohorts must not be pooled for a C/F versus A/B ranking.

## 5. Strategy impact and trade-offs

- **A → B:** paragraph grouping improves the sampled coherence mean from 1.0 to 1.1, but long paragraphs still get split. Original dev top-three strict evidence hits improve from 8/15 to 9/15, and original test hits from 2/5 to 3/5.
- **B → C:** chunks, vectors and coherence stay identical. Section filtering improves original-test requested-scope compliance from 0/2 to 2/2 and grounding from 1.6/2 to 1.8/2. It does not repair missing intra-chunk context.
- **C → F:** the shared-location coherence mean rises from 1.1 to 1.7. On the matched fresh five-case grounding subset, the mean rises from 0.8/2 to 2.0/2. The separate ten-question strict retrieval comparison rises from 4/10 to 10/10 top-three hits.
- The improvement combines larger overlapping context, rank fusion and a local reranker. Dev ablations showed that larger windows or fusion alone did not beat C's selection score; the reranked method won before the fresh holdout was evaluated.
- Warm retrieval/ranking time on that fresh ten-question comparison averaged about 27 ms for C and 970 ms for F, excluding query embedding and model startup. F uses 535 longer overlapping chunks in a separate table, compared with 1,012 chunks for C; inference and model files stay local on F:.
- C remains the simpler original baseline, while F is the active dev-selected method. The original corpus, results and frozen indexes are unchanged.

## Status and next checkpoint

Completed for this checkpoint: retrieval traces/metrics; explicit coherence labels; source-checked metadata labels and filter counts; explicit grounding labels; reasons, failure examples and strategy-impact analysis. All are documented as AI-assisted.

Independent human validation of the subjective ratings remains pending. The student should review the CSV labels and their reasons before describing them as personally verified. Human-score/reason/reviewer/date columns are deliberately blank, and the current summary aggregates AI labels only.

The next milestone is the final report/submission package: complete STUDENT.md, finalize source permissions/content-page review and the manifest, prepare the individual report and submission checklist, and provide an accessible repository link. This audit does not resolve source rights or fill in unknown student details.

## Audit files

Project audit folder: `F:\Github\K5-L3B-Day06-DataIngestionEngineering\starter\results\checkpoint_audit`.

- `protocol.json`, `sample_freeze.json`: fixed sample rules, scales, attribution/bias and hashes.
- `coherence_samples.jsonl`, `coherence_labels.csv`: 40 labeled chunk instances with reasons.
- `grounding_cases.jsonl`, `grounding_labels.csv`: 25 three-passage review cases and explicit reasons.
- `metadata_checks.jsonl`, `metadata_labels.csv`: 75 provenance checks and AI-reviewed labels.
- `source_verification.json`, `source_pages.jsonl`, `pdf_contents_page.txt`: actual PDF verification evidence.
- `equivalent_evidence_review.csv`: disclosed A/q16 alternative-source finding.
- `summary.json`, `summary.csv`: cohort-separated aggregates.

Reproduction: from starter/, `python -m src.audit summarize` rechecks frozen audit inputs and recomputes the AI-label means/counts. `prepare` refuses to overwrite this audit sample set. Source excerpts are derived from the novel; keep restricted material local unless sharing is permitted.
