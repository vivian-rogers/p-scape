# Contributing

Short version: this is a small research repo. Be quick, don't over-process.

## Branching

- `main` is the trunk and is usually what runs.
- For small, low-risk changes (docs, fixing a typo, a small isolated function), push directly to `main`.
- For anything that touches the math, the routing setup, or external-facing interfaces, open a PR so the other person can react before it lands.
- Branch names: `kebab-case` describing the change (`fit-tensor-lstsq`, `valhalla-docker-setup`).

## Commits

- Imperative subject, ≤72 chars (`add tensor-fit smoke test`, not `added a smoke test`).
- Body explains *why* if the *what* isn't obvious from the diff.
- Don't squash if the intermediate commits are independently meaningful; squash if they're "fix typo" / "wip".

## Code style

- `ruff` defaults. `uv run ruff check .` and `uv run ruff format .` before pushing if you remember.
- Default to no comments. Add one when the *why* is non-obvious.
- Prefer editing existing files over creating new ones.

## Where things go

- Algorithmic / library code → `src/isochrone_metric/`.
- One-off scripts (downloading extracts, building tiles, running an experiment end-to-end) → `scripts/`.
- Exploratory work → `notebooks/`. Don't import notebooks from library code.
- Anything heavy or generated → `data/` (gitignored). Reproducibility lives in scripts.

## Updating docs

- Append to `docs/journal.md` after a session — even a 4-line entry helps the next session.
- If you make a non-obvious design choice, drop a numbered ADR in `docs/decisions/`.
- If the math model changes, update `docs/math.md` in the same PR as the code change.

## Working alongside agents

Multiple agents (Claude Code, Codex, Cursor) may be in this repo at different times. The journal is the coordination surface; if you finished a chunk, write it down so the next session — agent or human — can pick up cold.
