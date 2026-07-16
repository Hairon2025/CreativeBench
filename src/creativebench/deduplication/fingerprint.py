"""Stable fingerprints for exact and near-text duplicate detection."""

import hashlib
import unicodedata
from collections import Counter


def exact_fingerprint(text: str) -> str:
    """Return a stable SHA-256 fingerprint of cleaned text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fingerprint_text(text: str) -> str:
    return "".join(
        char.casefold()
        for char in text
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def _character_ngrams(text: str, size: int = 3) -> list[str]:
    normalized = _fingerprint_text(text)
    if len(normalized) <= size:
        return [normalized] if normalized else []
    return [normalized[index : index + size] for index in range(len(normalized) - size + 1)]


def simhash(text: str, *, bits: int = 64, ngram_size: int = 3) -> int:
    """Create a SimHash from character n-grams, suitable for Chinese text."""

    if bits < 1 or bits > 256:
        raise ValueError("SimHash bits 必须在 1 到 256 之间")

    tokens = Counter(_character_ngrams(text, ngram_size))
    if not tokens:
        return 0

    vector = [0] * bits
    byte_count = (bits + 7) // 8
    for token, weight in tokens.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()[:byte_count]
        hashed = int.from_bytes(digest, byteorder="big")
        for bit in range(bits):
            vector[bit] += weight if hashed & (1 << bit) else -weight

    fingerprint = 0
    for bit, value in enumerate(vector):
        if value >= 0:
            fingerprint |= 1 << bit
    return fingerprint


def hamming_distance(left: int, right: int) -> int:
    """Count differing bits between two SimHash fingerprints."""

    return (left ^ right).bit_count()
