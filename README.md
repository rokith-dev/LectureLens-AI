# LectureLens AI

LectureLens AI is an NLP-based lecture summarization, study-notes, and quiz-generation application.

## Phase 2 status

Phase 2 implements the two supported lecture input methods:

1. A YouTube video URL, using an accessible transcript or captions.
2. A PDF upload, with text extracted from the PDF.

PDF text extraction uses PyMuPDF. Scanned or image-only PDFs are reported as
unextractable; OCR is not implemented. YouTube captions are retrieved through
`youtube-transcript-api` when the video provides accessible captions. The video
itself is never downloaded.

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

Summarization, study notes, quizzes, glossaries, and other NLP features are
intentionally deferred to Phase 3.
