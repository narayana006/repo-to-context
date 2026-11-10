"""A small .gitignore-compatible matcher.

Supports comments, blank lines, ``!`` negation, directory-only patterns
(trailing ``/``), anchoring (leading or inner ``/``), ``*``, ``?``, character
classes and ``**``. Rules from nested .gitignore files apply to their own
directory. As in git, the last matching rule wins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Rule:
    base: str  # directory the rule is relative to, "" for the root
    regex: "re.Pattern[str]"
    negated: bool
    dir_only: bool
    source: str


def _translate(pattern: str) -> str:
    out: list[str] = []
    i, n = 0, len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "*":
            if pattern.startswith("**", i):
                at_segment_start = i == 0 or pattern[i - 1] == "/"
                if at_segment_start and pattern.startswith("**/", i):
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        elif ch == "[":
            end = pattern.find("]", i + 2)
            if end == -1:
                out.append(re.escape(ch))
            else:
                body = pattern[i + 1 : end]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = end
        elif ch == "\\" and i + 1 < n:
            i += 1
            out.append(re.escape(pattern[i]))
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def parse_rule(line: str, base: str = "") -> Rule | None:
    """Turn one .gitignore line into a Rule, or None if it is blank/comment."""
    source = line.rstrip("\n")
    pattern = source
    if not pattern.endswith("\\ "):
        pattern = pattern.rstrip()
    if not pattern or pattern.startswith("#"):
        return None
    negated = pattern.startswith("!")
    if negated:
        pattern = pattern[1:]
    dir_only = pattern.endswith("/")
    pattern = pattern.rstrip("/")
    if not pattern:
        return None
    anchored = "/" in pattern
    pattern = pattern.lstrip("/")
    body = _translate(pattern)
    if not anchored:
        body = "(?:.*/)?" + body
    try:
        regex = re.compile(body + r"\Z")
    except re.error:
        return None
    return Rule(base, regex, negated, dir_only, source)


class IgnoreRules:
    """An ordered list of rules; later rules override earlier ones."""

    def __init__(self) -> None:
        self._rules: list[Rule] = []

    def add_patterns(self, patterns: Iterable[str], base: str = "") -> None:
        for line in patterns:
            rule = parse_rule(line, base)
            if rule is not None:
                self._rules.append(rule)

    def copy(self) -> "IgnoreRules":
        clone = IgnoreRules()
        clone._rules = list(self._rules)
        return clone

    def match(self, path: str, is_dir: bool = False) -> bool | None:
        """Return True (ignored), False (re-included) or None (no rule matched).

        ``path`` is relative to the repository root and uses ``/``.
        """
        verdict: bool | None = None
        for rule in self._rules:
            if rule.dir_only and not is_dir:
                continue
            if rule.base:
                prefix = rule.base + "/"
                if not path.startswith(prefix):
                    continue
                relative = path[len(prefix) :]
            else:
                relative = path
            if rule.regex.match(relative):
                verdict = not rule.negated
        return verdict

    def is_ignored(self, path: str, is_dir: bool = False) -> bool:
        return bool(self.match(path, is_dir))
