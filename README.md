# repo-to-context

> Pack a code repository into LLM-ready context: gitignore-aware, token-budgeted, importance-ranked.

**Status:** 🚧 Early stage — design and roadmap published, implementation in progress. Stars, issues and ideas welcome.

## Why

Feeding a codebase to an LLM means either blowing the context window or hand-picking files.

## Planned features

- [ ] Respects .gitignore and custom ignore rules
- [ ] Token budget with importance ranking (entrypoints, configs, recently changed files first)
- [ ] Output as Markdown, XML or JSON
- [ ] Optional AGENTS.md skeleton generation
- [ ] File tree summary and per-file token counts

## Intended usage

```
repo-to-context . --budget 120k --format xml > context.xml
```

_The interface above is the target design and may change._

## Roadmap

1. Core implementation of the first feature set
2. Examples and tests
3. CI and first tagged release
4. Docs and integrations

## Contributing

Contributions are welcome. Open an issue to discuss an idea or pick an unchecked item from the feature list.

## License

[MIT](LICENSE)
