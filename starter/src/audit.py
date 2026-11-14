"""Prepare fixed review samples and summarize explicit AI/human audit labels.

This module validates provenance and aggregates labels. It never assigns
coherence or grounding scores from retrieval metrics or exact string matches.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import sys

from pypdf import PdfReader

from .benchmark import read_records, sha, write_json
from .evaluation import normalized
from .ingestion import normalize_text
from .run import ROOT


OUTPUT = ROOT / "results" / "checkpoint_audit"


def write_records(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def prepare() -> None:
    if OUTPUT.exists():
        raise FileExistsError("Audit folder already exists; preserve its frozen samples")
    OUTPUT.mkdir(parents=True)
    prepared_path = ROOT / "results/roshidere/prepared_pages.jsonl"
    pages = {page["page"]: page for page in read_records(prepared_path)}
    collections = {strategy: read_records(ROOT / f"results/roshidere/chunks_{strategy}.jsonl")
                   for strategy in "ABC"}
    collections["F"] = read_records(ROOT / "results/roshidere-v2/chunks_D.jsonl")
    samples = []
    positions = []
    for number, page_id in enumerate(sorted(pages)[:10], 1):
        offset = len(pages[page_id]["text"]) // 2
        while offset < len(pages[page_id]["text"]) - 1 and pages[page_id]["text"][offset].isspace():
            offset += 1
        sample_id = f"c{number:02}"
        positions.append({"sample_id": sample_id, "pdf_page": page_id, "character_offset": offset})
        for strategy, chunks in collections.items():
            candidates = [chunk for chunk in chunks if chunk["page"] == page_id
                          and chunk["metadata"]["char_start"] <= offset < chunk["metadata"]["char_end"]]
            chosen = min(candidates, key=lambda chunk: (chunk["metadata"]["char_start"], chunk["chunk_id"]))
            samples.append({"audit_id": f"{sample_id}_{strategy}", "sample_id": sample_id,
                            "strategy": strategy, "target_offset": offset, **chosen})
    cases = []
    trace_paths = [ROOT / "results/roshidere/benchmark/test/traces.jsonl",
                   ROOT / "results/roshidere-v2/test/traces.jsonl"]
    for group, path in zip(("original_test", "fresh_test_subset"), trace_paths):
        traces = read_records(path)
        chosen_ids = sorted({trace["question_id"] for trace in traces})[:5]
        for trace in traces:
            if trace["question_id"] not in chosen_ids:
                continue
            strategy = "C" if trace["strategy"] == "baseline_C" else trace["strategy"]
            if group == "original_test" and strategy not in "ABC":
                continue
            hits = [{key: hit[key] for key in
                     ("chunk_id", "document_id", "source", "page", "text", "metadata", "rank")}
                    for hit in trace["hits"]]
            cases.append({"audit_id": f"{group}_{strategy}_{trace['question_id']}",
                          "cohort": group, "strategy": strategy,
                          "question_id": trace["question_id"], "question": trace["question"],
                          "expected_answer": trace["expected_answer"],
                          "requested_filter": trace["requested_filter"],
                          "filter_applied": trace["filter_applied"], "hits": hits})
    protocol = {
        "created_before_label_entry_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer": "Codex AI assistant", "review_type": "explicit rubric-based AI-assisted content review",
        "independent_human_review": False,
        "bias": "Assistant implemented the pipeline and previously saw aggregate results and some failures. Scores and automatic evidence-hit flags are omitted from the audit case view; review is not fully blinded.",
        "coherence_sampling": "First ten prepared PDF page IDs sorted ascending; midpoint character adjusted forward over whitespace; earliest-starting chunk that contains that location. Identical B/C chunks receive identical labels.",
        "coherence_locations": positions,
        "coherence_scale": {"0": "Fragmented or missing subject/context so the local idea cannot be understood", "1": "Partly understandable but cut boundaries or missing context prevent a complete standalone idea", "2": "Subject/action and complete local idea are understandable within the chunk"},
        "grounding_sampling": {"original_test": "All five original test questions q16-q20, same questions for A/B/C", "fresh_test_subset": "First five fresh holdout IDs h01-h05, same questions for C/F; supplementary comparison only"},
        "grounding_scale": {"0": "No question-responsive supporting evidence", "1": "Relevant partial evidence but a required fact, condition, identity, or link is missing", "2": "Top-three passages jointly contain sufficient evidence and conditions to answer with source traceability"},
        "grounding_policy": "Review actual top-three text independently of strict full-quote scores. Multiple chunks and valid alternative source pages may jointly support an answer. Do not invent unavailable facts or assume missing conditions.",
        "metadata_checks": ["document_id/source identify the actual local PDF", "physical page number and passage text match original PDF extraction", "section matches verified PDF contents/section opening pages", "character offsets match unchanged prepared page", "explicit filter compliance checked separately from field correctness"],
        "limitations": ["No independent human judgment", "First-ten-page coherence sample emphasizes early scenes", "Only five grounding questions per strategy/cohort", "Local file paths require a manifest/access instructions for another computer", "Source permissions remain unverified"],
    }
    write_json(OUTPUT / "protocol.json", protocol)
    write_records(OUTPUT / "coherence_samples.jsonl", samples)
    write_records(OUTPUT / "grounding_cases.jsonl", cases)
    unique_pages = sorted({sample["page"] for sample in samples} |
                          {hit["page"] for case in cases for hit in case["hits"]})
    source = Path(pages[min(pages)]["source"])
    raw = {}
    with source.open("rb") as file:
        reader = PdfReader(file)
        toc = normalize_text(reader.pages[12].extract_text(extraction_mode="layout", layout_mode_strip_rotated=False) or "")
        for number in unique_pages:
            raw[number] = normalize_text(reader.pages[number - 1].extract_text(
                extraction_mode="layout", layout_mode_strip_rotated=False) or "")
        config = json.loads((ROOT / "configs/roshidere.json").read_text(encoding="utf-8"))
        heading_checks = []
        for section in config["sections"]:
            opening = normalize_text(reader.pages[section["start_page"] - 1].extract_text(
                extraction_mode="layout", layout_mode_strip_rotated=False) or "")
            heading_checks.append({"section": section["name"], "start_page": section["start_page"],
                                   "heading_matches": normalized(opening).startswith(section["heading_prefix"])})
    if not all(check["heading_matches"] for check in heading_checks):
        raise ValueError("A PDF section opening no longer matches the recorded metadata")
    write_records(OUTPUT / "source_pages.jsonl", [{"page": page, "text": raw[page]} for page in unique_pages])
    (OUTPUT / "pdf_contents_page.txt").write_text(toc, encoding="utf-8")
    validations = []
    for case in cases:
        for hit in case["hits"]:
            m = hit["metadata"]
            section = next((s for s in config["sections"]
                            if s["start_page"] <= hit["page"] <= s["end_page"]), None)
            required = all(key in hit and hit[key] is not None for key in ("document_id", "source", "page")) and bool(m.get("section"))
            text_matches = normalized(hit["text"]) in normalized(raw[hit["page"]])
            offsets_match = hit["text"] == pages[hit["page"]]["text"][m["char_start"]:m["char_end"]]
            source_matches = Path(hit["source"]).resolve() == source.resolve() and hit["document_id"] == config["document_id"]
            section_matches = section is not None and m["section"] == section["name"]
            requested = case["requested_filter"]
            filter_match = all(hit.get(key, m.get(key)) == value for key, value in requested.items()) if requested else None
            validations.append({"audit_id": f"{case['audit_id']}_r{hit['rank']}",
                                "cohort": case["cohort"], "strategy": case["strategy"],
                                "question_id": case["question_id"], "rank": hit["rank"],
                                "chunk_id": hit["chunk_id"], "pdf_page": hit["page"], "section": m["section"],
                                "required_fields_present": required, "actual_pdf_text_matches": text_matches,
                                "prepared_offsets_match": offsets_match, "source_identity_matches": source_matches,
                                "section_matches_verified_headings": section_matches,
                                "requested_filter_matches": filter_match})
    write_records(OUTPUT / "metadata_checks.jsonl", validations)
    write_json(OUTPUT / "source_verification.json", {
        "pdf_path": str(source), "pdf_sha256": sha(source), "unique_audited_pdf_pages": unique_pages,
        "section_opening_checks": heading_checks,
        "coherence_samples": len(samples), "grounding_cases": len(cases),
        "metadata_records": len(validations), "all_source_checks_pass": all(
            all(row[key] for key in ("required_fields_present", "actual_pdf_text_matches",
                                     "prepared_offsets_match", "source_identity_matches", "section_matches_verified_headings"))
            for row in validations),
    })
    freeze = {"frozen_before_label_entry_utc": datetime.now(timezone.utc).isoformat(),
              "files": {path.name: sha(path) for path in sorted(OUTPUT.iterdir()) if path.is_file()},
              "input_trace_hashes": {str(path.relative_to(ROOT)): sha(path) for path in trace_paths},
              "prepared_pages_sha256": sha(prepared_path)}
    write_json(OUTPUT / "sample_freeze.json", freeze)
    print(f"Prepared {len(samples)} coherence samples, {len(cases)} grounding cases, {len(validations)} metadata records.")
    print("Actual PDF source checks:", all(row["actual_pdf_text_matches"] for row in validations))


def summarize_labels() -> dict:
    frozen = json.loads((OUTPUT / "sample_freeze.json").read_text(encoding="utf-8"))
    for name, expected in frozen["files"].items():
        if sha(OUTPUT / name) != expected:
            raise ValueError(f"Frozen audit input changed: {name}")
    for path, expected in frozen["input_trace_hashes"].items():
        if sha(ROOT / path) != expected:
            raise ValueError("Original retrieval traces changed")
    groups = defaultdict(list)
    for kind, input_name in (("coherence", "coherence_samples.jsonl"),
                             ("grounding", "grounding_cases.jsonl"),
                             ("metadata", "metadata_checks.jsonl")):
        with (OUTPUT / f"{kind}_labels.csv").open(encoding="utf-8", newline="") as file:
            labels = list(csv.DictReader(file))
        items = {row["audit_id"]: row for row in read_records(OUTPUT / input_name)}
        if len({label["audit_id"] for label in labels}) != len(labels) or {label["audit_id"] for label in labels} != set(items):
            raise ValueError(f"Missing, duplicate or extra {kind} labels")
        for label in labels:
            if not label["reason"].strip() or label["reviewer"] != "Codex AI assistant":
                raise ValueError("Every AI-assisted label needs a reason and honest reviewer attribution")
            row = items[label["audit_id"]]
            cohort = row.get("cohort", "shared_source_locations")
            score = int(label["score"])
            if score not in ({0, 1} if kind == "metadata" else {0, 1, 2}):
                raise ValueError("Invalid audit score")
            groups[(kind, cohort, row["strategy"])].append(score)
    result = {"reviewer_type": "AI_assistant", "independent_human_review": False,
              "status": "AI-assisted checkpoint audit complete; human validation pending", "groups": []}
    for (kind, cohort, strategy), scores in sorted(groups.items()):
        row = {"kind": kind, "cohort": cohort, "strategy": strategy, "n": len(scores),
               "sum": sum(scores), "mean": sum(scores) / len(scores),
               "score_counts": dict(Counter(scores))}
        result["groups"].append(row)
    by_case = defaultdict(list)
    for record in read_records(OUTPUT / "metadata_checks.jsonl"):
        if record["requested_filter_matches"] is not None:
            by_case[(record["cohort"], record["strategy"], record["question_id"])].append(record["requested_filter_matches"])
    filters = defaultdict(lambda: [0, 0])
    for (cohort, strategy, _), values in by_case.items():
        filters[(cohort, strategy)][1] += 1
        filters[(cohort, strategy)][0] += bool(values) and all(values)
    result["filter_compliance"] = [
        {"cohort": cohort, "strategy": strategy, "compliant_questions": counts[0], "filter_questions": counts[1]}
        for (cohort, strategy), counts in sorted(filters.items())
    ]
    source = json.loads((OUTPUT / "source_verification.json").read_text(encoding="utf-8"))
    result["review_counts"] = {
        "coherence_labels": sum(group["n"] for group in result["groups"] if group["kind"] == "coherence"),
        "grounding_labels": sum(group["n"] for group in result["groups"] if group["kind"] == "grounding"),
        "metadata_labels": sum(group["n"] for group in result["groups"] if group["kind"] == "metadata"),
        "distinct_coherence_chunks": len({row["chunk_id"] for row in read_records(OUTPUT / "coherence_samples.jsonl")}),
        "actual_pdf_pages_reextracted": len(source["unique_audited_pdf_pages"]),
    }
    equivalence = OUTPUT / "equivalent_evidence_review.csv"
    if equivalence.exists():
        with equivalence.open(encoding="utf-8", newline="") as file:
            result["ai_equivalent_evidence_reviews"] = list(csv.DictReader(file))
        result["equivalence_status"] = "Supplementary AI-supported findings; frozen metrics unchanged; independent human validation pending"
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "summarize"))
    if parser.parse_args().phase == "prepare":
        prepare()
    else:
        summarize_labels()


if __name__ == "__main__":
    main()
