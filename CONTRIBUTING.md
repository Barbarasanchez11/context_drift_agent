# Contributing to Context Drift Agent

Thank you for your interest in contributing. This project is open-source (Apache 2.0)
and welcomes bug reports, feature requests, and pull requests.

## Getting Started

```bash
git clone https://github.com/Barbarasanchez11/context-drift-agent
cd context-drift-agent
cp .env.example .env   # add your API keys
uv sync --all-extras
```

Run tests:
```bash
uv run pytest
uv run ruff check .
uv run pyright
```

## Before You Open a PR

1. **Tests pass** — `uv run pytest` green.
2. **Linting passes** — `uv run ruff check .` clean.
3. **No secrets committed** — check `.env` is not staged.
4. **One concern per PR** — keep scope tight; large refactors block review.

## Architecture Constraints

Please read [`DECISIONS.md`](DECISIONS.md) before proposing changes to:
- How metadata is written back to DataHub (Decision 006)
- How schema changes are detected (Decision 007)
- What this project does vs. DataHub Cloud Context Platform (Decision 008)

These decisions exist for reasons — if you disagree with one, open an issue first.

## Development Workflow

```
main          — stable, released
feature/*     — new features, branched from main
fix/*         — bug fixes
```

PRs go to `main`. Use the PR template and fill in the checklist.

## Code Style

- Python 3.11+, typed hints everywhere
- `from __future__ import annotations` at the top of every file
- `uv run ruff format .` before committing
- No comments that explain *what* the code does — only *why* when non-obvious

## Reporting Issues

Use the issue templates in `.github/ISSUE_TEMPLATE/`. For security issues, see
[`SECURITY.md`](SECURITY.md).
