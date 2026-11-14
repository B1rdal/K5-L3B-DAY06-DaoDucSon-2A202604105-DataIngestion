"""Deterministic, page-local chunking with traceable character offsets."""
from copy import deepcopy
import hashlib
import json
import re

from .models import Chunk, DocumentPage


def _chunk(page: DocumentPage, start: int, end: int, index: int,
           settings: dict) -> Chunk:
    text = page.text[start:end]
    identity = ["chunk-v1", page.document_id, page.source, page.page,
                settings, start, end, text]
    chunk_id = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    metadata = deepcopy(page.metadata)
    metadata.update(settings)
    metadata.update(chunk_index=index, char_start=start, char_end=end)
    return Chunk(chunk_id, page.document_id, page.source, page.page, text, metadata)


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split into character windows; stop when the last window reaches page end."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("size must be positive and 0 <= overlap < size")
    if not page.text.strip():
        return []
    chunks = []
    settings = {"chunking": "fixed", "chunk_size": size, "overlap": overlap}
    for start in range(0, len(page.text), size - overlap):
        end = min(start + size, len(page.text))
        if page.text[start:end].strip():
            chunks.append(_chunk(page, start, end, len(chunks), settings))
        if end == len(page.text):
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Pack blank-line-separated paragraphs up to max_size characters.

    Oversized paragraphs split at whitespace when possible, or at a character
    boundary for a word longer than max_size. Offsets address the original page
    text; chunks never cross pages and no non-whitespace content is discarded.
    """
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    spans: list[tuple[int, int]] = []
    pending: tuple[int, int] | None = None
    for paragraph in re.finditer(r"\S.*?(?=\n[ \t]*\n|\Z)", page.text, re.DOTALL):
        start, end = paragraph.span()
        while end > start and page.text[end - 1].isspace():
            end -= 1
        if end - start > max_size:
            if pending:
                spans.append(pending)
                pending = None
            while start < end:
                limit = min(start + max_size, end)
                if limit < end:
                    boundaries = [m.start() for m in
                                  re.finditer(r"\s", page.text[start:limit + 1])]
                    if boundaries and boundaries[-1] > 0:
                        limit = start + boundaries[-1]
                piece_end = limit
                while piece_end > start and page.text[piece_end - 1].isspace():
                    piece_end -= 1
                if piece_end > start:
                    spans.append((start, piece_end))
                start = limit
                while start < end and page.text[start].isspace():
                    start += 1
        elif pending and end - pending[0] <= max_size:
            pending = (pending[0], end)
        else:
            if pending:
                spans.append(pending)
            pending = (start, end)
    if pending:
        spans.append(pending)
    settings = {"chunking": "paragraph", "chunk_size": max_size, "overlap": 0}
    return [_chunk(page, start, end, index, settings)
            for index, (start, end) in enumerate(spans)]


def sentence_windows(page: DocumentPage, max_size: int = 1000, overlap: int = 250) -> list[Chunk]:
    """Overlapping page-local windows, preferring sentence-end boundaries.

    This is a punctuation heuristic, not a linguistic sentence parser. Oversized
    sentences use whitespace boundaries and long words use character boundaries.
    Character offsets always point into the unchanged prepared page text.
    """
    if max_size <= 0 or not 0 <= overlap < max_size:
        raise ValueError("max_size must be positive and 0 <= overlap < max_size")
    text = page.text
    if not text.strip():
        return []
    ends = [match.end() for match in re.finditer(r'''[.!?\u2026][\u201d\u2019"')\]]*(?=\s|$)''', text)]
    chunks = []
    start = 0
    settings = {"chunking": "sentence_window", "chunk_size": max_size, "overlap": overlap}
    while start < len(text):
        limit = min(start + max_size, len(text))
        end = limit
        if limit < len(text):
            candidates = [position for position in ends if start + max_size // 2 <= position <= limit]
            if candidates:
                end = candidates[-1]
            else:
                spaces = [match.start() + start for match in re.finditer(r"\s", text[start:limit + 1])]
                if spaces and spaces[-1] > start:
                    end = spaces[-1]
        trimmed_end = end
        while trimmed_end > start and text[trimmed_end - 1].isspace():
            trimmed_end -= 1
        if trimmed_end > start:
            chunks.append(_chunk(page, start, trimmed_end, len(chunks), settings))
        if end == len(text):
            break
        target = max(start + 1, end - overlap)
        boundaries = [position for position in ends if start < position <= target]
        next_start = boundaries[-1] if boundaries else target
        # Avoid splitting a word at the next start when a nearby space exists.
        if not boundaries and next_start > 0 and not text[next_start - 1].isspace():
            space = re.search(r"\s", text[next_start:end])
            if space:
                next_start += space.end()
        start = max(start + 1, next_start)
        while start < len(text) and text[start].isspace():
            start += 1
    return chunks
