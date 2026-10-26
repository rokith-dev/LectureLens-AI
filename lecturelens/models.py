from dataclasses import dataclass
from typing import Literal


InputKind = Literal["pdf", "youtube"]


@dataclass(frozen=True)
class LectureText:
    """Normalized text returned by either supported lecture input."""

    source_type: InputKind
    text: str
    title: str
    metadata: dict[str, str | int]
