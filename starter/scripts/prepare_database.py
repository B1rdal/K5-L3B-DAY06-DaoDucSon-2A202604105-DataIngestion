"""Rebuild missing search indexes without overwriting measured result files."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.embeddings import MyEmbedder
from src.models import Chunk
from src.retrieval import LocalReranker
from src.run import database_url
from src.store import PgVectorStore


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def chunks(path: str) -> list[Chunk]:
    return [Chunk(**json.loads(line)) for line in (ROOT / path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def collection_matches(store: PgVectorStore, strategy: str, items: list[Chunk], document_id: str) -> bool:
    expected = sorted((asdict(item) for item in items), key=lambda item: item['chunk_id'])
    with psycopg.connect(store.database_url, connect_timeout=5) as connection:
        rows = connection.execute(sql.SQL('SELECT chunk_id, document_id, source, page, text, metadata FROM {} WHERE strategy = %s AND document_id = %s ORDER BY chunk_id').format(sql.Identifier(store.table_name)), (strategy, document_id)).fetchall()
    actual = [dict(zip(('chunk_id', 'document_id', 'source', 'page', 'text', 'metadata'), row)) for row in rows]
    return actual == expected


def main() -> None:
    config = load('configs/roshidere.json')
    improved = load('configs/roshidere-v2.json')
    stats = load('results/roshidere/ingest_stats.json')
    setup = load('results/roshidere-v2/setup.json')
    if stats['storage_model_id'] != setup['storage_model_id']:
        raise ValueError('The baseline and improved index require different embedding models')
    url = database_url()
    baseline_store = PgVectorStore(url, stats['dimensions'], stats['storage_model_id'])
    improved_store = PgVectorStore(url, setup['dimensions'], setup['storage_model_id'], improved['table_name'])
    baseline_store.create_schema()
    improved_store.create_schema()
    improved_store.enable_keyword_search()
    jobs = [(baseline_store, strategy, chunks(f'results/roshidere/chunks_{strategy}.jsonl')) for strategy in ('A', 'B', 'C')]
    jobs.append((improved_store, 'D', chunks('results/roshidere-v2/chunks_D.jsonl')))
    pending = [(store, strategy, items) for store, strategy, items in jobs
               if not collection_matches(store, strategy, items, config['document_id'])]
    if pending:
        print('Preparing local embeddings for missing indexes...', flush=True)
        model = MyEmbedder(config['model_name'], config['model_cache'])
        if model.storage_model_id != stats['storage_model_id']:
            raise ValueError('Downloaded model files differ from the archived model; no index was replaced')
        texts = list(dict.fromkeys(item.text for _, _, items in pending for item in items))
        vectors = dict(zip(texts, model.embed_documents(texts)))
        for store, strategy, items in pending:
            store.upsert(strategy, items, [vectors[item.text] for item in items], [config['document_id']])
            print(f'Ready: {store.table_name} / {strategy} / {len(items)} passages', flush=True)
    else:
        print('Existing A/B/C/F indexes match the archived passages; reusing them.', flush=True)
    print('Preparing the local reranker...', flush=True)
    reranker = LocalReranker(improved['reranker_name'], improved['reranker_cache'])
    if reranker.fingerprint != setup['reranker_fingerprint']:
        raise ValueError('Reranker files differ from the archived model')
    print('Search indexes and local models are ready. Measured result files were preserved.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, psycopg.Error) as exc:
        print(f'Index setup failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
