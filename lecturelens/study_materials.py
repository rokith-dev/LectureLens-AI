from collections import Counter
from dataclasses import dataclass
from html import unescape
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
_WORD_RE = re.compile(r"[^\W\d_][\w'-]{2,}", re.UNICODE)
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

    normalized_text = normalize_lecture_text(text)
    words = [word.casefold() for word in _WORD_RE.findall(normalized_text)]
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
    seen_phrases: set[str] = set()
    maximum = ranked[0][1] if ranked else 1
    for phrase, count in ranked:
        normalized_phrase = _normalize_phrase(phrase)
        if normalized_phrase in seen_phrases:
            continue
        if _is_repetitive_phrase(phrase) or _is_noise_phrase(phrase):
            continue
        if any(
            normalized_phrase in existing or existing in normalized_phrase
            for existing in seen_phrases
        ):
            continue
        seen_phrases.add(normalized_phrase)
        score = round((count / maximum) * (1 + 0.1 * phrase.count(" ")), 3)
        results.append(Keyword(phrase=phrase, score=score))
        if len(results) >= limit:
            break
    return tuple(results)


def generate_glossary(text: str, keywords: tuple[Keyword, ...] | None = None) -> tuple[GlossaryEntry, ...]:
    """Build glossary entries from explicit definitions or source context."""
    _validate_text(text)
    normalized_text = normalize_lecture_text(text)
    sentences = _sentences(normalized_text)
    explicit = _explicit_definitions(sentences)
    selected = keywords or extract_keywords(normalized_text, limit=12)
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

    normalized_text = normalize_lecture_text(text)
    sentences = _sentences(normalized_text)
    keywords = extract_keywords(normalized_text)
    glossary = generate_glossary(normalized_text, keywords)
    definition_terms = {entry.term.lower() for entry in glossary if not entry.needs_verification}
    examples = tuple(
        sentence for sentence in sentences
        if re.search(r"\b(for example|e\.g\.|such as|for instance)\b", sentence, re.IGNORECASE)
    )
    headings = tuple(dict.fromkeys(
        _heading(sentence) for sentence in sentences[: min(5, len(sentences))]
    ))[:3]
    bullets = tuple(dict.fromkeys(sentences))[:8]
    takeaways = tuple(dict.fromkeys(
        item.strip() for item in (short_summary, *sentences[-3:])
        if item.strip()
    ))[:3]
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
    return list(dict.fromkeys(
        sentence.strip() for sentence in _SENTENCE_RE.split(normalize_lecture_text(text))
        if sentence.strip()
    ))


def normalize_lecture_text(text: str) -> str:
    """Normalize extraction artifacts while preserving meaningful source wording."""
    if not isinstance(text, str):
        raise StudyMaterialsError("Lecture text must be a string.")
    cleaned = unescape(text).replace("\u00a0", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\s*\n\s*", "\n", cleaned)
    lines: list[str] = []
    previous_line = ""
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_repetitive_line(line) or _normalize_phrase(line) == _normalize_phrase(previous_line):
            previous_line = line
            continue
        lines.append(line)
        previous_line = line
    cleaned = " ".join(lines)
    cleaned = re.sub(
        r"\b([^\W\d_][\w'-]{2,})(?:\s+\1){2,}\b",
        r"\1",
        cleaned,
        flags=re.IGNORECASE | re.UNICODE,
    )
    sentences = []
    for sentence in _SENTENCE_RE.split(cleaned):
        sentence = re.sub(r"\s+", " ", sentence).strip()
        if sentence and _normalize_phrase(sentence) not in {
            _normalize_phrase(item) for item in sentences
        }:
            sentences.append(sentence)
    return "\n".join(sentences)


def _normalize_phrase(value: str) -> str:
    return re.sub(r"\W+", " ", value.casefold(), flags=re.UNICODE).strip()


def _is_repetitive_line(line: str) -> bool:
    words = _WORD_RE.findall(line)
    return bool(words) and len(words) >= 3 and len({word.casefold() for word in words}) == 1


def _is_repetitive_phrase(phrase: str) -> bool:
    words = phrase.split()
    return len(words) > 1 and len(set(words)) == 1


def _is_noise_phrase(phrase: str) -> bool:
    words = phrase.split()
    return len(words) == 1 and len(words[0]) < 3


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
