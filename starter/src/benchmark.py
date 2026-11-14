"""Freeze an evidence benchmark, run dev, select a strategy, then run test."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from dotenv import load_dotenv
import psycopg

from .embeddings import MyEmbedder
from .evaluation import evaluate_query, gold_records, normalized, summarize
from .store import PgVectorStore


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SELECTION_RULE = ["highest dev Evidence Hit@3 count", "highest dev Hit@1 count",
                  "fewest indexed chunks", "alphabetical strategy name"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]


def url() -> str:
    load_dotenv(ROOT / ".env")
    if not os.getenv("DATABASE_URL"):
        raise ValueError("DATABASE_URL missing")
    return os.environ["DATABASE_URL"]


def validate_questions(questions: list[dict], pages: list[dict], raw_pages: list[dict]) -> dict:
    if len({question["id"] for question in questions}) != len(questions):
        raise ValueError("Question IDs must be unique")
    counts = Counter(question["split"] for question in questions)
    if counts["dev"] < 15 or counts["test"] < 5 or set(counts) - {"dev", "test"}:
        raise ValueError("Need at least 15 dev and 5 test questions")
    indexed = {(page["document_id"], page["page"]): page for page in pages}
    raw = {(page["document_id"], page["page"]): page for page in raw_pages}
    filter_counts = Counter()
    for question in questions:
        if not question["question"].strip() or not question["expected_answer"].strip():
            raise ValueError("Question and expected answer must not be empty")
        filters = question.get("filter") or {}
        if filters:
            if set(filters) != {"section"} or not question.get("filter_context"):
                raise ValueError("This benchmark requires an explicit section context for filters")
            label = filters["section"].replace("_", " ")
            if label not in question["question"].lower():
                raise ValueError(f"Filter must be supplied in question text: {question['id']}")
            filter_counts[question["split"]] += 1
        for gold in gold_records(question):
            numbers = gold["gold_page"]
            numbers = numbers if isinstance(numbers, list) else [numbers]
            if not numbers or any(type(number) is not int or number < 1 for number in numbers):
                raise ValueError("Gold pages must be physical PDF page numbers")
            quote = normalized(gold["evidence_quote"])
            if not quote:
                raise ValueError("Evidence quotes must not be empty")
            for number in numbers:
                key = (gold["gold_source_id"], number)
                if key not in indexed or key not in raw:
                    raise ValueError(f"Gold page missing from corpus: {question['id']}")
                if quote not in normalized(indexed[key]["text"]) or quote not in normalized(raw[key]["text"]):
                    raise ValueError(f"Gold quote not found in source page: {question['id']}")
                if filters and indexed[key]["metadata"].get("section") != filters["section"]:
                    raise ValueError(f"Gold evidence is outside the supplied filter: {question['id']}")
    if sum(filter_counts.values()) < 3 or filter_counts["test"] < 1:
        raise ValueError("Need at least 3 filter questions, including at least 1 test")
    return {"split_counts": dict(counts), "filter_counts": dict(filter_counts),
            "all_gold_quotes_verified_in_prepared_and_raw_pages": True,
            "independent_human_verification": False}


def snapshot(config_path: Path, benchmark_dir: Path, config: dict) -> dict:
    output = ROOT / config["output_dir"]
    ingest_stats = json.loads((output / "ingest_stats.json").read_text(encoding="utf-8"))
    semantic_config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    if semantic_config_hash != ingest_stats["config_sha256"]:
        raise ValueError("Configuration changed since ingestion")
    if sha(ROOT / config["pages_path"]) != ingest_stats["input_sha256"]:
        raise ValueError("Input pages changed since ingestion")
    digest = hashlib.sha256()
    counts = Counter()
    models = set()
    with psycopg.connect(url(), connect_timeout=5) as connection:
        rows = connection.execute("""
            SELECT strategy, chunk_id, document_id, source, page, text, metadata,
                   embedding_model, embedding::text FROM day6_chunks ORDER BY strategy, chunk_id
        """)
        for row in rows:
            if row[2] != config["document_id"]:
                raise ValueError("Benchmark expects only the configured corpus in this table")
            counts[row[0]] += 1
            models.add(row[7])
            digest.update(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
    expected = {strategy: stats["database_rows"] for strategy, stats in ingest_stats["strategies"].items()}
    if dict(counts) != expected or models != {ingest_stats["storage_model_id"]}:
        raise ValueError("Database rows/model do not match the ingested configurations")
    return {
        "questions_sha256": sha(benchmark_dir / "questions.jsonl"),
        "protocol_sha256": sha(benchmark_dir / "protocol.json"),
        "config_sha256": sha(config_path),
        "prepared_pages_sha256": sha(output / "prepared_pages.jsonl"),
        "raw_pages_sha256": sha(ROOT / "results" / "roshidere_pages.jsonl"),
        "database_sha256": digest.hexdigest(), "index_counts": dict(counts),
        "storage_model_id": ingest_stats["storage_model_id"],
    }


def run_benchmark(phase: str, config_path: Path, benchmark_dir: Path,
                  results_dir: Path | None = None) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    protocol = json.loads((benchmark_dir / "protocol.json").read_text(encoding="utf-8"))
    if protocol["selection_rule"] != SELECTION_RULE:
        raise ValueError("Protocol selection rule does not match the implementation")
    questions = read_records(benchmark_dir / "questions.jsonl")
    output = results_dir if results_dir is not None else ROOT / config["output_dir"] / "benchmark"
    validation = validate_questions(
        questions, read_records(ROOT / config["output_dir"] / "prepared_pages.jsonl"),
        read_records(ROOT / "results" / "roshidere_pages.jsonl"),
    )
    current = snapshot(config_path, benchmark_dir, config)
    frozen_path = benchmark_dir / "freeze.json"
    if phase == "freeze":
        if frozen_path.exists():
            raise FileExistsError("A freeze already exists; preserve it and version a changed benchmark separately")
        frozen = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                  "snapshot": current, "validation": validation, "selection_rule": SELECTION_RULE}
        write_json(frozen_path, frozen)
        print("Benchmark frozen before retrieval:", json.dumps(validation))
        return frozen
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if current != frozen["snapshot"]:
        raise ValueError("Benchmark, corpus, index, or configuration changed after freezing")
    decision_path = output / "selection.json"
    decision = None
    if phase == "test":
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        dev_status = json.loads((output / "dev" / "run_metadata.json").read_text(encoding="utf-8"))
        if decision["freeze_sha256"] != sha(frozen_path) or dev_status["status"] != "complete":
            raise ValueError("A completed dev selection for this freeze is required before test")
    folder = output / phase
    folder.mkdir(parents=True, exist_ok=False)
    metadata = {"status": "running", "split": phase,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "freeze_sha256": sha(frozen_path), "snapshot": current,
                "selection_before_test": decision, "validation": validation,
                "human_coherence_grounding_audit": "not performed"}
    write_json(folder / "run_metadata.json", metadata)
    traces = []
    try:
        model = MyEmbedder(config["model_name"], config["model_cache"])
        if model.storage_model_id != current["storage_model_id"]:
            raise ValueError("Actual model weights/tokenizer do not match the frozen database")
        store = PgVectorStore(url(), model.dimensions, model.storage_model_id)
        store.create_schema()
        with (folder / "traces.jsonl").open("x", encoding="utf-8") as trace_file:
            for question in [question for question in questions if question["split"] == phase]:
                started = time.perf_counter()
                # Only question text is embedded. Answers/gold pages are never search inputs.
                vector = model.embed_query(question["question"])
                embedding_ms = (time.perf_counter() - started) * 1000
                per_question = {}
                for strategy in "ABC":
                    filters = (question.get("filter") or None) if strategy == "C" else None
                    started = time.perf_counter()
                    hits = store.search(strategy, vector, top_k=3, filters=filters)
                    retrieval_ms = (time.perf_counter() - started) * 1000
                    trace = {**evaluate_query(question, hits), "strategy": strategy,
                             "filter_applied": filters or {}, "query_embedding_ms": embedding_ms,
                             "retrieval_ms": retrieval_ms}
                    per_question[strategy] = trace
                    traces.append(trace)
                    trace_file.write(json.dumps(trace, ensure_ascii=False) + "\n")
                    trace_file.flush()
                if not question.get("filter"):
                    if [hit["chunk_id"] for hit in per_question["B"]["hits"]] != [hit["chunk_id"] for hit in per_question["C"]["hits"]]:
                        raise RuntimeError("B/C retrieval differs despite identical chunks and no filter")
                print(f"Evaluated {phase} {question['id']} for A/B/C", flush=True)
        if snapshot(config_path, benchmark_dir, config) != current:
            raise ValueError("Evaluation inputs changed while retrieval was running")
        summary = summarize(traces)
        write_json(folder / "metrics.json", summary)
        with (folder / "metrics.csv").open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(summary["metrics"][0]))
            writer.writeheader()
            writer.writerows(summary["metrics"])
        if phase == "dev":
            ranked = sorted(summary["metrics"], key=lambda metric: (
                -metric["evidence_hit_at_3_count"], -metric["hit_at_1_count"],
                current["index_counts"][metric["strategy"]], metric["strategy"],
            ))
            decision = {"selected_strategy": ranked[0]["strategy"],
                        "selected_at_utc": datetime.now(timezone.utc).isoformat(),
                        "freeze_sha256": sha(frozen_path), "rule": SELECTION_RULE,
                        "dev_ranking": ranked, "test_results_used": False}
            write_json(decision_path, decision)
        metadata.update(status="complete", finished_at_utc=datetime.now(timezone.utc).isoformat(),
                        trace_count=len(traces), embedding_api_cost_usd=0)
        write_json(folder / "run_metadata.json", metadata)
        print(json.dumps(summary, indent=2))
        return summary
    except Exception as error:
        metadata.update(status="failed", error_type=type(error).__name__,
                        finished_at_utc=datetime.now(timezone.utc).isoformat())
        write_json(folder / "run_metadata.json", metadata)
        raise


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "dev", "test"))
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "roshidere.json")
    parser.add_argument("--benchmark-dir", type=Path, default=REPO / "benchmark" / "roshidere")
    parser.add_argument("--output-dir", type=Path, help="New results directory for a reproduction run")
    args = parser.parse_args()
    run_benchmark(args.phase, args.config, args.benchmark_dir, args.output_dir)


if __name__ == "__main__":
    main()
