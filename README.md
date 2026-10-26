# LectureLens AI

LectureLens AI is an NLP-based lecture summarization, study-notes, and quiz-generation application.

## Current application status

Phase 2 implements the two supported lecture input methods:

1. A YouTube video URL, using an accessible transcript or captions.
2. A PDF upload, with text extracted from the PDF.

PDF text extraction uses PyMuPDF. Scanned or image-only PDFs are reported as
unextractable; OCR is not implemented. YouTube captions are retrieved through
`youtube-transcript-api` when the video provides accessible captions. The video
itself is never downloaded. Summaries, study notes, keywords, glossary entries, and quiz questions are
generated through the Groq API. The configured model is read from
`GROQ_MODEL`, and the application verifies that it is available to the
configured account before making a request. The API key is loaded from
`GROQ_API_KEY` in a local `.env` file and is never displayed or committed.
Copy `.env.example` to `.env` and set the Groq values plus
`SUPADATA_API_KEY` before using automatic YouTube processing. Supadata accepts
the YouTube URL, retrieves native captions when available, and can generate a
transcript with speech-to-text when captions are unavailable. Set
`SUPADATA_BASE_URL` only when using a compatible endpoint or mock service.
Long lectures are processed in bounded chunks. Groq responses must be valid
JSON and source-grounded; malformed or unsupported results are rejected.

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
python -c "import groq, pymupdf, nltk, streamlit, youtube_transcript_api; print('imports ok')"
```

Run the application:

```powershell
streamlit run app.py
```

Run the input tests without requiring a separate test runner:

```powershell
python -m unittest discover -s tests -v
```

The Streamlit application provides Groq-backed summaries, source-grounded study
notes, ranked keywords, a glossary, validated quiz generation, interactive
answer checking, scoring, and revision recommendations. Glossary entries that
lack an explicit definition in the lecture are marked as needing verification.

The quiz generator asks Groq for concise, source-grounded questions and rejects
duplicate, ambiguous, malformed, or unsupported questions. Short lectures may
produce fewer questions than requested when there is not enough reliable source
material. Unanswered questions are counted as incorrect, and malformed
questions are excluded from the denominator. Interactive scoring and revision
recommendations are included.
File export remains intentionally unavailable.

### Automatic YouTube transcripts

The app first attempts the installed YouTube transcript library. If YouTube
blocks the request or captions are unavailable, it uses Supadata when
`SUPADATA_API_KEY` is configured:

```env
SUPADATA_API_KEY=your_supadata_api_key_here
SUPADATA_BASE_URL=https://api.supadata.ai/v1
```

Start the app with `streamlit run app.py`, choose **YouTube URL**, paste a
standard YouTube URL, and wait while the transcript and Groq study materials
are generated. If the provider is not configured, the app reports the exact
setup requirement; the optional manual transcript area remains available.
