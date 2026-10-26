from dataclasses import dataclass
import re

from .study_materials import GlossaryEntry, Keyword


class QuizGenerationError(ValueError):
    """Raised when lecture content cannot produce a validated quiz."""


@dataclass(frozen=True)
class QuizQuestion:
    question: str
    options: tuple[str, str, str, str]
    correct_index: int
    explanation: str
    source_passage: str


@dataclass(frozen=True)
class QuizResult:
    requested_count: int
    questions: tuple[QuizQuestion, ...]


def generate_quiz(
    text: str,
    question_count: int,
    glossary: tuple[GlossaryEntry, ...] = (),
    keywords: tuple[Keyword, ...] = (),
) -> QuizResult:
    """Generate validated definition-based MCQs from explicit lecture content."""
    if not isinstance(text, str) or not text.strip():
        raise QuizGenerationError("Lecture text is empty; provide readable lecture content.")
    if question_count not in {5, 10, 15}:
        raise QuizGenerationError("Choose 5, 10, or 15 questions.")

    definitions = [
        entry for entry in glossary
        if not entry.needs_verification and entry.definition.strip()
    ]
    terms = _unique_terms(definitions, keywords)
    if len(terms) < 4:
        raise QuizGenerationError(
            "The lecture does not contain at least four distinct supported concepts "
            "to build validated multiple-choice questions."
        )

    questions: list[QuizQuestion] = []
    seen_questions: set[str] = set()
    for entry in definitions:
        if len(questions) >= question_count:
            break
        question = _build_question(entry, terms)
        normalized = _normalize(question.question)
        if normalized in seen_questions or not _validate_question(question, text):
            continue
        seen_questions.add(normalized)
        questions.append(question)

    if not questions:
        raise QuizGenerationError(
            "No questions could be validated from the lecture's explicit definitions."
        )
    return QuizResult(requested_count=question_count, questions=tuple(questions))


def _build_question(
    entry: GlossaryEntry,
    terms: list[GlossaryEntry],
) -> QuizQuestion:
    distractors = [item.term for item in terms if item.term.lower() != entry.term.lower()][:3]
    options = (entry.term, *distractors)
    return QuizQuestion(
        question=f"Which term is defined by this lecture passage: \"{entry.definition}\"",
        options=options,
        correct_index=0,
        explanation=f"The passage explicitly defines {entry.term}.",
        source_passage=entry.definition,
    )


def _validate_question(question: QuizQuestion, source_text: str) -> bool:
    if len(question.options) != 4 or len(set(option.lower() for option in question.options)) != 4:
        return False
    if question.correct_index not in range(4):
        return False
    if not question.source_passage.strip() or question.source_passage not in source_text:
        return False
    return bool(question.options[question.correct_index].strip())


def _unique_terms(
    definitions: list[GlossaryEntry],
    keywords: tuple[Keyword, ...],
) -> list[GlossaryEntry]:
    result: list[GlossaryEntry] = []
    seen: set[str] = set()
    for entry in (*definitions, *(GlossaryEntry(keyword.phrase, "", True) for keyword in keywords)):
        normalized = entry.term.lower().strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(entry)
    return result


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())
