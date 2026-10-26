from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from .quiz import QuizQuestion, QuizResult, _is_valid_question
from .study_materials import (
    GlossaryEntry,
    Keyword,
    StudyNotes,
    normalize_lecture_text,
)
from .summarizer import SummaryResult


load_dotenv()


class GroqConfigurationError(RuntimeError):
    """Raised when Groq is not configured or the selected model is unavailable."""


class GroqGenerationError(RuntimeError):
    """Raised when Groq cannot generate or validate lecture materials."""


@dataclass(frozen=True)
class GroqAnalysis:
    summaries: SummaryResult
    notes: StudyNotes
    keywords: tuple[Keyword, ...]
    glossary: tuple[GlossaryEntry, ...]


class GroqLectureGenerator:
    """Generate validated lecture materials through the official Groq SDK."""

    def __init__(
        self,
        client: Any | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GROQ_API_KEY", "").strip()
        self.model = model if model is not None else os.getenv("GROQ_MODEL", "").strip()
        if client is not None:
            self.client = client
        elif self.api_key:
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None

    def validate_configuration(self) -> None:
        if not self.api_key or self.client is None:
            raise GroqConfigurationError(
                "GROQ_API_KEY is missing. Add it to .env before generating materials."
            )
        if not self.model:
            raise GroqConfigurationError(
                "GROQ_MODEL is missing. Set it to a model available in your Groq account."
            )
        try:
            models = self.client.models.list()
            available = {getattr(item, "id", "") for item in getattr(models, "data", ())}
        except Exception as error:
            raise GroqConfigurationError(
                "Groq model availability could not be checked. Verify the API key and network connection."
            ) from error
        if not available or self.model not in available:
            raise GroqConfigurationError(
                f"The configured Groq model '{self.model}' is not available for this account."
            )

    def generate_analysis(self, text: str) -> GroqAnalysis:
        source = _validated_source(text)
        self.validate_configuration()
        responses = [
            self._request_json(_analysis_prompt(chunk), "lecture analysis")
            for chunk in _chunks(source)
        ]
        return _merge_analysis(responses, len(responses))

    def generate_quiz(
        self,
        text: str,
        question_count: int,
    ) -> QuizResult:
        source = _validated_source(text)
        if question_count not in {5, 10, 15}:
            raise GroqGenerationError("Choose 5, 10, or 15 questions.")
        self.validate_configuration()
        questions: list[QuizQuestion] = []
        seen: set[str] = set()
        for chunk in _chunks(source):
            payload = self._request_json(
                _quiz_prompt(chunk, question_count),
                "quiz generation",
            )
            for item in payload.get("questions", []):
                question = _question_from_payload(item)
                if question is None or not _is_valid_question(question):
                    continue
                if question.source_passage not in source:
                    continue
                key = re.sub(r"\W+", " ", question.question.casefold()).strip()
                if key in seen:
                    continue
                seen.add(key)
                questions.append(question)
                if len(questions) >= question_count:
                    break
            if len(questions) >= question_count:
                break
        if not questions:
            raise GroqGenerationError(
                "Groq returned no source-supported, valid quiz questions for this lecture."
            )
        return QuizResult(requested_count=question_count, questions=tuple(questions))

    def _request_json(self, prompt: str, operation: str) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a careful lecture-learning assistant. Use only the supplied "
                            "lecture text and return valid JSON, never markdown."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
        except Exception as error:
            message = str(error).lower()
            if "rate" in message or "429" in message:
                detail = "Groq rate limit reached. Wait briefly and try again."
            elif "credit" in message or "billing" in message:
                detail = "Groq credits are insufficient for this request."
            elif "timeout" in message:
                detail = "Groq request timed out. Try a shorter lecture or try again."
            elif "401" in message or "authentication" in message or "api key" in message:
                detail = "Groq rejected the API key. Check GROQ_API_KEY in .env."
            else:
                detail = f"Groq {operation} failed. Check the API configuration and network connection."
            raise GroqGenerationError(detail) from error
        if not isinstance(content, str) or not content.strip():
            raise GroqGenerationError(f"Groq returned an empty response for {operation}.")
        try:
            parsed = json.loads(_strip_json_fence(content))
        except (json.JSONDecodeError, TypeError) as error:
            raise GroqGenerationError(
                f"Groq returned malformed JSON for {operation}; no results were displayed."
            ) from error
        if not isinstance(parsed, dict):
            raise GroqGenerationError(f"Groq returned an invalid object for {operation}.")
        return parsed


def _validated_source(text: str) -> str:
    if not isinstance(text, str):
        raise GroqGenerationError("Lecture text must be a string.")
    source = normalize_lecture_text(text)
    if len(source.split()) < 8:
        raise GroqGenerationError(
            "The lecture text is empty or too short to generate reliable study materials."
        )
    return source


def _chunks(text: str, max_characters: int = 12000) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        if current and length + len(word) + 1 > max_characters:
            chunks.append(" ".join(current))
            current = []
            length = 0
        current.append(word)
        length += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def _analysis_prompt(source: str) -> str:
    return f"""Create grounded study materials from this lecture text.
Return JSON with exactly these keys:
short_summary (string), detailed_summary (string), headings (array of strings),
important_concepts (array of strings), bullet_points (array of strings),
supported_definitions (array of objects with term, definition, needs_verification),
examples (array of strings), key_takeaways (array of strings), keywords
(array of objects with phrase and score), glossary (array of objects with term,
definition, needs_verification).
Do not invent facts. Mark unsupported definitions with needs_verification true.
Keep keywords concise and non-repetitive.

LECTURE:
{source}"""


def _quiz_prompt(source: str, count: int) -> str:
    return f"""Create up to {count} source-grounded multiple-choice questions.
Return JSON with a single key questions containing objects with:
question (concise question, never a full paragraph), options (exactly four
distinct strings), correct_index (integer 0-3), explanation (string), and
source_passage (an exact passage copied from the lecture).
Use only information explicitly supported by the lecture. Avoid ambiguity and
duplicate questions. If fewer reliable questions are possible, return fewer.

LECTURE:
{source}"""


def _strip_json_fence(content: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)


def _question_from_payload(item: Any) -> QuizQuestion | None:
    if not isinstance(item, dict):
        return None
    try:
        options = tuple(item["options"])
        if len(options) != 4:
            return None
        return QuizQuestion(
            question=str(item["question"]).strip(),
            options=options,  # type: ignore[arg-type]
            correct_index=int(item["correct_index"]),
            explanation=str(item["explanation"]).strip(),
            source_passage=str(item["source_passage"]).strip(),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _merge_analysis(responses: list[dict[str, Any]], chunk_count: int) -> GroqAnalysis:
    def strings(key: str) -> tuple[str, ...]:
        values = (item for response in responses for item in response.get(key, []))
        return tuple(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))

    summaries = SummaryResult(
        short=str(responses[0].get("short_summary", "")).strip(),
        detailed=str(responses[0].get("detailed_summary", "")).strip(),
        chunk_count=chunk_count,
    )
    if not summaries.short or not summaries.detailed:
        raise GroqGenerationError("Groq returned incomplete summaries.")

    keyword_items = (item for response in responses for item in response.get("keywords", []))
    keywords = tuple(
        Keyword(str(item["phrase"]).strip(), float(item["score"]))
        for item in keyword_items
        if isinstance(item, dict) and item.get("phrase") and _number(item.get("score"))
    )
    glossary = _entries(responses, "glossary")
    definitions = _entries(responses, "supported_definitions")
    notes = StudyNotes(
        overview=summaries.detailed,
        headings=strings("headings"),
        important_concepts=strings("important_concepts"),
        bullet_points=strings("bullet_points"),
        supported_definitions=definitions,
        examples=strings("examples"),
        key_takeaways=strings("key_takeaways"),
    )
    return GroqAnalysis(summaries, notes, keywords, glossary)


def _entries(responses: list[dict[str, Any]], key: str) -> tuple[GlossaryEntry, ...]:
    result: list[GlossaryEntry] = []
    seen: set[str] = set()
    for response in responses:
        for item in response.get(key, []):
            if not isinstance(item, dict):
                continue
            term = str(item.get("term", "")).strip()
            definition = str(item.get("definition", "")).strip()
            normalized = term.casefold()
            if term and definition and normalized not in seen:
                seen.add(normalized)
                result.append(GlossaryEntry(term, definition, bool(item.get("needs_verification"))))
    return tuple(result)


def _number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True
