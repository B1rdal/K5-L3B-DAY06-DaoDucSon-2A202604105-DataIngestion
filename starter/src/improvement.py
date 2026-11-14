"""Bounded dev-only retrieval improvement with a separately frozen fresh holdout."""
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import psycopg
from psycopg import sql

from .benchmark import read_records, sha, snapshot, validate_questions, write_json
from .chunking import sentence_windows
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .models import DocumentPage
from .retrieval import LocalReranker, retrieve
from .run import ROOT, database_url
from .store import PgVectorStore


BENCHMARK = ROOT.parent / "benchmark" / "roshidere-v2"
ORDER = ["baseline_C", "D", "E", "F"]


def baseline_state() -> dict:
    config_path = ROOT / "configs" / "roshidere.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    folder = ROOT.parent / "benchmark" / "roshidere"
    state = snapshot(config_path, folder, config)
    original = json.loads((folder / "freeze.json").read_text(encoding="utf-8"))
    if state != original["snapshot"]:
        raise ValueError("Original baseline changed; refuse an unfair comparison")
    return state


def question_state() -> dict:
    frozen = json.loads((BENCHMARK / "question_freeze.json").read_text(encoding="utf-8"))
    for key, name in [("questions_sha256", "questions.jsonl"), ("protocol_sha256", "protocol.json")]:
        if sha(BENCHMARK / name) != frozen[key]:
            raise ValueError("Questions/protocol changed after the pre-tuning freeze")
    old_dev = [q for q in read_records(ROOT.parent / "benchmark/roshidere/questions.jsonl") if q["split"] == "dev"]
    new_dev = [q for q in read_records(BENCHMARK / "questions.jsonl") if q["split"] == "dev"]
    if old_dev != new_dev:
        raise ValueError("Dev questions must remain unchanged for comparison")
    return {"questions_sha256": frozen["questions_sha256"],
            "protocol_sha256": frozen["protocol_sha256"],
            "promotion_gate_sha256": sha(BENCHMARK / "promotion_gate.json")}


def index_state(config: dict) -> dict:
    # PgVectorStore validates the table identifier, and SQL identifiers are quoted here.
    store = PgVectorStore(database_url(), 384, table_name=config["table_name"])
    digest = hashlib.sha256()
    count = 0
    with psycopg.connect(database_url()) as connection:
        rows = connection.execute(sql.SQL("SELECT strategy, chunk_id, document_id, source, page, text, metadata, embedding_model, embedding::text FROM {} ORDER BY strategy, chunk_id").format(sql.Identifier(store.table_name)))
        for row in rows:
            digest.update(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
            count += 1
    return {"sha256": digest.hexdigest(), "rows": count}


def prepare(config_path: Path, config: dict) -> None:
    output = ROOT / config["output_dir"]
    if (output / "setup.json").exists():
        raise FileExistsError("Candidate setup already exists; preserve this experiment")
    questions = question_state()
    baseline = baseline_state()
    pages = read_records(ROOT / config["prepared_pages_path"])
    validate_questions(read_records(BENCHMARK / "questions.jsonl"), pages,
                       read_records(ROOT / "results/roshidere_pages.jsonl"))
    chunks = [chunk for page in pages for chunk in sentence_windows(
        DocumentPage(**page), config["sentence_window_size"], config["sentence_window_overlap"])]
    output.mkdir(parents=True, exist_ok=True)
    with (output / "chunks_D.jsonl").open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
    model = MyEmbedder(config["model_name"], config["model_cache"])
    if model.storage_model_id != baseline["storage_model_id"]:
        raise ValueError("Embedding model differs from baseline")
    texts = list(dict.fromkeys(chunk.text for chunk in chunks))
    tokens = [model._model.token_count([text]) for text in texts]
    if max(tokens) >= 512:
        raise ValueError("At least one candidate reaches the embedding truncation limit")
    print(f"Embedding {len(texts)} overlapping passages; max {max(tokens)} tokens...", flush=True)
    started = time.perf_counter()
    vectors = dict(zip(texts, model.embed_documents(texts)))
    store = PgVectorStore(database_url(), model.dimensions, model.storage_model_id, config["table_name"])
    store.create_schema()
    store.enable_keyword_search()
    store.upsert("D", chunks, [vectors[chunk.text] for chunk in chunks], [config["document_id"]])
    elapsed = time.perf_counter() - started
    print("Loading the local reranker before evaluation...", flush=True)
    reranker = LocalReranker(config["reranker_name"], config["reranker_cache"])
    if baseline_state() != baseline:
        raise ValueError("Baseline changed during candidate setup")
    setup = {"prepared_at_utc": datetime.now(timezone.utc).isoformat(),
             "config_sha256": sha(config_path), "questions": questions,
             "prepared_pages_sha256": sha(ROOT / config["prepared_pages_path"]),
             "baseline": baseline, "candidate_index": index_state(config),
             "storage_model_id": model.storage_model_id, "dimensions": model.dimensions,
             "reranker_name": reranker.model_name, "reranker_fingerprint": reranker.fingerprint,
             "reranker_model_files": reranker.model_files,
             "chunk_count": len(chunks), "max_embedding_tokens": max(tokens),
             "max_chunk_characters": max(len(chunk.text) for chunk in chunks),
             "embedding_and_storage_seconds": elapsed, "embedding_api_cost_usd": 0,
             "candidate_order": ORDER, "candidate_params": {"depth": 30, "rrf_k": 60,
                                                               "rerank_pool": 30}}
    write_json(output / "setup.json", setup)
    print(f"Candidate collection ready: {len(chunks)} chunks. Original table unchanged.")


def evaluate(phase: str, config_path: Path, config: dict) -> dict:
    output = ROOT / config["output_dir"]
    setup_path = output / "setup.json"
    setup = json.loads(setup_path.read_text(encoding="utf-8"))
    if (question_state() != setup["questions"] or baseline_state() != setup["baseline"]
            or index_state(config) != setup["candidate_index"]
            or sha(config_path) != setup["config_sha256"]
            or sha(ROOT / config["prepared_pages_path"]) != setup["prepared_pages_sha256"]):
        raise ValueError("A frozen experiment input changed")
    decision = None
    if phase == "test":
        decision = json.loads((output / "selection.json").read_text(encoding="utf-8"))
        if decision["setup_sha256"] != sha(setup_path):
            raise ValueError("Selection does not belong to this setup")
        methods = list(dict.fromkeys(["baseline_C", decision["selected_strategy"]]))
    else:
        methods = ["D", "E", "F"]
    folder = output / phase
    folder.mkdir(parents=True, exist_ok=False)
    metadata = {"status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "phase": phase, "setup_sha256": sha(setup_path), "decision_before_test": decision}
    write_json(folder / "run_metadata.json", metadata)
    model = MyEmbedder(config["model_name"], config["model_cache"])
    if model.storage_model_id != setup["storage_model_id"]:
        raise ValueError("Embedding model changed")
    reranker = LocalReranker(config["reranker_name"], config["reranker_cache"])
    if reranker.fingerprint != setup["reranker_fingerprint"]:
        raise ValueError("Reranker model changed")
    baseline = PgVectorStore(database_url(), model.dimensions, model.storage_model_id)
    improved = PgVectorStore(database_url(), model.dimensions, model.storage_model_id, config["table_name"])
    traces = []
    if phase == "dev":
        traces = [{**trace, "strategy": "baseline_C", "reused_unchanged_v1_dev_trace": True}
                  for trace in read_records(ROOT / "results/roshidere/benchmark/dev/traces.jsonl")
                  if trace["strategy"] == "C"]
    with (folder / "traces.jsonl").open("x", encoding="utf-8") as file:
        for trace in traces:
            file.write(json.dumps(trace, ensure_ascii=False) + "\n")
        for question in [q for q in read_records(BENCHMARK / "questions.jsonl") if q["split"] == phase]:
            vector = model.embed_query(question["question"])
            filters = question.get("filter") or None
            for method in methods:
                started = time.perf_counter()
                hits = (baseline.search("C", vector, filters=filters) if method == "baseline_C"
                        else retrieve(improved, question["question"], vector, method, filters,
                                      reranker=reranker))
                trace = {**evaluate_query(question, hits), "strategy": method,
                         "filter_applied": filters or {},
                         "retrieval_ms": (time.perf_counter() - started) * 1000}
                traces.append(trace)
                file.write(json.dumps(trace, ensure_ascii=False) + "\n")
                file.flush()
            print(f"{phase}: {question['id']} complete", flush=True)
    if baseline_state() != setup["baseline"] or index_state(config) != setup["candidate_index"]:
        raise ValueError("Index changed during evaluation")
    summary = summarize(traces)
    write_json(folder / "metrics.json", summary)
    if phase == "dev":
        ranked = sorted(summary["metrics"], key=lambda m: (-m["evidence_hit_at_3_count"],
                                                         -m["hit_at_1_count"], ORDER.index(m["strategy"])))
        decision = {"selected_strategy": ranked[0]["strategy"], "selected_at_utc": datetime.now(timezone.utc).isoformat(),
                    "setup_sha256": sha(setup_path), "test_used": False, "ranking": ranked,
                    "rule": "Highest dev Hit@3, then Hit@1, then baseline_C/D/E/F simplicity order"}
        write_json(output / "selection.json", decision)
    else:
        by_method = {m["strategy"]: m for m in summary["metrics"]}
        selected = decision["selected_strategy"]
        old, new = by_method["baseline_C"], by_method[selected]
        nonregression = (new["evidence_hit_at_3_count"] >= old["evidence_hit_at_3_count"]
                         and new["hit_at_1_count"] >= old["hit_at_1_count"])
        promoted = selected != "baseline_C" and nonregression
        promotion = {"dev_selected": selected, "fresh_test_nonregression": nonregression,
                     "promoted": promoted, "rule_predeclared_in": "benchmark/roshidere-v2/promotion_gate.json"}
        if promoted:
            write_json(ROOT / "configs" / "active.json", {
                "config": str(config_path.resolve().relative_to(ROOT)).replace("\\", "/"),
                "strategy": selected, "selection": str((output / "selection.json").relative_to(ROOT)).replace("\\", "/")})
        write_json(output / "promotion.json", promotion)
    metadata.update(status="complete", finished_at_utc=datetime.now(timezone.utc).isoformat(),
                    traces=len(traces), api_cost_usd=0)
    write_json(folder / "run_metadata.json", metadata)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "dev", "test"))
    parser.add_argument("--config", type=Path, default=ROOT / "configs/roshidere-v2.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.phase == "prepare":
        prepare(args.config, config)
    else:
        evaluate(args.phase, args.config, config)


if __name__ == "__main__":
    main()
