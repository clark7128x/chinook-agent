from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

_SPACES = str.maketrans({"\u00a0": " ", "\u202f": " ", "\u2009": " "})
_QUOTES = str.maketrans({"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "’": "'", "ʼ": "'"})
_LETTERS = "A-Za-zА-Яа-яІіЇїЄєҐґ"
_NUMBER_PATTERNS = [
    r"-?\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?",
    r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?",
    r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?",
    r"-?\d+(?:[.,]\d+)?",
]
_NUMBER_RE = re.compile(
    rf"(?<![\w.,])(?:{'|'.join(_NUMBER_PATTERNS)})(?![{_LETTERS}])"
)
_GROUPED = re.compile(r"-?\d{1,3}(?:[.,]\d{3})+")


@dataclass(frozen=True)
class CompareConfig:
    abs_tol: float = 0.005
    rel_tol: float = 1e-6


@dataclass
class MatchResult:
    solved: bool
    strict_solved: bool
    value_recall: float | None
    matched: int
    total: int
    missing: list[Any] = field(default_factory=list)
    extra_numbers: list[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "solved": self.solved,
            "strict_solved": self.strict_solved,
            "value_recall": self.value_recall,
            "matched": self.matched,
            "total": self.total,
            "missing": self.missing,
            "extra_numbers": self.extra_numbers,
        }


def normalize_text(value: str) -> str:
    text = value.translate(_SPACES).translate(_QUOTES).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _parse_number(token: str) -> float:
    text = re.sub(r"[ \u00a0\u202f]", "", token)
    if _GROUPED.fullmatch(text):
        return float(text.replace(",", "").replace(".", ""))
    comma, dot = text.rfind(","), text.rfind(".")
    if comma >= 0 and dot >= 0:
        decimal, thousands = (",", ".") if comma > dot else (".", ",")
        text = text.replace(thousands, "").replace(decimal, ".")
    elif comma >= 0:
        text = text.replace(",", ".")
    return float(text)


def extract_numbers(text: str) -> list[float]:
    numbers: list[float] = []
    for match in _NUMBER_RE.finditer(text.translate(_SPACES)):
        try:
            numbers.append(_parse_number(match.group()))
        except ValueError:
            continue
    return numbers


def _numbers_close(left: float, right: float, cfg: CompareConfig) -> bool:
    return math.isclose(left, right, rel_tol=cfg.rel_tol, abs_tol=cfg.abs_tol)


def _string_present(value: str, answer: str) -> bool:
    needle = normalize_text(value).strip("\"' ")
    if not needle:
        return False
    haystack = normalize_text(answer)
    if len(needle) < 3:
        return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None
    return needle in haystack


def compare_answer(
    answer: str | None,
    gold_rows: Sequence[Sequence[Any]],
    question: str = "",
    cfg: CompareConfig | None = None,
) -> MatchResult:
    cfg = cfg or CompareConfig()
    values = [cell for row in gold_rows for cell in row if cell is not None]
    if not values:
        return MatchResult(False, False, None, 0, 0)
    if answer is None or not answer.strip():
        return MatchResult(False, False, 0.0, 0, len(values), missing=list(values))

    answer_numbers = extract_numbers(answer)
    gold_numbers = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]

    matched = 0
    missing: list[Any] = []
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            hit = any(_numbers_close(float(value), number, cfg) for number in answer_numbers)
        else:
            hit = _string_present(str(value), answer)
        if hit:
            matched += 1
        else:
            missing.append(value)

    allowed = gold_numbers + extract_numbers(question)
    extra = [
        number
        for number in answer_numbers
        if not any(_numbers_close(number, candidate, cfg) for candidate in allowed)
    ]
    solved = matched == len(values)
    return MatchResult(
        solved=solved,
        strict_solved=solved and not extra,
        value_recall=matched / len(values),
        matched=matched,
        total=len(values),
        missing=missing,
        extra_numbers=extra,
    )
