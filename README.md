# LectureLens AI

LectureLens AI is an NLP-based lecture summarization, study-notes, and quiz-generation application.

## Current application status

Phase 2 implements the two supported lecture input methods:

1. A YouTube video URL, using an accessible transcript or captions.
2. A PDF upload, with text extracted from the PDF.

PDF text extraction uses PyMuPDF. Scanned or image-only PDFs are reported as
unextractable; OCR is not implemented. YouTube captions are retrieved through
`youtube-transcript-api` when the video provides accessible captions. The video
itself is never downloaded. Summarization uses the local `google-t5/t5-small`
Transformer model on CPU; its weights are downloaded on the first summary
request and cached locally.

## Windows setup

From the repository directory, create the virtual environment with Python 3.12:

```powershell
py -3.12 -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the declared dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Verify the environment:

```powershell
python --version
python -m pip --version
python -c "import pymupdf, nltk, streamlit, youtube_transcript_api; print('imports ok')"
```

Run the application:

```powershell
streamlit run app.py
```

Run the input tests without requiring a separate test runner:

```powershell
python -m unittest discover -s tests -v
```

The Streamlit application provides local summarization, source-grounded study
notes, ranked keywords, a glossary, validated quiz generation, interactive
answer checking, scoring, and revision recommendations. Glossary entries that
lack an explicit definition in the lecture are marked as needing verification.

The quiz generator uses explicit lecture definitions rather than a second large
question-generation model, so short lectures may produce fewer questions than
requested when there is not enough source-supported material. Unanswered
questions are counted as incorrect, and malformed questions are excluded from
the denominator. Interactive scoring and revision recommendations are included.
File export remains intentionally unavailable.
