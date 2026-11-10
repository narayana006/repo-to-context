"""Walk a repository, rank its files and choose what fits in the budget."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .ignore import IgnoreRules
from .ranking import git_recency, score_file
from .tokens import count_tokens

DEFAULT_IGNORES = (
    ".git/", ".hg/", ".svn/", "node_modules/", "__pycache__/", ".venv/", "venv/",
    ".tox/", ".mypy_cache/", ".pytest_cache/", ".ruff_cache/", ".idea/", ".vscode/",
    "*.egg-info/", "*.pyc", ".DS_Store",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock",
    "Cargo.lock", "Gemfile.lock", "composer.lock", "go.sum",
    "*.min.js", "*.min.css", "*.map",
)
DEFAULT_MAX_FILE_BYTES = 1_000_000

INCLUDED = "included"
OMITTED = "omitted"  # ranked too low to fit in the budget
BINARY = "binary"
TOO_LARGE = "too large"


@dataclass
class FileEntry:
    path: str  # relative to the repository root, "/" separated
    size: int
    status: str = OMITTED
    tokens: int = 0
    score: float = 0.0
    reason: str = ""
    content: str = field(default="", repr=False)


@dataclass
class Pack:
    name: str
    files: list[FileEntry]  # every non-ignored file, sorted by path
    budget: int | None = None

    @property
    def included(self) -> list[FileEntry]:
        """Included files, most important first."""
        chosen = [f for f in self.files if f.status == INCLUDED]
        return sorted(chosen, key=lambda f: (-f.score, f.path))

    @property
    def ranked(self) -> list[FileEntry]:
        """All text files, most important first."""
        text = [f for f in self.files if f.status in (INCLUDED, OMITTED)]
        return sorted(text, key=lambda f: (-f.score, f.path))

    @property
    def content_tokens(self) -> int:
        return sum(f.tokens for f in self.files if f.status == INCLUDED)


def _read_text(path: Path) -> str | None:
    """Return the file's text, or None if it looks binary."""
    data = path.read_bytes()
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def walk(
    root: Path,
    file_rules: IgnoreRules,
    override_rules: IgnoreRules | None = None,
    use_gitignore: bool = True,
) -> list[str]:
    """Return the relative paths of all files that are not ignored.

    ``file_rules`` are the lowest-precedence rules; .gitignore files found on
    the way down are layered on top of them, and ``override_rules`` (for
    example patterns from the command line) have the final say. Ignored
    directories are not entered, and symlinks are never followed.
    """
    found: list[str] = []

    def visit(directory: Path, rel: str, active: IgnoreRules) -> None:
        ignore_file = directory / ".gitignore"
        if use_gitignore and ignore_file.is_file():
            try:
                lines = ignore_file.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
            active = active.copy()
            active.add_patterns(lines, base=rel)
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            if entry.is_symlink():
                continue
            child = f"{rel}/{entry.name}" if rel else entry.name
            is_dir = entry.is_dir()
            verdict = override_rules.match(child, is_dir) if override_rules else None
            if verdict is None:
                verdict = active.match(child, is_dir)
            if verdict:
                continue
            if is_dir:
                visit(Path(entry.path), child, active)
            elif entry.is_file():
                found.append(child)

    visit(root, "", file_rules)
    return found


def scan(
    root: str | os.PathLike[str],
    *,
    ignore: Iterable[str] = (),
    use_gitignore: bool = True,
    use_default_ignores: bool = True,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    recency: dict[str, int] | None = None,
) -> Pack:
    """Read and score every non-ignored file under ``root``; select nothing yet.

    ``recency`` overrides the git history lookup (path -> index of the newest
    commit touching it), mainly for tests.
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"{root} is not a directory")

    defaults = IgnoreRules()
    if use_default_ignores:
        defaults.add_patterns(DEFAULT_IGNORES)
    overrides = IgnoreRules()
    overrides.add_patterns(ignore)
    if recency is None:
        recency = git_recency(root_path)

    files: list[FileEntry] = []
    for rel in walk(root_path, defaults, overrides, use_gitignore):
        full = root_path / rel
        try:
            size = full.stat().st_size
            entry = FileEntry(path=rel, size=size)
            if size > max_file_bytes:
                entry.status = TOO_LARGE
            else:
                text = _read_text(full)
                if text is None:
                    entry.status = BINARY
                else:
                    entry.content = text
                    entry.tokens = count_tokens(text)
                    entry.score, entry.reason = score_file(rel, entry.tokens, recency)
        except OSError:
            continue
        files.append(entry)
    return Pack(name=root_path.name, files=files)


def select(
    pack: Pack,
    budget: int | None,
    cost: Callable[[FileEntry], int] | None = None,
    overhead: int = 0,
) -> Pack:
    """Mark the files that fit in ``budget``, most important first.

    ``cost`` returns the tokens a file adds to the output including its
    wrapper (defaults to the content tokens); ``overhead`` is the fixed cost
    of everything that is not a file. A file that does not fit is skipped and
    smaller, lower-ranked files may still be taken after it.
    """
    pack.budget = budget
    remaining = None if budget is None else budget - overhead
    for entry in pack.ranked:
        if remaining is None:
            entry.status = INCLUDED
            continue
        needed = cost(entry) if cost else entry.tokens
        if needed <= remaining:
            entry.status = INCLUDED
            remaining -= needed
        else:
            entry.status = OMITTED
    return pack


def pack_repo(
    root: str | os.PathLike[str],
    budget: int | None = None,
    fmt: str = "markdown",
    **scan_options,
) -> Pack:
    """Scan ``root`` and select the files that fit ``budget`` tokens of output.

    The budget covers the whole rendered document in format ``fmt``: the
    header, the file tree and each file's wrapper as well as its content.
    Extra keyword arguments are passed to :func:`scan`.
    """
    from .render import file_cost, overhead_tokens

    pack = scan(root, **scan_options)
    if budget is None:
        return select(pack, None)
    return select(pack, budget, lambda entry: file_cost(entry, fmt), overhead_tokens(pack, fmt))
