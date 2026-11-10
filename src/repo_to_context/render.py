"""Render a Pack as Markdown, XML or JSON."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from xml.sax.saxutils import escape, quoteattr

from .pack import INCLUDED, OMITTED, FileEntry, Pack
from .tokens import count_tokens

FORMATS = ("markdown", "xml", "json")

LANGUAGES = {
    ".py": "python", ".js": "javascript", ".jsx": "jsx", ".ts": "typescript",
    ".tsx": "tsx", ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin",
    ".rb": "ruby", ".php": "php", ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp",
    ".hpp": "cpp", ".cs": "csharp", ".swift": "swift", ".sh": "bash", ".sql": "sql",
    ".json": "json", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml", ".md": "markdown",
    ".html": "html", ".css": "css", ".xml": "xml", ".ini": "ini", ".cfg": "ini",
}
_XML_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
NOTE = "Token counts are approximate."


def _annotation(entry: FileEntry) -> str:
    if entry.status == INCLUDED:
        return f"{entry.tokens:,} tokens"
    if entry.status == OMITTED:
        return f"{entry.tokens:,} tokens, omitted"
    return f"{entry.status}, skipped"


def render_tree(pack: Pack) -> str:
    """Draw every non-ignored file with its token count and status."""
    root: dict = {}
    for entry in pack.files:
        node = root
        parts = entry.path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = entry

    lines = [f"{pack.name}/"]

    def draw(node: dict, prefix: str) -> None:
        # directories first, then files, each alphabetically
        names = sorted(node, key=lambda name: (not isinstance(node[name], dict), name))
        for index, name in enumerate(names):
            last = index == len(names) - 1
            branch = "└── " if last else "├── "
            child = node[name]
            if isinstance(child, dict):
                lines.append(f"{prefix}{branch}{name}/")
                draw(child, prefix + ("    " if last else "│   "))
            else:
                lines.append(f"{prefix}{branch}{name}  ({_annotation(child)})")

    draw(root, "")
    return "\n".join(lines)


def _summary(pack: Pack) -> str:
    text_files = [f for f in pack.files if f.status in (INCLUDED, OMITTED)]
    included = [f for f in text_files if f.status == INCLUDED]
    line = (
        f"{len(included)} of {len(text_files)} text files included, "
        f"about {pack.content_tokens:,} tokens of file content"
    )
    if pack.budget is not None:
        line += f" (budget {pack.budget:,})"
    return line + ". " + NOTE


def _fence(content: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", content)), default=0)
    return "`" * max(3, longest + 1)


def _markdown_file(entry: FileEntry) -> str:
    fence = _fence(entry.content)
    language = LANGUAGES.get(PurePosixPath(entry.path).suffix.lower(), "")
    body = entry.content if entry.content.endswith("\n") or not entry.content else entry.content + "\n"
    return f"### `{entry.path}`\n\n{fence}{language}\n{body}{fence}\n\n"


def _xml_file(entry: FileEntry) -> str:
    content = escape(_XML_ILLEGAL.sub("", entry.content))
    return f"<file path={quoteattr(entry.path)} tokens=\"{entry.tokens}\">\n{content}\n</file>\n"


def _json_file(entry: FileEntry) -> dict:
    return {
        "path": entry.path,
        "tokens": entry.tokens,
        "score": entry.score,
        "content": entry.content,
    }


def render_markdown(pack: Pack) -> str:
    parts = [
        f"# Repository context: {pack.name}\n\n{_summary(pack)}\n\n",
        f"## File tree\n\n```\n{render_tree(pack)}\n```\n\n## Files\n\n",
    ]
    parts.extend(_markdown_file(entry) for entry in pack.included)
    return "".join(parts).rstrip("\n") + "\n"


def render_xml(pack: Pack) -> str:
    budget = "" if pack.budget is None else f" token_budget=\"{pack.budget}\""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f"<repository name={quoteattr(pack.name)} approx_content_tokens=\"{pack.content_tokens}\"{budget}>\n",
        f"<summary>{escape(_summary(pack))}</summary>\n",
        f"<tree>\n{escape(render_tree(pack))}\n</tree>\n<files>\n",
    ]
    parts.extend(_xml_file(entry) for entry in pack.included)
    parts.append("</files>\n</repository>\n")
    return "".join(parts)


def render_json(pack: Pack) -> str:
    document = {
        "repository": pack.name,
        "token_counts": "approximate",
        "token_budget": pack.budget,
        "content_tokens": pack.content_tokens,
        "tree": render_tree(pack),
        "files": [_json_file(entry) for entry in pack.included],
        "not_included": [
            {"path": f.path, "tokens": f.tokens, "reason": f.status}
            for f in pack.files
            if f.status != INCLUDED
        ],
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


_RENDERERS = {"markdown": render_markdown, "xml": render_xml, "json": render_json}


def render(pack: Pack, fmt: str = "markdown") -> str:
    """Render ``pack`` in one of :data:`FORMATS`."""
    try:
        return _RENDERERS[fmt](pack)
    except KeyError:
        raise ValueError(f"unknown format {fmt!r}; choose from {', '.join(FORMATS)}") from None


def file_cost(entry: FileEntry, fmt: str) -> int:
    """Tokens that including ``entry`` adds to the rendered output."""
    if fmt == "markdown":
        return count_tokens(_markdown_file(entry))
    if fmt == "xml":
        return count_tokens(_xml_file(entry))
    if fmt == "json":
        # the entry moves from "not_included" to "files"; charge the full
        # object plus separators and ignore the small saving
        return count_tokens(json.dumps(_json_file(entry), indent=6, ensure_ascii=False)) + 2
    raise ValueError(f"unknown format {fmt!r}; choose from {', '.join(FORMATS)}")


def overhead_tokens(pack: Pack, fmt: str) -> int:
    """Tokens used by the header and tree when no file is included yet.

    Measured with every file marked omitted, which is the longest the tree
    and summary can get, plus a small margin for the totals in the header.
    """
    saved = [(entry, entry.status) for entry in pack.files]
    saved_budget = pack.budget
    for entry in pack.files:
        if entry.status == INCLUDED:
            entry.status = OMITTED
    pack.budget = 10**9
    try:
        return count_tokens(render(pack, fmt)) + 8
    finally:
        pack.budget = saved_budget
        for entry, status in saved:
            entry.status = status
