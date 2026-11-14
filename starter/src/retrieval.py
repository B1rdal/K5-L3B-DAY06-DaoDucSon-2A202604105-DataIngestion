"""Dense/full-text fusion and local query-passage reranking."""
import hashlib
import json
import math
from pathlib import Path

from .store import PgVectorStore
from .paths import cache_path


def reciprocal_rank_fusion(rankings: list[list[dict]], limit: int = 30, k: int = 60) -> list[dict]:
    if limit <= 0 or k <= 0:
        raise ValueError("Fusion limit and k must be positive")
    combined = {}
    for method, ranking in enumerate(rankings):
        seen = set()
        for rank, hit in enumerate(ranking, 1):
            key = hit["chunk_id"]
            if key in seen:
                continue
            seen.add(key)
            if key not in combined:
                combined[key] = {**hit, "score": 0.0, "score_type": "reciprocal_rank_fusion",
                                 "retriever_ranks": {}}
            combined[key]["score"] += 1 / (k + rank)
            combined[key]["retriever_ranks"][str(method)] = rank
    return sorted(combined.values(), key=lambda hit: (-hit["score"], hit["chunk_id"]))[:limit]


class LocalReranker:
    def __init__(self, model_name: str = "Xenova/ms-marco-MiniLM-L-6-v2",
                 cache_dir: str | Path | None = None) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        cache = cache_path("rerankers", cache_dir)
        cache.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self._model = TextCrossEncoder(model_name=model_name, cache_dir=str(cache),
                                       threads=4, providers=["CPUExecutionProvider"], cuda=False)
        description = next(item for item in TextCrossEncoder.list_supported_models()
                           if item["model"] == model_name)
        directory = Path(self._model.model._model_dir)
        self.model_files = {}
        for name in (description["model_file"], "tokenizer.json", "tokenizer_config.json", "config.json"):
            path = directory / name
            if path.is_file():
                with path.open("rb") as stream:
                    self.model_files[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        self.fingerprint = hashlib.sha256(json.dumps(self.model_files, sort_keys=True).encode()).hexdigest()

    def rerank(self, question: str, hits: list[dict], top_k: int = 3) -> list[dict]:
        if not hits:
            return []
        scores = list(self._model.rerank(question, [hit["text"] for hit in hits], batch_size=16))
        if len(scores) != len(hits) or not all(math.isfinite(score) for score in scores):
            raise RuntimeError("Reranker returned invalid scores")
        ranked = [{**hit, "fusion_score": hit["score"], "score": float(score),
                   "score_type": "cross_encoder_logit"} for hit, score in zip(hits, scores)]
        return sorted(ranked, key=lambda hit: (-hit["score"], hit["chunk_id"]))[:top_k]


def retrieve(store: PgVectorStore, question: str, vector: list[float], method: str,
             filters: dict | None = None, top_k: int = 3,
             reranker: LocalReranker | None = None) -> list[dict]:
    if not isinstance(top_k, int) or not 1 <= top_k <= 30:
        raise ValueError("Improved retrieval top_k must be between 1 and 30")
    if method == "D":
        return [{**hit, "score_type": "cosine_similarity"}
                for hit in store.search("D", vector, top_k, filters)]
    if method not in {"E", "F"}:
        raise ValueError("Unknown improved retrieval method")
    dense = store.search("D", vector, 30, filters)
    lexical = store.keyword_search("D", question, 30, filters)
    candidates = reciprocal_rank_fusion([dense, lexical], limit=30, k=60)
    if method == "F":
        if reranker is None:
            raise ValueError("Method F requires the configured local reranker")
        return reranker.rerank(question, candidates, top_k)
    return candidates[:top_k]
