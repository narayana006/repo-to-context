"""Command-line interface for repo-to-context."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__
from .pack import INCLUDED, OMITTED, Pack, pack_repo
from .render import FORMATS, render
from .tokens import count_tokens, parse_budget


def _size(value: str) -> int:
    text = value.strip().lower()
    scale = 1
    for suffix, factor in (("kb", 1_000), ("mb", 1_000_000), ("k", 1_000), ("m", 1_000_000)):
        if text.endswith(suffix):
            text, scale = text[: -len(suffix)], factor
            break
    try:
        size = int(float(text) * scale)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid size {value!r} (try 500kb or 2mb)")
    if size <= 0:
        raise argparse.ArgumentTypeError("size must be greater than zero")
    return size


def _budget(value: str) -> int:
    try:
        return parse_budget(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def _ranking_table(pack: Pack) -> str:
    rows = [("SCORE", "TOKENS", "STATUS", "WHY", "PATH")]
    for entry in pack.ranked:
        rows.append(
            (f"{entry.score:.1f}", f"{entry.tokens:,}", entry.status, entry.reason, entry.path)
        )
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    lines = []
    for row in rows:
        cells = [row[0].rjust(widths[0]), row[1].rjust(widths[1]),
                 row[2].ljust(widths[2]), row[3].ljust(widths[3]), row[4]]
        lines.append("  ".join(cells))
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-to-context",
        description="Pack a repository into one Markdown, XML or JSON file for an LLM. "
        "Token counts are approximate.",
    )
    parser.add_argument("path", nargs="?", default=".", help="repository root (default: .)")
    parser.add_argument(
        "-b", "--budget", type=_budget, metavar="TOKENS",
        help="approximate token limit for the whole output, e.g. 8000, 120k, 1.5m",
    )
    parser.add_argument(
        "-f", "--format", choices=FORMATS + ("md",), default="markdown",
        help="output format (default: markdown)",
    )
    parser.add_argument("-o", "--output", metavar="FILE", help="write here instead of stdout")
    parser.add_argument(
        "-i", "--ignore", action="append", default=[], metavar="PATTERN",
        help="extra ignore rule in .gitignore syntax (repeatable; prefix with ! to re-include)",
    )
    parser.add_argument(
        "--ignore-file", action="append", default=[], metavar="FILE",
        help="read extra ignore rules from a file (repeatable)",
    )
    parser.add_argument("--no-gitignore", action="store_true", help="do not read .gitignore files")
    parser.add_argument(
        "--no-default-ignores", action="store_true",
        help="do not skip .git, node_modules, lock files and similar by default",
    )
    parser.add_argument(
        "--no-git", action="store_true",
        help="do not use git history to boost recently changed files",
    )
    parser.add_argument(
        "--max-file-size", type=_size, default=1_000_000, metavar="SIZE",
        help="skip files larger than this (default: 1mb)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="print the ranking table (score, tokens, status) instead of file contents",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="no summary on stderr")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fmt = "markdown" if args.format == "md" else args.format
    patterns = list(args.ignore)
    try:
        for name in args.ignore_file:
            with open(name, encoding="utf-8") as handle:
                patterns.extend(handle.read().splitlines())
        pack = pack_repo(
            args.path,
            args.budget,
            fmt,
            ignore=patterns,
            use_gitignore=not args.no_gitignore,
            use_default_ignores=not args.no_default_ignores,
            max_file_bytes=args.max_file_size,
            recency={} if args.no_git else None,
        )
    except OSError as exc:
        print(f"repo-to-context: {exc}", file=sys.stderr)
        return 2

    output = _ranking_table(pack) if args.list else render(pack, fmt)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output)
    else:
        sys.stdout.write(output)

    if not args.quiet:
        included = sum(1 for f in pack.files if f.status == INCLUDED)
        omitted = sum(1 for f in pack.files if f.status == OMITTED)
        skipped = len(pack.files) - included - omitted
        message = f"repo-to-context: {included} files included"
        if omitted:
            message += f", {omitted} omitted to fit the budget"
        if skipped:
            message += f", {skipped} binary or oversized files skipped"
        if not args.list:
            message += f"; output is about {count_tokens(output):,} tokens"
            if args.budget is not None:
                message += f" of a {args.budget:,} budget"
            message += " (approximate)"
        print(message, file=sys.stderr)
        if args.budget is not None and included == 0 and omitted:
            print(
                "repo-to-context: the budget is too small for any file; "
                "only the tree was written",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
