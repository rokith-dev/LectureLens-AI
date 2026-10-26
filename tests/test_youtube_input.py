import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from youtube_transcript_api._errors import IpBlocked, NoTranscriptFound

from lecturelens.youtube_input import (
    YouTubeInputError,
    create_manual_youtube_lecture,
    extract_video_id,
    fetch_youtube_transcript,
)


class YouTubeInputTests(unittest.TestCase):
    def test_extracts_video_ids_from_supported_urls(self) -> None:
        expected = "dQw4w9WgXcQ"
        for url in (
            f"https://www.youtube.com/watch?v={expected}",
            f"https://www.youtube.com/watch?x=1&v={expected}&t=20",
            f"https://youtu.be/{expected}",
            f"https://youtu.be/{expected}?si=tracking&t=20",
            f"https://www.youtube.com/embed/{expected}",
            f"https://www.youtube.com/shorts/{expected}",
            f"https://www.youtube.com/shorts/{expected}?feature=share",
        ):
            self.assertEqual(extract_video_id(url), expected)

    def test_rejects_non_youtube_or_malformed_urls(self) -> None:
        for url in ("", "https://example.com/watch?v=dQw4w9WgXcQ", "not a url"):
            with self.subTest(url=url), self.assertRaises(YouTubeInputError):
                extract_video_id(url)

    def test_normalizes_mocked_transcript(self) -> None:
        def fetcher(video_id: str) -> object:
            self.assertEqual(video_id, "dQw4w9WgXcQ")
            return SimpleNamespace(
                snippets=[
                    SimpleNamespace(text="Opening sentence."),
                    SimpleNamespace(text="Key explanation."),
                ]
            )

        result = fetch_youtube_transcript(
            "https://youtu.be/dQw4w9WgXcQ",
            transcript_fetcher=fetcher,
        )

        self.assertEqual(result.metadata["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(result.text, "Opening sentence.\nKey explanation.")

    def test_reports_mocked_transcript_failure(self) -> None:
        def fetcher(_: str) -> object:
            raise OSError("network unavailable")

        with self.assertRaisesRegex(YouTubeInputError, "could not be reached"):
            fetch_youtube_transcript(
                "https://youtu.be/dQw4w9WgXcQ",
                transcript_fetcher=fetcher,
            )

    def test_reports_blocked_requests_separately(self) -> None:
        def fetcher(_: str) -> object:
            raise IpBlocked("blocked")

        with self.assertRaisesRegex(YouTubeInputError, "blocked transcript requests"):
            fetch_youtube_transcript(
                "https://youtu.be/dQw4w9WgXcQ",
                transcript_fetcher=fetcher,
            )

    def test_reports_missing_captions_separately(self) -> None:
        def fetcher(_: str) -> object:
            raise NoTranscriptFound("dQw4w9WgXcQ", (), [])

        with self.assertRaisesRegex(YouTubeInputError, "No accessible transcript"):
            fetch_youtube_transcript(
                "https://youtu.be/dQw4w9WgXcQ",
                transcript_fetcher=fetcher,
            )

    def test_rejects_empty_pasted_transcript(self) -> None:
        with self.assertRaisesRegex(YouTubeInputError, "pasted YouTube transcript is empty"):
            create_manual_youtube_lecture(" \n ")

    def test_normalizes_valid_pasted_transcript(self) -> None:
        result = create_manual_youtube_lecture(
            "Activation &amp; learning.\nActivation &amp; learning.",
            "https://youtu.be/dQw4w9WgXcQ",
        )

        self.assertEqual(result.source_type, "youtube")
        self.assertEqual(result.text, "Activation & learning.")
        self.assertEqual(result.metadata["input_method"], "manual transcript")
        self.assertEqual(result.metadata["url"], "https://youtu.be/dQw4w9WgXcQ")

    def test_pasted_text_can_be_passed_to_existing_generation_pipeline(self) -> None:
        lecture = create_manual_youtube_lecture(
            "Neural networks learn patterns from data. "
            "Activation functions transform model signals.",
        )
        generator = Mock()

        generator.generate_analysis(lecture.text)

        generator.generate_analysis.assert_called_once_with(lecture.text)
