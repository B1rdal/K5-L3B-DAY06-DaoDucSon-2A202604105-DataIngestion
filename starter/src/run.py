"""Prepare chunks, ingest real local embeddings, or search the pgvector database."""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import statistics
import sys
import time

from dotenv import load_dotenv
import psycopg

from .chunking import by_paragraph, fixed_size
from .corpus import prepare_pages
from .embeddings import MyEmbedder
from .models import DocumentPage
from .store import PgVectorStore


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_records(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def build_chunks(config: dict) -> tuple[dict, dict]:
    started = time.perf_counter()
    source = ROOT / config["pages_path"]
    records = [json.loads(line) for line in source.read_text(encoding="utf-8-sig").splitlines()
               if line.strip()]
    pages, audit = prepare_pages([DocumentPage(**record) for record in records], config)
    if len(pages) < 30:
        raise ValueError("Working corpus has fewer than 30 text pages")
    a = [chunk for page in pages for chunk in
         fixed_size(page, config["chunk_size"], config["overlap"])]
    b = [chunk for page in pages for chunk in
         by_paragraph(page, config["paragraph_max_size"])]
    chunks = {"A": a, "B": b, "C": b}
    output = ROOT / config["output_dir"]
    write_records(output / "prepared_pages.jsonl", pages)
    write_json(output / "page_selection.json", {
        "scope": config["corpus_scope"], "review_status": config["content_review_status"],
        "section_source": config["section_source"], "pages": audit,
    })
    stats = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "input_text_pages": len(records), "prepared_text_pages": len(pages),
        "section_page_counts": dict(Counter(page.metadata["section"] for page in pages)),
        "strategies": {}, "corpus_scope": config["corpus_scope"],
        "content_review_status": config["content_review_status"],
    }
    for strategy, items in chunks.items():
        write_records(output / f"chunks_{strategy}.jsonl", items)
        lengths = [len(chunk.text) for chunk in items]
        stats["strategies"][strategy] = {
            "chunk_count": len(items), "characters": sum(lengths),
            "min_characters": min(lengths), "max_characters": max(lengths),
            "mean_characters": statistics.mean(lengths),
            "median_characters": statistics.median(lengths),
            "chunking": "fixed" if strategy == "A" else "paragraph",
            "overlap": config["overlap"] if strategy == "A" else 0,
            "filter_policy": "provided section filter only" if strategy == "C" else "none",
        }
    stats["chunking_seconds"] = time.perf_counter() - started
    write_json(output / "chunk_stats.json", stats)
    print(f"Prepared {len(pages)} text pages; selection audit: {output / 'page_selection.json'}")
    print("Chunk counts: " + ", ".join(f"{key}={len(items)}" for key, items in chunks.items()))
    return chunks, stats


def database_url() -> str:
    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL missing from starter/.env")
    return url


def ingest(config: dict) -> None:
    started = time.perf_counter()
    chunks, stats = build_chunks(config)
    print("Loading the local embedding model...", flush=True)
    model = MyEmbedder(config["model_name"], config["model_cache"])
    store = PgVectorStore(database_url(), model.dimensions, model.storage_model_id)
    store.create_schema()
    unique_texts = list(dict.fromkeys(chunk.text for items in chunks.values() for chunk in items))
    print(f"Embedding {len(unique_texts)} unique passages locally...", flush=True)
    embed_started = time.perf_counter()
    vectors = model.embed_documents(unique_texts)
    vector_by_text = dict(zip(unique_texts, vectors))
    stats["embedding_seconds"] = time.perf_counter() - embed_started
    stats["model_name"] = model.model_name
    stats["storage_model_id"] = model.storage_model_id
    stats["model_files_sha256"] = model.model_files
    stats["dimensions"] = model.dimensions
    stats["unique_embedded_texts"] = len(unique_texts)
    stats["embedding_backend"] = "local ONNX CPU, 4 threads, batch size 32"
    stats["query_document_processing"] = "FastEmbed query_embed/passage_embed, no additional prefix, model token limit 512"
    stats["similarity"] = "exact cosine; no approximate vector index"
    stats["api_cost_usd"] = 0
    stats["api_cost_note"] = "Local inference; excludes hardware, electricity, and network costs"
    stats["package_versions"] = {name: version(name) for name in
                                 ("fastembed", "onnxruntime", "psycopg", "pypdf", "numpy")}
    with psycopg.connect(database_url(), connect_timeout=5) as connection:
        stats["postgresql_version"] = connection.execute("SHOW server_version").fetchone()[0]
        stats["pgvector_version"] = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()[0]
    for strategy, items in chunks.items():
        save_started = time.perf_counter()
        embeddings = [vector_by_text[chunk.text] for chunk in items]
        store.upsert(strategy, items, embeddings, document_ids=[config["document_id"]])
        with psycopg.connect(database_url(), connect_timeout=5) as connection:
            count = connection.execute(
                "SELECT count(*) FROM day6_chunks WHERE strategy = %s AND document_id = %s",
                (strategy, config["document_id"]),
            ).fetchone()[0]
        if count != len(items):
            raise RuntimeError(f"Stored row count mismatch for strategy {strategy}")
        stats["strategies"][strategy]["database_rows"] = count
        stats["strategies"][strategy]["database_write_seconds"] = time.perf_counter() - save_started
        print(f"Stored strategy {strategy}: {count} chunks", flush=True)
    stats["total_ingest_seconds"] = time.perf_counter() - started
    stats["benchmark_status"] = "Not run; gold questions and a frozen dev/test split are still required"
    write_json(ROOT / config["output_dir"] / "ingest_stats.json", stats)
    print("Ingestion complete. Source passages and real embeddings are now in PostgreSQL.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Override the active search configuration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("chunk", help="Prepare working corpus and export A/B/C chunks")
    commands.add_parser("ingest", help="Chunk, embed locally, and store all three strategies")
    search = commands.add_parser("search", help="Retrieve passages; this is not an LLM answer")
    search.add_argument("question")
    search.add_argument("--strategy", choices=("A", "B", "C", "D", "E", "F"))
    search.add_argument("--section", help="Optional user-supplied section; C/D/E/F only")
    search.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    active_path = ROOT / "configs" / "active.json"
    active = json.loads(active_path.read_text(encoding="utf-8")) if active_path.exists() else {}
    default_config = (ROOT / active["config"] if args.command == "search" and active
                      else ROOT / "configs" / "roshidere.json")
    config_path = args.config or default_config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if args.command != "search" and config.get("table_name") == "day6_chunks_v2":
        parser.error("Use python -m src.improvement prepare for the improved collection")
    if args.command == "chunk":
        build_chunks(config)
    elif args.command == "ingest":
        ingest(config)
    else:
        default_strategy = config.get("default_strategy", "C")
        selection_path = ROOT / config["output_dir"] / "selection.json"
        if config.get("table_name") == "day6_chunks_v2" and selection_path.exists():
            default_strategy = json.loads(selection_path.read_text(encoding="utf-8"))["selected_strategy"]
        if not args.config and active:
            default_strategy = active["strategy"]
        strategy = args.strategy or default_strategy
        if strategy == "baseline_C":
            strategy = "C"
        if args.section and strategy in {"A", "B"}:
            parser.error("Only strategies C/D/E/F use section filters")
        if args.section and args.section not in {item["name"] for item in config["sections"]}:
            parser.error("Unknown section; see the section names in the configuration")
        model = MyEmbedder(config["model_name"], config["model_cache"])
        filters = {"section": args.section} if args.section else None
        vector = model.embed_query(args.question)
        if strategy in {"D", "E", "F"}:
            if config.get("table_name") != "day6_chunks_v2":
                parser.error("Improved strategies require configs/roshidere-v2.json")
            from .retrieval import LocalReranker, retrieve
            store = PgVectorStore(database_url(), model.dimensions, model.storage_model_id, config["table_name"])
            store.create_schema()
            reranker = (LocalReranker(config["reranker_name"], config["reranker_cache"])
                        if strategy == "F" else None)
            hits = retrieve(store, args.question, vector, strategy, filters, args.top_k, reranker)
        else:
            store = PgVectorStore(database_url(), model.dimensions, model.storage_model_id)
            store.create_schema()
            hits = store.search(strategy, vector, args.top_k, filters)
        print(json.dumps(hits, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
