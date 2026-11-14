"""Resolve runtime storage independently of the current working directory."""
import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def cache_path(kind: str, configured: str | Path | None = None) -> Path:
    """Local overrides win; relative paths are based on starter/, never cwd."""
    variables = {"fastembed": "DAY6_MODEL_CACHE", "rerankers": "DAY6_RERANKER_CACHE"}
    if kind not in variables:
        raise ValueError("Unknown model cache kind")
    load_dotenv(ROOT / ".env")
    value = os.getenv(variables[kind]) or configured or f".cache/{kind}"
    path = Path(os.path.expandvars(str(value))).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()
