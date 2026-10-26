from collections.abc import Callable
import os
import time
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeDataUnparsable,
    YouTubeRequestFailed,
    YouTubeTranscriptApiException,
)

from .models import LectureText
from .study_materials import normalize_lecture_text

DEFAULT_SUPADATA_BASE_URL = "https://api.supadata.ai/v1"
load_dotenv(override=True)


class YouTubeInputError(ValueError):
    """Raised when a YouTube URL or transcript is unavailable."""


def extract_video_id(url: str) -> str:
    """Return a YouTube video ID from a supported canonical URL shape."""
    try:
        parsed = urlparse(url.strip())
    except ValueError as error:
        raise YouTubeInputError("Enter a valid YouTube video URL.") from error

    hostname = (parsed.hostname or "").lower().removeprefix("www.")
    if hostname in {"youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith(("/embed/", "/shorts/", "/live/")):
            video_id = parsed.path.split("/", 2)[2].split("/")[0]
        else:
            video_id = None
    elif hostname == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    else:
        video_id = None

    if not video_id or len(video_id) != 11 or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for character in video_id
    ):
        raise YouTubeInputError("Enter a valid YouTube video URL.")
    return video_id


def fetch_youtube_transcript(
    url: str,
    transcript_fetcher: Callable[[str], object] | None = None,
    provider_fetcher: Callable[[str, str], str] | None = None,
) -> LectureText:
    """Fetch a transcript directly, then use the configured hosted provider."""
    video_id = extract_video_id(url)
    fetcher = transcript_fetcher or _fetch_transcript

    try:
        transcript = fetcher(video_id)
    except (IpBlocked, RequestBlocked) as error:
        return _fetch_from_configured_provider(url, error, provider_fetcher)
    except (YouTubeRequestFailed, OSError) as error:
        return _fetch_from_configured_provider(url, error, provider_fetcher)
    except YouTubeDataUnparsable as error:
        raise YouTubeInputError(
            "YouTube returned a transcript response that could not be parsed."
        ) from error
    except (InvalidVideoId, VideoUnplayable) as error:
        raise YouTubeInputError(
            "YouTube rejected this video ID or the video cannot be played."
        ) from error
    except (
        AgeRestricted,
        CouldNotRetrieveTranscript,
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    ) as error:
        return _fetch_from_configured_provider(url, error, provider_fetcher)
    except YouTubeTranscriptApiException as error:
        raise YouTubeInputError(
            f"The YouTube transcript service returned {type(error).__name__}. "
            "No transcript was retrieved."
        ) from error
    except (TypeError, AttributeError, KeyError) as error:
        raise YouTubeInputError(
            "The YouTube transcript response had an unexpected format."
        ) from error

    snippets = getattr(transcript, "snippets", transcript)
    text_parts = []
    for snippet in snippets:
        text = snippet.get("text") if isinstance(snippet, dict) else getattr(snippet, "text", None)
        if text:
            text_parts.append(str(text).strip())
    text = "\n".join(part for part in text_parts if part)
    text = normalize_lecture_text(text)
    if not text:
        raise YouTubeInputError("The available transcript contains no readable text.")

    return LectureText(
        source_type="youtube",
        text=text,
        title=f"YouTube video {video_id}",
        metadata={"video_id": video_id, "url": url.strip()},
    )


def create_manual_youtube_lecture(
    text: str,
    source_url: str = "",
) -> LectureText:
    """Create the same normalized lecture result from user-supplied captions."""
    normalized_text = normalize_lecture_text(text)
    if not normalized_text:
        raise YouTubeInputError(
            "The pasted YouTube transcript is empty. Paste readable captions and try again."
        )
    return LectureText(
        source_type="youtube",
        text=normalized_text,
        title="Pasted YouTube transcript",
        metadata={"url": source_url.strip(), "input_method": "manual transcript"},
    )


def _fetch_from_configured_provider(
    url: str,
    direct_error: Exception,
    provider_fetcher: Callable[[str, str], str] | None,
) -> LectureText:
    api_key = os.getenv("SUPADATA_API_KEY", "").strip()
    if not api_key and provider_fetcher is None:
        raise YouTubeInputError(
            f"{_direct_error_message(direct_error)} Configure SUPADATA_API_KEY "
            "in .env for automatic hosted transcript retrieval."
        ) from direct_error
    try:
        text = provider_fetcher(url, api_key) if provider_fetcher else _fetch_supadata_transcript(url, api_key)
    except YouTubeInputError:
        raise
    except requests.RequestException as error:
        raise YouTubeInputError(
            "The hosted transcript provider could not be reached. Check the network and try again."
        ) from error
    except (TypeError, KeyError, ValueError) as error:
        raise YouTubeInputError(
            "The hosted transcript provider returned an invalid response."
        ) from error
    normalized_text = normalize_lecture_text(text)
    if not normalized_text:
        raise YouTubeInputError(
            "The hosted transcript provider returned no readable speech."
        ) from direct_error
    video_id = extract_video_id(url)
    return LectureText(
        source_type="youtube",
        text=normalized_text,
        title=f"YouTube video {video_id}",
        metadata={"video_id": video_id, "url": url.strip(), "transcript_provider": "supadata"},
    )


def _fetch_supadata_transcript(url: str, api_key: str) -> str:
    base_url = os.getenv("SUPADATA_BASE_URL", DEFAULT_SUPADATA_BASE_URL).strip().rstrip("/")
    response = requests.get(
        f"{base_url}/transcript",
        params={"url": url, "text": "true", "mode": "auto"},
        headers={"x-api-key": api_key},
        timeout=30,
    )
    if response.status_code == 401 or response.status_code == 403:
        raise YouTubeInputError(
            "The hosted transcript provider rejected SUPADATA_API_KEY. Check .env."
        )
    if response.status_code == 404:
        raise YouTubeInputError(
            "The hosted transcript provider could not find this YouTube video."
        )
    if response.status_code == 429:
        raise YouTubeInputError(
            "The hosted transcript provider rate limit was reached. Try again later."
        )
    if response.status_code >= 400:
        raise YouTubeInputError(
            f"The hosted transcript provider returned HTTP {response.status_code}."
        )
    payload = response.json()
    if response.status_code == 202 or payload.get("jobId"):
        job_id = payload.get("jobId")
        if not job_id:
            raise YouTubeInputError("The hosted transcript provider returned no job ID.")
        return _poll_supadata_job(base_url, job_id, api_key)
    return _provider_content(payload)


def _poll_supadata_job(base_url: str, job_id: str, api_key: str) -> str:
    for _ in range(60):
        response = requests.get(
            f"{base_url}/transcript/{job_id}",
            headers={"x-api-key": api_key},
            timeout=30,
        )
        if response.status_code == 401 or response.status_code == 403:
            raise YouTubeInputError("The hosted transcript provider rejected SUPADATA_API_KEY.")
        if response.status_code == 429:
            raise YouTubeInputError("The hosted transcript provider rate limit was reached.")
        if response.status_code >= 400:
            raise YouTubeInputError(
                f"The hosted transcript job returned HTTP {response.status_code}."
            )
        payload = response.json()
        status = payload.get("status")
        if status == "completed":
            return _provider_content(payload)
        if status == "failed":
            raise YouTubeInputError(
                "The hosted provider could not generate a transcript for this video."
            )
        time.sleep(1)
    raise YouTubeInputError(
        "The hosted transcript provider timed out while generating captions."
    )


def _provider_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise ValueError("provider payload must be an object")
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", "")).strip()
            for item in content
            if isinstance(item, dict) and item.get("text")
        )
    raise ValueError("provider content is missing")


def _direct_error_message(error: Exception) -> str:
    if isinstance(error, (IpBlocked, RequestBlocked)):
        return "YouTube blocked transcript requests from this network or IP."
    if isinstance(error, (YouTubeRequestFailed, OSError)):
        return "YouTube could not be reached while retrieving captions."
    return _transcript_error_message(error)


def _fetch_transcript(video_id: str) -> object:
    api = YouTubeTranscriptApi()
    transcripts = api.list(video_id)
    try:
        transcript = transcripts.find_transcript(("en", "en-US", "en-GB"))
    except NoTranscriptFound:
        transcript = next(iter(transcripts), None)
    if transcript is None:
        raise NoTranscriptFound(video_id, (), transcripts)
    return transcript.fetch()


def _transcript_error_message(error: Exception) -> str:
    if isinstance(error, TranscriptsDisabled):
        return "Captions are disabled for this YouTube video."
    if isinstance(error, NoTranscriptFound):
        return "No accessible transcript or captions were found for this video."
    if isinstance(error, VideoUnavailable):
        return "This YouTube video is unavailable."
    if isinstance(error, AgeRestricted):
        return "This age-restricted YouTube video cannot be accessed."
    return "The YouTube transcript could not be retrieved."
