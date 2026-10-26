import unittest

import pymupdf

from lecturelens.pdf_input import extract_pdf_text
from lecturelens.summarizer import LectureSummarizer, SummarizationError
from lecturelens.youtube_input import fetch_youtube_transcript


class FakeTokenizer:
    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        return list(range(len(text.split())))

    def decode(self, token_ids: list[int], skip_special_tokens: bool = True) -> str:
        return " ".join(f"token-{token_id}" for token_id in token_ids)

    def __call__(self, text: str, **_: object) -> dict[str, list[list[int]]]:
        token_count = max(1, len(text.split()))
        return {"input_ids": [[token_count]], "attention_mask": [[1]]}


class FakeModel:
    def eval(self) -> None:
        return None

    def generate(self, **_: object) -> list[list[int]]:
        return [[1, 2, 3]]


def fake_loader(_: str) -> tuple[FakeTokenizer, FakeModel]:
    return FakeTokenizer(), FakeModel()


class SummarizerTests(unittest.TestCase):
    def test_rejects_empty_text(self) -> None:
        summarizer = LectureSummarizer(model_loader=fake_loader)

        with self.assertRaisesRegex(SummarizationError, "empty"):
            summarizer.summarize("  ")

    def test_summarizes_short_text_with_mocked_model(self) -> None:
        summarizer = LectureSummarizer(model_loader=fake_loader)

        result = summarizer.summarize("A short lecture about effective study habits.")

        self.assertEqual(result.short, "token-1 token-2 token-3")
        self.assertEqual(result.detailed, "token-1 token-2 token-3")
        self.assertEqual(result.chunk_count, 1)

    def test_chunks_long_text_without_truncating(self) -> None:
        summarizer = LectureSummarizer(model_loader=fake_loader, max_input_tokens=32)
        text = " ".join(f"word-{index}" for index in range(75))

        result = summarizer.summarize(text)

        self.assertGreater(result.chunk_count, 1)

    def test_reports_model_loading_failure(self) -> None:
        def failing_loader(_: str) -> tuple[object, object]:
            raise OSError("model files unavailable")

        summarizer = LectureSummarizer(model_loader=failing_loader)

        with self.assertRaisesRegex(SummarizationError, "could not be loaded"):
            summarizer.summarize("A lecture text.")

    def test_reports_inference_failure(self) -> None:
        class FailingModel(FakeModel):
            def generate(self, **_: object) -> list[list[int]]:
                raise RuntimeError("out of memory")

        summarizer = LectureSummarizer(
            model_loader=lambda _: (FakeTokenizer(), FailingModel())
        )

        with self.assertRaisesRegex(SummarizationError, "could not process"):
            summarizer.summarize("A lecture text.")

    def test_pdf_and_youtube_results_share_summarization_input(self) -> None:
        summarizer = LectureSummarizer(model_loader=fake_loader)
        document = pymupdf.open()
        page = document.new_page()
        page.insert_text((72, 72), "Text extracted from a PDF lecture.")
        pdf_bytes = document.tobytes()
        document.close()
        pdf_lecture = extract_pdf_text(pdf_bytes, "lecture.pdf")
        youtube_lecture = fetch_youtube_transcript(
            "https://youtu.be/dQw4w9WgXcQ",
            transcript_fetcher=lambda _: [{"text": "Transcript text retrieved from YouTube."}],
        )

        for lecture in (pdf_lecture, youtube_lecture):
            with self.subTest(source=lecture.source_type):
                result = summarizer.summarize(lecture.text)
                self.assertTrue(result.short)
