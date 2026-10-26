from io import BytesIO

import pymupdf as fitz

from .models import LectureText


class PdfInputError(ValueError):
    """Raised when a PDF cannot be read or contains no extractable text."""


def extract_pdf_text(file_data: bytes, filename: str) -> LectureText:
    """Extract readable text from every page of a PDF upload."""
    if not filename.lower().endswith(".pdf"):
        raise PdfInputError("Please upload a file with a .pdf extension.")
    if not file_data:
        raise PdfInputError("The uploaded PDF is empty.")

    try:
        document = fitz.open(stream=BytesIO(file_data), filetype="pdf")
    except (fitz.FileDataError, RuntimeError) as error:
        raise PdfInputError("The uploaded file is not a readable PDF.") from error

    try:
        pages = [page.get_text("text").strip() for page in document]
        text = "\n\n".join(page for page in pages if page)
        page_count = len(document)
    finally:
        document.close()

    if not text:
        raise PdfInputError(
            "This PDF contains no extractable text. It may be scanned or image-only; "
            "OCR is not implemented."
        )

    return LectureText(
        source_type="pdf",
        text=text,
        title=filename,
        metadata={"filename": filename, "page_count": page_count},
    )
