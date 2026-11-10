# repo-to-context

Pack a code repository into LLM-ready context: gitignore-aware, token-budgeted, importance-ranked.

> **Project status: planning. There is no working code in this repository yet.**
> This README describes what the project will do. Nothing below can be installed or run today.
> Features are ticked off in the checklist as they are built.

## What it is

A command-line tool.

**The problem it solves:** Feeding a codebase to an LLM means either blowing the context window or hand-picking files.

## Who it is for

Developers who want to give an LLM an accurate picture of a codebase without exceeding its context window.

## How it will work

1. You point the tool at a repository and give it a token budget.
2. It skips ignored files, ranks the rest by importance and fits as much as the budget allows.
3. It writes one file (Markdown, XML or JSON) with a file tree and the selected contents, ready to paste or pipe into a model.

## Planned features

Unticked items are not built yet.

- [ ] Respects .gitignore and custom ignore rules
- [ ] Token budget with importance ranking (entrypoints, configs, recently changed files first)
- [ ] Output as Markdown, XML or JSON
- [ ] Optional AGENTS.md skeleton generation
- [ ] File tree summary and per-file token counts

## Planned usage

This is the intended interface, shown so you can judge the design. **It does not work yet**, and names may change before the first release.

```bash
repo-to-context . --budget 120k --format xml > context.xml
```

## Contributing

Feedback on the design is the most useful contribution right now. Open an issue to suggest a feature, question an approach or describe your use case. Code contributions are welcome once the first version lands.

## License

[MIT](LICENSE)
