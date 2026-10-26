from collections.abc import Callable
from urllib.parse import parse_qs, urlparse

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
) -> LectureText:
    """Fetch an accessible transcript without downloading the video."""
    video_id = extract_video_id(url)
    fetcher = transcript_fetcher or _fetch_transcript

    try:
        transcript = fetcher(video_id)
    except (IpBlocked, RequestBlocked) as error:
        raise YouTubeInputError(
            "YouTube blocked transcript requests from this network or IP. "
            "Try again later or paste the transcript manually."
        ) from error
    except (YouTubeRequestFailed, OSError) as error:
        raise YouTubeInputError(
            "YouTube could not be reached while retrieving captions. "
            "Check the network connection and try again."
        ) from error
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
        raise YouTubeInputError(_transcript_error_message(error)) from error
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
