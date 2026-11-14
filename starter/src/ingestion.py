"""Extract PDF pages, preserving source locations and extraction problems."""
import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path
import re
import unicodedata

from pypdf import PdfReader

from .models import DocumentPage


logger = logging.getLogger(__name__)


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Return one record per physical PDF page, numbered from one.

    Empty and failed pages retain their position and have an extraction_status
    in metadata. File-level errors propagate; page extraction errors are logged
    and recorded so the remaining pages can still be read. OCR is not performed.
    """
    path = Path(path)
    if not document_id.strip() or not source.strip():
        raise ValueError("document_id and source must not be empty")

    pages: list[DocumentPage] = []
    with path.open("rb") as stream:
        reader = PdfReader(stream)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError(f"PDF requires a password: {path}")

        for page_number, pdf_page in enumerate(reader.pages, start=1):
            text = ""
            metadata = {}
            try:
                # Layout extraction avoids one-word-per-line output in some PDFs.
                raw_text = pdf_page.extract_text(
                    extraction_mode="layout", layout_mode_strip_rotated=False
                )
                text = normalize_text(raw_text or "")
                metadata["extraction_status"] = "ok" if text else "empty"
                if not text:
                    logger.warning(
                        "%s: PDF page %d has no extractable text "
                        "(blank or image-only; OCR not performed)",
                        document_id, page_number,
                    )
            except Exception as error:
                logger.exception(
                    "%s: failed to extract PDF page %d", document_id, page_number
                )
                metadata["extraction_status"] = "error"
                metadata["extraction_error"] = f"{type(error).__name__}: {error}"

            metadata["character_count"] = len(text)
            pages.append(DocumentPage(
                document_id=document_id,
                source=source,
                page=page_number,
                text=text,
                metadata=metadata,
            ))
    return pages


def normalize_text(text: str) -> str:
    """Normalize Unicode and spacing, retaining line and paragraph boundaries.

    Keep punctuation, accents, headings, and page furniture for traceability.
    Corpus-specific header/footer removal can be added as a separate step.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = "".join(
        character for character in text
        if character in "\n\t" or unicodedata.category(character) != "Cc"
    )
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--source", help="Source URL or path; defaults to the PDF path")
    parser.add_argument("--output", type=Path, help="Save page records as UTF-8 JSONL")
    args = parser.parse_args()
    if args.output and args.output.resolve() == args.pdf.resolve():
        parser.error("Output must be different from the source PDF")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    pages = load_pdf(args.pdf, args.document_id, args.source or str(args.pdf.resolve()))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as output:
            for page in pages:
                output.write(json.dumps(asdict(page), ensure_ascii=False) + "\n")
        print(f"Saved page records to {args.output}")

    statuses = [page.metadata["extraction_status"] for page in pages]
    print(
        f"Physical pages: {len(pages)} | Text pages: {statuses.count('ok')} | "
        f"Empty pages: {statuses.count('empty')} | Errors: {statuses.count('error')}"
    )
    print("Text pages still need review before counting them as lab content pages.")
    if not any(page.text for page in pages) or "error" in statuses:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
