"""Apply a documented, configurable working-corpus selection to extracted pages."""
from dataclasses import replace
import re

from .models import DocumentPage


def prepare_pages(pages: list[DocumentPage], config: dict) -> tuple[list[DocumentPage], list[dict]]:
    if len({page.page for page in pages}) != len(pages):
        raise ValueError("Duplicate PDF page numbers in input")
    if any(page.document_id != config["document_id"] for page in pages):
        raise ValueError("Input document IDs do not match the corpus configuration")
    sections = config["sections"]
    if len({section["name"] for section in sections}) != len(sections):
        raise ValueError("Section names must be unique")
    occupied = set()
    page_index = {page.page: page for page in pages}
    for section in sections:
        if not 1 <= section["start_page"] <= section["end_page"]:
            raise ValueError("Invalid section page range")
        numbers = set(range(section["start_page"], section["end_page"] + 1))
        if occupied & numbers:
            raise ValueError("Section page ranges must not overlap")
        occupied.update(numbers)
        opening = page_index.get(section["start_page"])
        if opening is None or not " ".join(opening.text.split()).startswith(section["heading_prefix"]):
            raise ValueError(f"Section heading could not be verified: {section['name']}")

    prepared = []
    audit = []
    for page in sorted(pages, key=lambda item: item.page):
        section = next((item for item in sections if
                        item["start_page"] <= page.page <= item["end_page"]), None)
        reason = None
        text = re.sub(rf"(?m)^Glucose Translations[ \t]+{page.page}[ \t]*$", "", page.text).strip()
        if page.metadata.get("extraction_status") == "error":
            raise ValueError(f"Extraction error must be resolved before ingestion: page {page.page}")
        if section is None:
            reason = "outside_selected_story_sections"
        elif not any(character.isalpha() for character in text):
            reason = "no_prose_after_footer_removal"
        elif re.match(r"^\[\d+\]:", text):
            reason = "standalone_translator_note_page"
        audit.append({"page": page.page, "included": reason is None,
                      "reason": reason, "normalized_characters": len(text)})
        if reason is not None:
            continue
        metadata = dict(page.metadata)
        metadata.update(section=section["name"], section_source=config["section_source"],
                        language="en", document_type="novel", character_count=len(text),
                        offset_basis="prepared_page_text")
        prepared.append(replace(page, text=text, metadata=metadata))
    if not prepared:
        raise ValueError("Corpus selection contains no usable text")
    return prepared, audit
