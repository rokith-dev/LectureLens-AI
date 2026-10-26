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


@dataclass(frozen=True)
class QuizScore:
    correct_count: int
    valid_question_count: int
    percentage: float
    answered_count: int


@dataclass(frozen=True)
class RevisionRecommendation:
    question: str
    correct_answer: str
    explanation: str
    source_passage: str


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


def score_quiz(
    quiz: QuizResult,
    answers: dict[int, int | None],
) -> QuizScore:
    """Score only structurally valid questions; unanswered answers count wrong."""
    correct_count = 0
    answered_count = 0
    valid_count = 0
    for index, question in enumerate(quiz.questions):
        if not _is_valid_question(question):
            continue
        valid_count += 1
        answer = answers.get(index)
        if answer is not None:
            answered_count += 1
        if answer == question.correct_index:
            correct_count += 1

    percentage = round((correct_count / valid_count) * 100, 2) if valid_count else 0.0
    return QuizScore(
        correct_count=correct_count,
        valid_question_count=valid_count,
        percentage=percentage,
        answered_count=answered_count,
    )


def revision_recommendations(
    quiz: QuizResult,
    answers: dict[int, int | None],
) -> tuple[RevisionRecommendation, ...]:
    """Return lecture-grounded recommendations for valid incorrect answers."""
    recommendations = []
    for index, question in enumerate(quiz.questions):
        if not _is_valid_question(question):
            continue
        if answers.get(index) == question.correct_index:
            continue
        recommendations.append(
            RevisionRecommendation(
                question=question.question,
                correct_answer=question.options[question.correct_index],
                explanation=question.explanation,
                source_passage=question.source_passage,
            )
        )
    return tuple(recommendations)


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
    return _is_valid_question(question) and question.source_passage in source_text


def _is_valid_question(question: QuizQuestion) -> bool:
    if not isinstance(question, QuizQuestion):
        return False
    if not question.question.strip() or not question.explanation.strip():
        return False
    if len(question.options) != 4:
        return False
    if any(not isinstance(option, str) or not option.strip() for option in question.options):
        return False
    if len(set(option.casefold().strip() for option in question.options)) != 4:
        return False
    if question.correct_index not in range(4):
        return False
    return bool(question.source_passage.strip())


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
