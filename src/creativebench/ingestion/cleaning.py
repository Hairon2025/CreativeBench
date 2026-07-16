"""Deterministic text normalization for raw Prompt data."""

import re
import unicodedata
from dataclasses import dataclass

from creativebench.ingestion.models import CleaningOperation

INVISIBLE_CHARACTERS = {"\u200b", "\u200c", "\u200d", "\ufeff"}
FULLWIDTH_ALPHANUMERIC_TRANSLATION = str.maketrans(
    {
        **{chr(code): chr(code - 0xFEE0) for code in range(0xFF10, 0xFF1A)},
        **{chr(code): chr(code - 0xFEE0) for code in range(0xFF21, 0xFF3B)},
        **{chr(code): chr(code - 0xFEE0) for code in range(0xFF41, 0xFF5B)},
        "\u3000": " ",
    }
)


@dataclass(frozen=True)
class CleaningResult:
    text: str
    operations: list[CleaningOperation]


def _apply(
    text: str,
    operation: CleaningOperation,
    transform,
    operations: list[CleaningOperation],
) -> str:
    updated = transform(text)
    if updated != text:
        operations.append(operation)
    return updated


def _normalize_unicode(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return normalized.translate(FULLWIDTH_ALPHANUMERIC_TRANSLATION)


def normalize_prompt_text(text: str) -> CleaningResult:
    """Normalize formatting noise without changing the Prompt's meaning."""

    operations: list[CleaningOperation] = []

    text = _apply(
        text,
        CleaningOperation.NORMALIZED_LINE_ENDINGS,
        lambda value: value.replace("\r\n", "\n").replace("\r", "\n"),
        operations,
    )
    text = _apply(
        text,
        CleaningOperation.NORMALIZED_UNICODE,
        _normalize_unicode,
        operations,
    )
    text = _apply(
        text,
        CleaningOperation.REMOVED_INVISIBLE_CHARACTERS,
        lambda value: "".join(char for char in value if char not in INVISIBLE_CHARACTERS),
        operations,
    )
    text = _apply(
        text,
        CleaningOperation.REMOVED_CONTROL_CHARACTERS,
        lambda value: "".join(
            char
            for char in value
            if char in {"\n", "\t"} or unicodedata.category(char) != "Cc"
        ),
        operations,
    )
    text = _apply(
        text,
        CleaningOperation.NORMALIZED_WHITESPACE,
        lambda value: re.sub(r"\n{3,}", "\n\n", re.sub(r"[^\S\n]+", " ", value)),
        operations,
    )
    text = _apply(
        text,
        CleaningOperation.TRIMMED_TEXT,
        lambda value: "\n".join(line.strip() for line in value.splitlines()).strip(),
        operations,
    )

    return CleaningResult(text=text, operations=operations)
