"""Real, local CPU embeddings via FastEmbed/ONNX; no API or mock fallback."""
import os
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
from typing import Protocol

from .paths import cache_path


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Download model weights to the chosen cache, then embed text locally."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5",
                 cache_dir: str | Path | None = None) -> None:
        cache = cache_path("fastembed", cache_dir)
        cache.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(cache / "huggingface")
        os.environ["HF_HUB_CACHE"] = str(cache / "huggingface" / "hub")
        os.environ["HF_XET_CACHE"] = str(cache / "huggingface" / "xet")
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        from fastembed import TextEmbedding

        descriptions = {item["model"]: item for item in TextEmbedding.list_supported_models()}
        if model_name not in descriptions:
            raise ValueError(f"Unsupported FastEmbed model: {model_name}")
        self.model_name = model_name
        self.dimensions = descriptions[model_name]["dim"]
        self._model = TextEmbedding(model_name=model_name, cache_dir=str(cache), threads=4,
                                    providers=["CPUExecutionProvider"], cuda=False)
        # FastEmbed is pinned; record the actual weights and tokenizer used.
        model_dir = Path(self._model.model._model_dir)
        self.model_files = {}
        for name in (descriptions[model_name]["model_file"], "tokenizer.json",
                     "config.json", "tokenizer_config.json", "special_tokens_map.json"):
            file = model_dir / name
            if file.is_file():
                with file.open("rb") as stream:
                    self.model_files[name] = hashlib.file_digest(stream, "sha256").hexdigest()
        fingerprint = hashlib.sha256(json.dumps(self.model_files, sort_keys=True).encode()).hexdigest()
        self.storage_model_id = f"{model_name}|fastembed={version('fastembed')}|sha256={fingerprint}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if any(not text.strip() for text in texts):
            raise ValueError("Cannot embed empty document text")
        if not texts:
            return []
        vectors = [vector.tolist() for vector in
                   self._model.passage_embed(texts, batch_size=32)]
        if len(vectors) != len(texts) or any(len(v) != self.dimensions for v in vectors):
            raise RuntimeError("Embedding provider returned unexpected vector shapes")
        return vectors

    def embed_query(self, question: str) -> list[float]:
        if not question.strip():
            raise ValueError("Question must not be empty")
        vector = next(iter(self._model.query_embed(question))).tolist()
        if len(vector) != self.dimensions:
            raise RuntimeError("Embedding provider returned an unexpected query shape")
        return vector
