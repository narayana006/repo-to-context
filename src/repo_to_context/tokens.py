"""Approximate token counting.

No tokenizer is bundled, so counts are estimates. The heuristic is tuned to
land close to, and usually slightly above, what BPE tokenizers report for
source code and English prose:

* a run of letters, digits and underscores costs one token per four
  characters (rounded up), so ``id`` is 1 and ``get_user_by_id`` is 4;
* every other non-space character (punctuation, CJK, emoji) costs one token;
* every line break costs one token; other whitespace is free.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_OTHER_RE = re.compile(r"[^A-Za-z0-9_\s]")
_BUDGET_RE = re.compile(r"\s*(\d+(?:\.\d+)?)\s*([kKmM]?)\s*\Z")


def count_tokens(text: str) -> int:
    """Return the approximate number of tokens in ``text``."""
    total = text.count("\n")
    total += len(_OTHER_RE.findall(text))
    for match in _WORD_RE.finditer(text):
        total += (match.end() - match.start() + 3) // 4
    return total


def parse_budget(value: str) -> int:
    """Parse ``"8000"``, ``"120k"`` or ``"1.5m"`` into a token count."""
    match = _BUDGET_RE.match(value)
    if match is None:
        raise ValueError(f"invalid token budget {value!r} (try 8000, 120k or 1.5m)")
    number = float(match.group(1))
    scale = {"": 1, "k": 1_000, "m": 1_000_000}[match.group(2).lower()]
    budget = int(number * scale)
    if budget <= 0:
        raise ValueError("token budget must be greater than zero")
    return budget
