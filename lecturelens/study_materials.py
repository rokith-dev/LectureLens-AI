from collections import Counter
from dataclasses import dataclass
import re


class StudyMaterialsError(ValueError):
    """Raised when source text is invalid for study-material generation."""


@dataclass(frozen=True)
class Keyword:
    phrase: str
    score: float


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    definition: str
    needs_verification: bool


@dataclass(frozen=True)
class StudyNotes:
    overview: str
    headings: tuple[str, ...]
    important_concepts: tuple[str, ...]
    bullet_points: tuple[str, ...]
    supported_definitions: tuple[GlossaryEntry, ...]
    examples: tuple[str, ...]
    key_takeaways: tuple[str, ...]


_STOPWORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been",
    "being", "between", "but", "can", "could", "does", "during", "each",
    "for", "from", "have", "into", "its", "more", "most", "not", "of",
    "on", "only", "other", "our", "over", "same", "should", "some",
    "such", "than", "that", "their", "there", "these", "they", "this",
    "through", "to", "under", "use", "used", "using", "was", "were",
    "what", "when", "where", "which", "who", "with", "would", "your",
}
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_DEFINITION_RE = re.compile(
    r"(?P<term>[A-Za-z][A-Za-z0-9 -]{1,60}?)\s+"
    r"(?:is|are|means|refers to|can be defined as)\s+"
    r"(?P<definition>[^.!?]+[.!?]?)",
    re.IGNORECASE,
)


def extract_keywords(text: str, limit: int = 12) -> tuple[Keyword, ...]:
    """Extract ranked unigrams and noun-like phrases without external models."""
    _validate_text(text)
    if limit < 1:
        raise ValueError("limit must be positive.")

    words = [word.lower() for word in _WORD_RE.findall(text)]
    candidates = [word for word in words if word not in _STOPWORDS]
    counts = Counter(candidates)
    phrases: Counter[str] = Counter()
    for index in range(len(words)):
        if words[index] in _STOPWORDS:
            continue
        phrases[words[index]] += 1
        if index + 1 < len(words) and words[index + 1] not in _STOPWORDS:
            phrases[f"{words[index]} {words[index + 1]}"] += 1

    ranked = sorted(
        phrases.items(),
        key=lambda item: (item[1] * (1 + item[0].count(" ")), len(item[0])),
        reverse=True,
    )
    results: list[Keyword] = []
    seen_stems: set[str] = set()
    maximum = ranked[0][1] if ranked else 1
    for phrase, count in ranked:
        stem = phrase.split()[0]
        if stem in seen_stems and " " not in phrase:
            continue
        seen_stems.add(stem)
        score = round((count / maximum) * (1 + 0.1 * phrase.count(" ")), 3)
        results.append(Keyword(phrase=phrase, score=score))
        if len(results) >= limit:
            break
    return tuple(results)


def generate_glossary(text: str, keywords: tuple[Keyword, ...] | None = None) -> tuple[GlossaryEntry, ...]:
    """Build glossary entries from explicit definitions or source context."""
    _validate_text(text)
    sentences = _sentences(text)
    explicit = _explicit_definitions(sentences)
    selected = keywords or extract_keywords(text, limit=12)
    entries: list[GlossaryEntry] = []
    seen: set[str] = set()
    for keyword in selected:
        term = keyword.phrase
        normalized_term = term.lower()
        if normalized_term in seen:
            continue
        seen.add(normalized_term)
        definition = explicit.get(normalized_term)
        if definition:
            entries.append(GlossaryEntry(term=term, definition=definition, needs_verification=False))
            continue
        context = next(
            (sentence for sentence in sentences if re.search(rf"\b{re.escape(term)}\b", sentence, re.IGNORECASE)),
            "",
        )
        if context:
            entries.append(
                GlossaryEntry(
                    term=term,
                    definition=context,
                    needs_verification=True,
                )
            )
    return tuple(entries)


def generate_study_notes(
    text: str,
    short_summary: str,
    detailed_summary: str,
) -> StudyNotes:
    """Create structured notes using only source sentences and supplied summaries."""
    _validate_text(text)
    if not short_summary.strip() or not detailed_summary.strip():
        raise StudyMaterialsError("Both short and detailed summaries are required.")

    sentences = _sentences(text)
    keywords = extract_keywords(text)
    glossary = generate_glossary(text, keywords)
    definition_terms = {entry.term.lower() for entry in glossary if not entry.needs_verification}
    examples = tuple(
        sentence for sentence in sentences
        if re.search(r"\b(for example|e\.g\.|such as|for instance)\b", sentence, re.IGNORECASE)
    )
    headings = tuple(_heading(sentence) for sentence in sentences[: min(3, len(sentences))])
    bullets = tuple(sentences[: min(8, len(sentences))])
    takeaways = tuple(dict.fromkeys((short_summary.strip(), *sentences[-2:])))[:3]
    return StudyNotes(
        overview=detailed_summary.strip(),
        headings=headings,
        important_concepts=tuple(keyword.phrase for keyword in keywords[:6]),
        bullet_points=bullets,
        supported_definitions=tuple(
            entry for entry in glossary if entry.term.lower() in definition_terms
        ),
        examples=examples,
        key_takeaways=takeaways,
    )


def _validate_text(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise StudyMaterialsError("Lecture text is empty; provide readable lecture content.")


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCE_RE.split(text) if sentence.strip()]


def _explicit_definitions(sentences: list[str]) -> dict[str, str]:
    definitions: dict[str, str] = {}
    for sentence in sentences:
        match = _DEFINITION_RE.search(sentence)
        if match:
            term = match.group("term").strip().lower()
            definitions[term] = sentence
    return definitions


def _heading(sentence: str) -> str:
    words = _WORD_RE.findall(sentence)
    return " ".join(words[:7]).title() or "Lecture section"
