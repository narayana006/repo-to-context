"""Importance scoring: which files should claim the token budget first."""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

MANIFESTS = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "package.json",
    "tsconfig.json", "cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "build.gradle.kts", "gemfile", "composer.json", "makefile", "dockerfile",
    "docker-compose.yml", "docker-compose.yaml", "compose.yaml", "cmakelists.txt",
    "justfile", "tox.ini", "mix.exs", "deno.json",
}
ENTRYPOINT_STEMS = {"main", "__main__", "cli", "app", "index", "server", "manage", "lib", "mod"}
CODE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".rb", ".php",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".swift", ".scala", ".sh", ".sql",
    ".ex", ".exs", ".lua", ".r", ".m", ".vue", ".svelte", ".dart", ".zig",
}
DOC_SUFFIXES = {".md", ".rst", ".txt", ".adoc"}
TOP_DOCS = {"architecture", "agents", "contributing", "design", "overview"}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testdata", "fixtures"}
LOW_VALUE_DIRS = {"examples", "example", "samples", "docs", "doc", "vendor", "third_party"}

RECENCY_COMMITS = 30
RECENCY_BONUS = 15.0


def _is_test(path: PurePosixPath) -> bool:
    name = path.name.lower()
    if any(part.lower() in TEST_DIRS for part in path.parts[:-1]):
        return True
    stem = name.split(".")[0]
    return (
        stem.startswith("test_")
        or stem.endswith("_test")
        or ".test." in name
        or ".spec." in name
        or name == "conftest.py"
    )


def base_score(rel_path: str) -> tuple[float, str]:
    """Return ``(score, reason)`` from the path alone."""
    path = PurePosixPath(rel_path)
    name = path.name.lower()
    stem = name.split(".")[0]
    suffix = path.suffix.lower()
    depth = len(path.parts) - 1

    if depth == 0 and stem == "readme":
        return 100.0, "readme"
    if _is_test(path):
        return 15.0, "test"
    if name in MANIFESTS:
        return 80.0, "config"
    if suffix in CODE_SUFFIXES and stem in ENTRYPOINT_STEMS:
        return 70.0, "entrypoint"
    if depth == 0 and suffix in DOC_SUFFIXES and stem in TOP_DOCS:
        return 60.0, "doc"
    if suffix in CODE_SUFFIXES:
        return 45.0, "source"
    if suffix in DOC_SUFFIXES:
        return 25.0, "doc"
    return 30.0, "other"


def score_file(rel_path: str, tokens: int, recency: dict[str, int]) -> tuple[float, str]:
    """Combine the path score with depth, size and recent-change adjustments.

    ``recency`` maps a path to the index of the newest commit that touched it
    (0 is the latest commit).
    """
    score, reason = base_score(rel_path)
    path = PurePosixPath(rel_path)
    directories = [part.lower() for part in path.parts[:-1]]
    score -= min(len(directories), 5) * 2.0
    if any(part in LOW_VALUE_DIRS for part in directories):
        score -= 15.0
    score -= min(tokens / 2000.0, 10.0)  # very large files are poor value per token
    if rel_path in recency:
        age = recency[rel_path]
        score += RECENCY_BONUS * max(0.0, 1.0 - age / RECENCY_COMMITS)
        reason += ", recent"
    return round(score, 1), reason


def git_recency(root: Path, commits: int = RECENCY_COMMITS) -> dict[str, int]:
    """Map each recently changed path to the index of its newest commit.

    Returns an empty dict when ``root`` is not inside a git work tree or git
    is not installed.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "log", f"-n{commits}", "--relative",
             "--name-only", "--format=%x01"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if result.returncode != 0:
        return {}
    recency: dict[str, int] = {}
    index = -1
    for line in result.stdout.splitlines():
        if line.startswith("\x01"):
            index += 1
        elif line.strip() and index >= 0:
            recency.setdefault(line.strip(), index)
    return recency
