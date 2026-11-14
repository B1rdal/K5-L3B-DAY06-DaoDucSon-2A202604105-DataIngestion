"""Package text references, restore private evidence locally, and check submission files."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "starter"))

from src.corpus import prepare_pages
from src.evaluation import normalized
from src.ingestion import load_pdf


PACK = REPO / "data" / "artifact_references.json"
PRIVATE_PATTERNS = [
    "benchmark/*/questions.jsonl", "starter/results/*pages.jsonl",
    "starter/results/roshidere/prepared_pages.jsonl",
    "starter/results/roshidere/chunks_*.jsonl",
    "starter/results/roshidere-v2/chunks_D.jsonl",
    "starter/results/**/traces.jsonl",
    "starter/results/checkpoint_audit/coherence_samples.jsonl",
    "starter/results/checkpoint_audit/grounding_cases.jsonl",
    "starter/results/checkpoint_audit/source_pages.jsonl",
    "starter/results/checkpoint_audit/pdf_contents_page.txt",
]


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def text_maps(raw_pages: list[dict], prepared: list[dict]) -> dict:
    raw = {page["page"]: page["text"] for page in raw_pages}
    return {"raw": raw, "prepared": {page["page"]: page["text"] for page in prepared},
            "normalized_raw": {page: normalized(text) for page, text in raw.items()}}


def reference(text: str, pages: list[int], maps: dict, quote: bool = False) -> dict:
    bases = ["normalized_raw"] if quote else ["prepared", "raw"]
    for page in pages:
        for basis in bases:
            source = maps[basis].get(page)
            if source is None:
                continue
            start = source.find(text)
            if start >= 0:
                return {"$source_text": {"basis": basis, "page": page, "start": start,
                                         "end": start + len(text),
                                         "sha256_utf8": sha_bytes(text.encode("utf-8"))}}
    raise ValueError("A source text field could not be represented by a verified page location")


def encode(value: object, maps: dict) -> object:
    if isinstance(value, list):
        return [encode(item, maps) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "text" and isinstance(item, str):
            result[key] = reference(item, [value["page"]], maps)
        elif key == "evidence_quote" and isinstance(item, str):
            pages = value["gold_page"]
            result[key] = reference(item, pages if isinstance(pages, list) else [pages], maps, True)
        else:
            result[key] = encode(item, maps)
    return result


def decode(value: object, maps: dict) -> object:
    if isinstance(value, list):
        return [decode(item, maps) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"$source_text"}:
        item = value["$source_text"]
        source = maps[item["basis"]][item["page"]]
        start, end = item["start"], item["end"]
        if not 0 <= start <= end <= len(source):
            raise ValueError("Invalid source text offsets")
        text = source[start:end]
        if sha_bytes(text.encode("utf-8")) != item["sha256_utf8"]:
            raise ValueError("Restored source text differs from the archived evidence")
        return text
    return {key: decode(item, maps) for key, item in value.items()}


def render(artifact: dict, maps: dict) -> bytes:
    if artifact["kind"] == "jsonl":
        records = decode(artifact["records"], maps)
        text = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
        if artifact["final_newline"]:
            text += "\n"
    else:
        text = decode(artifact["content"], maps)
    data = text.replace("\n", artifact["newline"]).encode("utf-8")
    if sha_bytes(data) != artifact["sha256"]:
        raise ValueError(f"Artifact does not reproduce byte-for-byte: {artifact['path']}")
    return data


def build() -> None:
    raw = read_jsonl(REPO / "starter/results/roshidere_pages.jsonl")
    prepared = read_jsonl(REPO / "starter/results/roshidere/prepared_pages.jsonl")
    maps = text_maps(raw, prepared)
    paths = sorted({path for pattern in PRIVATE_PATTERNS for path in REPO.glob(pattern)})
    artifacts = []
    for path in paths:
        data = path.read_bytes()
        item = {"path": path.relative_to(REPO).as_posix(), "sha256": sha_bytes(data),
                "newline": "\r\n" if b"\r\n" in data else "\n",
                "final_newline": data.endswith(b"\n")}
        if path.suffix == ".jsonl":
            item.update(kind="jsonl", records=encode(read_jsonl(path), maps))
        else:
            item.update(kind="text", content=reference(path.read_text(encoding="utf-8"), [13], maps))
        render(item, maps)
        artifacts.append(item)
    verification = json.loads((REPO / "starter/results/checkpoint_audit/source_verification.json").read_text(encoding="utf-8"))
    config_path = REPO / "starter/configs/roshidere.json"
    pack = {"schema_version": 1, "source_id": "roshidere-vol10",
            "source_pdf_sha256": verification["pdf_sha256"],
            "canonical_source": raw[0]["source"],
            "normalization_code_sha256": sha_bytes((REPO / "starter/src/ingestion.py").read_bytes()),
            "corpus_config_sha256": sha_bytes(config_path.read_bytes()),
            "permission_status": "unconfirmed",
            "explanation": "Passage text/evidence quotes are replaced with original page offsets and hashes. An authorized matching PDF is required to restore them locally.",
            "artifacts": artifacts}
    json_write(PACK, pack)
    print(f"Built {len(artifacts)} text-reference artifacts; exact reconstruction verified locally.")


def restore(pdf: Path, output_root: Path) -> None:
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    with pdf.open("rb") as stream:
        actual_pdf_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual_pdf_hash != pack["source_pdf_sha256"]:
        raise ValueError("This PDF differs from the archived source; use the matching authorized snapshot")
    if sha_bytes((REPO / "starter/src/ingestion.py").read_bytes()) != pack["normalization_code_sha256"]:
        raise ValueError("Normalization code differs from the archived version")
    config_path = REPO / "starter/configs/roshidere.json"
    if sha_bytes(config_path.read_bytes()) != pack["corpus_config_sha256"]:
        raise ValueError("Corpus configuration differs from the archived version")
    pages = load_pdf(pdf, pack["source_id"], pack["canonical_source"])
    config = json.loads(config_path.read_text(encoding="utf-8"))
    prepared, _ = prepare_pages(pages, config)
    maps = text_maps([asdict(page) for page in pages], [asdict(page) for page in prepared])
    output_root = output_root.resolve()
    materialized = []
    for artifact in pack["artifacts"]:
        relative = Path(artifact["path"])
        destination = (output_root / relative).resolve()
        if relative.is_absolute() or not destination.is_relative_to(output_root):
            raise ValueError("Unsafe artifact output path")
        data = render(artifact, maps)
        if destination.exists() and destination.read_bytes() != data:
            raise FileExistsError(f"Existing artifact differs; left unchanged: {destination}")
        materialized.append((destination, data))
    for destination, data in materialized:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(data)
    print(f"Restored and hash-verified {len(materialized)} private artifacts in {output_root}")
    print("Archived canonical source IDs/paths are preserved for hash compatibility; the --pdf path supplies local access.")


def check() -> None:
    required = ["README.md", "STUDENT.md", "SUBMISSION_GUIDE.md", "data/manifest.json",
                "data/pages.csv", "data/access.md", "data/artifact_references.json",
                "results/retrieval_metrics.csv", "results/audit_summary.csv", "results/README.md",
                "artifacts/experiment_log.csv", "artifacts/improvement_log.csv",
                "report/individual/2A202604105_DaoDucSon.md", "starter/requirements-lock.txt"]
    missing = [path for path in required if not (REPO / path).is_file()]
    if missing:
        raise ValueError(f"Missing submission files: {missing}")
    manifest = json.loads((REPO / "data/manifest.json").read_text(encoding="utf-8"))
    if len(manifest["counted_content_pages"]) < 30:
        raise ValueError("Fewer than 30 explicitly reviewed content pages")
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    by_path = {artifact["path"]: artifact for artifact in pack["artifacts"]}
    questions = by_path["benchmark/roshidere/questions.jsonl"]["records"]
    if sum(q["split"] == "dev" for q in questions) < 15 or sum(q["split"] == "test" for q in questions) < 5:
        raise ValueError("Benchmark split is incomplete")
    if sum(bool(q.get("filter")) for q in questions) < 3:
        raise ValueError("Not enough filter questions")
    if not any(q["split"] == "test" and q.get("filter") for q in questions):
        raise ValueError("The test split needs at least one filter question")
    print(f"Technical submission files present; {len(manifest['counted_content_pages'])} reviewed content pages; {len(questions)} original questions.")
    print(f"Private evidence is represented by {len(pack['artifacts'])} restorable references.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build")
    commands.add_parser("check")
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("--pdf", type=Path, required=True)
    restore_parser.add_argument("--output-root", type=Path, default=REPO)
    args = parser.parse_args()
    if args.command == "build":
        build()
    elif args.command == "restore":
        restore(args.pdf, args.output_root)
    else:
        check()


if __name__ == "__main__":
    main()
