from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


MODEL_NAME = "google-t5/t5-small"


class SummarizationError(RuntimeError):
    """Raised when lecture text cannot be summarized."""


@dataclass(frozen=True)
class SummaryResult:
    short: str
    detailed: str
    chunk_count: int


class LectureSummarizer:
    """CPU-friendly Transformer summarizer with token-aware chunking."""

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        model_loader: Callable[[str], tuple[Any, Any]] | None = None,
        max_input_tokens: int = 448,
    ) -> None:
        if max_input_tokens < 32:
            raise ValueError("max_input_tokens must be at least 32.")
        self.model_name = model_name
        self._model_loader = model_loader or self._load_model
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self.max_input_tokens = max_input_tokens

    def summarize(self, text: str) -> SummaryResult:
        normalized_text = text.strip()
        if not normalized_text:
            raise SummarizationError(
                "Lecture text is empty; provide a PDF or transcript with readable text."
            )

        self._ensure_model()
        chunks = self._split_into_chunks(normalized_text)
        if not chunks:
            raise SummarizationError("Lecture text could not be split into summarizable chunks.")

        try:
            chunk_summaries = [
                self._generate(chunk, max_length=180, min_length=30)
                for chunk in chunks
            ]
            combined = " ".join(chunk_summaries).strip()
            detailed = self._summarize_combined(combined, max_length=220, min_length=60)
            short = self._summarize_combined(combined, max_length=90, min_length=20)
        except SummarizationError:
            raise
        except (RuntimeError, ValueError, TypeError) as error:
            raise SummarizationError(
                "The summarization model could not process this lecture text."
            ) from error

        return SummaryResult(short=short, detailed=detailed, chunk_count=len(chunks))

    def _ensure_model(self) -> None:
        if self._tokenizer is not None and self._model is not None:
            return
        try:
            self._tokenizer, self._model = self._model_loader(self.model_name)
            self._model.eval()
        except (OSError, RuntimeError, ValueError, ImportError) as error:
            raise SummarizationError(
                f"The summarization model could not be loaded. "
                f"Check the model download and available memory. Details: {error}"
            ) from error

    @staticmethod
    def _load_model(model_name: str) -> tuple[Any, Any]:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        return tokenizer, model

    def _split_into_chunks(self, text: str) -> list[str]:
        token_ids = self._tokenizer.encode(text, add_special_tokens=False)
        return [
            self._tokenizer.decode(
                token_ids[start : start + self.max_input_tokens],
                skip_special_tokens=True,
            )
            for start in range(0, len(token_ids), self.max_input_tokens)
        ]

    def _summarize_combined(self, text: str, max_length: int, min_length: int) -> str:
        combined_tokens = self._tokenizer.encode(text, add_special_tokens=False)
        if len(combined_tokens) <= self.max_input_tokens:
            return self._generate(text, max_length=max_length, min_length=min_length)

        intermediate = self._split_into_chunks(text)
        summaries = [
            self._generate(chunk, max_length=max_length, min_length=min_length)
            for chunk in intermediate
        ]
        return self._generate(" ".join(summaries), max_length=max_length, min_length=min_length)

    def _generate(self, text: str, max_length: int, min_length: int) -> str:
        inputs = self._tokenizer(
            f"summarize: {text}",
            return_tensors="pt",
            truncation=False,
            padding=True,
        )
        with torch.no_grad():
            output_ids = self._model.generate(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                max_length=max_length,
                min_length=min_length,
                num_beams=4,
                early_stopping=True,
            )
        result = self._tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        if not result:
            raise SummarizationError("The summarization model returned no text.")
        return result
