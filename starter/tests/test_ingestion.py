"""Checks for page traceability, normalization, and extraction failures."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from pypdf import PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from src.ingestion import load_pdf, normalize_text


class IngestionTests(unittest.TestCase):
    def test_normalization_preserves_paragraphs_and_unicode(self):
        raw = "  Cafe\u0301\t title\r\n wrapped\u00a0 line \r\n\r\n\r\n Next\x00 paragraph  "
        self.assertEqual(normalize_text(raw), "Café title\nwrapped line\n\nNext paragraph")
        self.assertEqual(normalize_text(" \t\r\n"), "")

    def test_real_pdf_retains_blank_pages_and_physical_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pages.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            page = writer.add_blank_page(width=300, height=300)
            font = DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            })
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
            })
            content = DecodedStreamObject()
            content.set_data(b"BT /F1 12 Tf 30 250 Td (Hello PDF) Tj ET")
            page[NameObject("/Contents")] = content
            writer.add_blank_page(width=300, height=300)
            with path.open("wb") as output:
                writer.write(output)

            with self.assertLogs("src.ingestion", level="WARNING"):
                pages = load_pdf(path, "sample", "fixture.pdf")
            self.assertEqual([p.page for p in pages], [1, 2, 3])
            self.assertEqual([p.metadata["extraction_status"] for p in pages],
                             ["empty", "ok", "empty"])
            self.assertEqual(pages[1].text, "Hello PDF")
            self.assertTrue(all(p.document_id == "sample" and p.source == "fixture.pdf"
                                for p in pages))

            destination = Path(folder) / "output" / "pages.jsonl"
            command = subprocess.run(
                [sys.executable, "-m", "src.ingestion", str(path),
                 "--document-id", "sample", "--output", str(destination)],
                check=True, capture_output=True, text=True,
            )
            records = [json.loads(line) for line in
                       destination.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["page"] for record in records], [1, 2, 3])
            self.assertEqual(records[1]["text"], "Hello PDF")
            self.assertIn("Errors: 0", command.stdout)

    def test_page_failure_is_recorded_and_later_pages_are_read(self):
        good = Mock()
        good.extract_text.return_value = "Readable"
        broken = Mock()
        broken.extract_text.side_effect = ValueError("broken content")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "placeholder.pdf"
            path.touch()
            with patch("src.ingestion.PdfReader") as reader:
                reader.return_value.is_encrypted = False
                reader.return_value.pages = [good, broken, good]
                with self.assertLogs("src.ingestion", level="ERROR"):
                    pages = load_pdf(path, "sample", "fixture.pdf")
            self.assertEqual(pages[1].page, 2)
            self.assertEqual(pages[1].text, "")
            self.assertEqual(pages[1].metadata["extraction_status"], "error")
            self.assertIn("broken content", pages[1].metadata["extraction_error"])
            self.assertEqual(pages[2].text, "Readable")

    def test_password_protected_pdf_fails_clearly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "encrypted.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            writer.encrypt("secret")
            with path.open("wb") as output:
                writer.write(output)
            with self.assertRaisesRegex(ValueError, "requires a password"):
                load_pdf(path, "sample", "fixture.pdf")

    def test_invalid_pdf_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid.pdf"
            path.write_bytes(b"This is not a PDF")
            with self.assertRaises(PdfReadError):
                load_pdf(path, "sample", "fixture.pdf")


if __name__ == "__main__":
    unittest.main()
