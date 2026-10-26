# LectureLens AI

LectureLens AI is an NLP-based lecture summarization, study-notes, and quiz-generation application.

## Phase 1 status

Phase 1 prepares the Windows development environment only. Application features and UI flows are intentionally not implemented yet.

The planned application will support exactly these input methods:

1. A YouTube video URL, using an accessible transcript or captions.
2. A PDF upload, with text extracted from the PDF.

Pretrained NLP models are not downloaded during environment setup.

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
python -c "import nltk, pypdf, streamlit, youtube_transcript_api; print('imports ok')"
```

No application entry point exists yet. Phase 2 can add the Streamlit application after this setup is reviewed.
