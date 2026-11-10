# repo-to-context

Pack a code repository into one LLM-ready file: gitignore-aware, token-budgeted, importance-ranked.

```bash
repo-to-context . --budget 120k --format xml > context.xml
```

**Status: v0.1.0, usable.** Working today: `.gitignore` handling plus custom ignore rules, a token budget with importance ranking, Markdown / XML / JSON output, and a file tree with per-file token counts. Token counts are **approximate** (a heuristic, not a real tokenizer). AGENTS.md skeleton generation is not built yet.

## Install

Python 3.10 or newer. No dependencies.

```bash
pip install git+https://github.com/narayana006/repo-to-context
```

or from a clone:

```bash
git clone https://github.com/narayana006/repo-to-context
cd repo-to-context
pip install -e .
```

## Try it

The clone includes a small sample project in `examples/sample-repo`. It contains a `debug.log` and a `scratch/` directory that its `.gitignore` excludes, and a PNG. Pack it with a 1,000-token budget:

```console
$ repo-to-context examples/sample-repo --budget 1k -o context.md
repo-to-context: 6 files included, 3 omitted to fit the budget, 1 binary or oversized files skipped; output is about 951 tokens of a 1,000 budget (approximate)
```

The first 40 lines of `context.md`:

````markdown
# Repository context: sample-repo

6 of 9 text files included, about 547 tokens of file content (budget 1,000). Token counts are approximate.

## File tree

```
sample-repo/
├── assets/
│   └── logo.png  (binary, skipped)
├── docs/
│   └── design.md  (67 tokens, omitted)
├── src/
│   └── shortlink/
│       ├── __init__.py  (31 tokens)
│       ├── cli.py  (231 tokens)
│       ├── codes.py  (190 tokens, omitted)
│       └── store.py  (337 tokens, omitted)
├── tests/
│   └── test_codes.py  (116 tokens)
├── .gitignore  (19 tokens)
├── README.md  (76 tokens)
└── pyproject.toml  (74 tokens)
```

## Files

### `README.md`

```markdown
# shortlink

A tiny URL shortener used as sample input for repo-to-context.

Run it with `python -m shortlink serve` and create a link with
`python -m shortlink add https://example.com/a/long/path`.
```

### `pyproject.toml`

````

The rest of the file is the remaining included files, most important first. What happened:

- `debug.log` and `scratch/` never appear: the sample's `.gitignore` excludes them.
- `logo.png` is listed in the tree but its bytes are not included.
- The README, the project config and the CLI entry point were taken first. `codes.py` and `store.py` did not fit in what was left, so they are marked `omitted` in the tree; the model still sees that they exist and how big they are. Smaller, lower-ranked files filled the remaining space.

To see how files are ranked without producing the context, use `--list`:

```console
$ repo-to-context examples/sample-repo --list --no-git --budget 700
SCORE  TOKENS  STATUS    WHY         PATH
100.0      76  included  readme      README.md
 80.0      74  included  config      pyproject.toml
 65.9     231  omitted   entrypoint  src/shortlink/cli.py
 41.0      31  included  source      src/shortlink/__init__.py
 40.9     190  omitted   source      src/shortlink/codes.py
 40.8     337  omitted   source      src/shortlink/store.py
 30.0      19  included  other       .gitignore
 12.9     116  omitted   test        tests/test_codes.py
  8.0      67  included  doc         docs/design.md
repo-to-context: 5 files included, 4 omitted to fit the budget, 1 binary or oversized files skipped
```

(`--no-git` is used here so the scores do not depend on commit history; see [Ranking](#ranking). The summary line is printed to stderr.)

## Usage

```text
repo-to-context [PATH] [options]
```

| Option | Meaning |
| --- | --- |
| `PATH` | Repository root. Default: current directory. |
| `-b`, `--budget TOKENS` | Approximate token limit for the whole output: `8000`, `120k`, `1.5m`. Without it every text file is included. |
| `-f`, `--format` | `markdown` (default, `md` also accepted), `xml` or `json`. |
| `-o`, `--output FILE` | Write to a file instead of stdout. |
| `-i`, `--ignore PATTERN` | Extra ignore rule in `.gitignore` syntax. Repeatable. These override `.gitignore`, and `!pattern` re-includes something. |
| `--ignore-file FILE` | Read extra ignore rules from a file. Repeatable. |
| `--no-gitignore` | Do not read `.gitignore` files. |
| `--no-default-ignores` | Do not apply the built-in ignore list (below). |
| `--no-git` | Do not use git history to boost recently changed files. |
| `--max-file-size SIZE` | Skip files larger than this, e.g. `500kb`, `2mb`. Default `1mb`. |
| `--list` | Print the ranking table instead of file contents. |
| `-q`, `--quiet` | No summary line on stderr. |

Examples:

```bash
# everything, as Markdown, to the clipboard (macOS)
repo-to-context . | pbcopy

# leave out tests and docs, 50k tokens, JSON
repo-to-context . -b 50k -f json -i 'tests/' -i 'docs/' -o context.json

# pipe-friendly: the summary goes to stderr, the context to stdout
repo-to-context ~/code/myservice --budget 120k --format xml > context.xml
```

### What gets ignored

1. A built-in list: `.git/`, `node_modules/`, `__pycache__/`, virtualenvs, tool caches, editor folders, lock files (`package-lock.json`, `yarn.lock`, `poetry.lock`, `Cargo.lock`, `go.sum`, ...), `*.min.js`, `*.min.css`, `*.map`.
2. Every `.gitignore` in the tree, each applied to its own directory. Supported syntax: comments, `!` negation, trailing `/` for directories, leading or inner `/` for anchoring, `*`, `?`, `[abc]`, `**`. The last matching rule wins, as in git.
3. `--ignore` and `--ignore-file` rules, which take precedence over both.

Binary files (a NUL byte in the first 8 KB, or not valid UTF-8) and files over `--max-file-size` are shown in the tree but their contents are skipped. Symlinks are not followed.

### Ranking

Each text file gets a score; files are added to the output from the highest score down until the budget is used.

| Kind | Base score | Recognised by |
| --- | --- | --- |
| readme | 100 | `README.*` at the root |
| config | 80 | `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Dockerfile`, `Makefile`, ... |
| entrypoint | 70 | code files named `main`, `__main__`, `cli`, `app`, `index`, `server`, `manage`, `lib`, `mod` |
| top-level doc | 60 | `ARCHITECTURE`, `AGENTS`, `CONTRIBUTING`, `DESIGN`, `OVERVIEW` at the root |
| source | 45 | other code files |
| other | 30 | anything unclassified |
| doc | 25 | other `.md`, `.rst`, `.txt`, `.adoc` |
| test | 15 | `tests/`, `test_*`, `*_test`, `*.spec.*`, ... |

Adjustments: minus 2 per directory level (up to 10), minus 15 under `examples/`, `docs/` or `vendor/`, minus up to 10 for very large files, and plus up to 15 for files touched in the last 30 commits (newest commit gets the most). The recency boost needs `git` and a repository; otherwise it is skipped silently.

A file that does not fit is skipped whole, never truncated, and smaller lower-ranked files may be taken after it.

### Token counts are approximate

No tokenizer is bundled. The estimate is: one token per four characters of each word or identifier (rounded up), one per punctuation or non-ASCII character, one per line break. It is designed to err slightly high so the output stays under the real limit, but it can be off by 10 to 20 percent either way depending on the model and the content. Leave headroom.

The budget covers the whole output, including the tree and per-file wrappers. If the budget is smaller than the tree alone, only the header and tree are written and a warning is printed.

### Output formats

- **Markdown**: summary, file tree, then each file under a `### path` heading in a fenced block (the fence grows if the file itself contains backtick fences).
- **XML**: `<repository>` with `<summary>`, `<tree>` and `<files>`; each `<file path="..." tokens="...">` holds the escaped content. The result is well-formed XML.
- **JSON**: `repository`, `token_budget`, `content_tokens`, `tree`, `files` (`path`, `tokens`, `score`, `content`) and `not_included` (`path`, `tokens`, `reason`).

### As a library

```python
from repo_to_context import pack_repo, render

pack = pack_repo("examples/sample-repo", budget=2000, fmt="xml")
text = render(pack, "xml")
for entry in pack.included:
    print(entry.path, entry.tokens, entry.score)
```

## Features

- [x] Respects `.gitignore` (including nested ones) and custom ignore rules
- [x] Token budget with importance ranking (entrypoints, configs, recently changed files first)
- [x] Output as Markdown, XML or JSON
- [x] File tree summary and per-file token counts
- [ ] Optional AGENTS.md skeleton generation
- [ ] Exact token counts through an optional tokenizer plug-in
- [ ] Truncating or summarising files that do not fit instead of omitting them
- [ ] Global gitignore and `.git/info/exclude`

## Limitations

- Token counts are estimates, not tokenizer output.
- Ranking is based on file names, paths, size and git recency. It does not read imports or measure how central a file is.
- Only the `.gitignore` files inside the tree are read; your global gitignore and `.git/info/exclude` are not.
- Files are included whole or not at all.
- Only UTF-8 text is included; files in other encodings are treated as binary.
- Nothing scans for secrets. If a credential is in a tracked file, it will be in the output.

## Contributing

Bug reports with a small directory layout that reproduces the problem are the most helpful, especially for `.gitignore` edge cases and ranking surprises. Pull requests are welcome:

```bash
pip install -e ".[dev]"
pytest
```

Built and maintained by [Narayana Vemburaj](https://github.com/narayana006).

## License

[MIT](LICENSE)
