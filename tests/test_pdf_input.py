import unittest

import pymupdf as fitz

from lecturelens.pdf_input import PdfInputError, extract_pdf_text


def make_pdf(*page_texts: str) -> bytes:
    document = fitz.open()
    for page_text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), page_text)
    data = document.tobytes()
    document.close()
    return data


class PdfInputTests(unittest.TestCase):
    def test_extracts_text_page_by_page_and_reports_page_count(self) -> None:
        result = extract_pdf_text(make_pdf("First page", "Second page"), "lecture.pdf")

        self.assertEqual(result.source_type, "pdf")
        self.assertIn("First page", result.text)
        self.assertIn("Second page", result.text)
        self.assertEqual(result.metadata["page_count"], 2)

    def test_rejects_invalid_pdf(self) -> None:
        with self.assertRaisesRegex(PdfInputError, "readable PDF"):
            extract_pdf_text(b"not a pdf", "lecture.pdf")

    def test_reports_scanned_or_empty_pdf_without_claiming_ocr(self) -> None:
        empty_pdf = fitz.open()
        empty_pdf.new_page()
        data = empty_pdf.tobytes()
        empty_pdf.close()

        with self.assertRaisesRegex(PdfInputError, "OCR is not implemented"):
            extract_pdf_text(data, "scanned.pdf")
