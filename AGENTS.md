# AGENTS.md

Guide for both humans and agentic coding tools (Claude Code, Codex, Cursor, etc.) working in this repo. `CLAUDE.md` is a symlink to this file — edit one, both update.

## What this repo is

A research project: derive a Riemannian-style "effective-time" metric on geographic space from routing isochrones, and compare it to the Euclidean (great-circle) norm. See [docs/math.md](docs/math.md) for the formulation.

Target region for the first pass: **Austin, TX**. Routing backend: **local Valhalla** in Docker on an OSM extract — local-only is a hard requirement (we want to fire isochrone calls without rate limits or cost).

## Repo layout

```
AGENTS.md / CLAUDE.md     # this file — read first
README.md                 # short overview, points here
CONTRIBUTING.md           # branch / commit / PR conventions
pyproject.toml            # uv-managed Python project, deps pinned via uv.lock
src/isochrone_metric/     # the package
notebooks/                # exploratory work; not the source of truth
data/                     # gitignored — OSM extracts, cached isochrones, tiles
docs/
  math.md                 # mathematical formulation (canonical)
  journal.md              # running session log — APPEND each session
  decisions/              # ADRs — short rationale for non-obvious choices
```

## Conventions

- **Python**: 3.11+, managed by `uv`. To set up: `uv sync`. To run: `uv run python -m isochrone_metric ...` or `uv run jupyter lab`.
- **Style**: ruff defaults. No comments unless the *why* is non-obvious.
- **Notebooks** are scratch. Anything worth keeping graduates into `src/isochrone_metric/`.
- **Data is gitignored.** Never commit OSM extracts, Valhalla tiles, isochrone caches, or `.env`. Reproducibility lives in scripts that re-fetch.
- **Commits**: imperative subject, ≤72 chars, body explains why if non-obvious. Conventional-Commits prefixes (`feat:`, `fix:`, `docs:`, `chore:`) are welcome but not required.
- **Branches**: `main` is the trunk. Push small, low-risk changes directly. Open a PR for anything touching the math, the routing setup, or external interfaces.

## Workflow expectations for agents

1. **Before working**, skim `docs/journal.md` (last 1–2 entries) and any open ADRs. Saves re-deriving context.
2. **While working**, prefer editing existing files; don't proliferate new top-level files without a reason.
3. **After a meaningful chunk of work**, append to `docs/journal.md`: date, who/what tool, what changed, what's next, any blockers. Keep entries terse — bullets are fine.
4. If you make a non-obvious design choice, add a numbered ADR in `docs/decisions/`. Use the smallest possible template — see existing ones.
5. The math doc is canonical. If code and `docs/math.md` disagree, fix one of them in the same PR; don't let them drift.

## Running things

```sh
uv sync                                  # install deps
cp .env.example .env                     # one-time
uv run python -c "import isochrone_metric; print(isochrone_metric.__version__)"
```

Routing: TBD. Valhalla via Docker on an Austin OSM extract. Setup script will land in `scripts/` and be referenced here.

## Who's working here

- Adam (`AFriendinNeed1903`) — repo owner.
- Vivian Rogers (`vivian-rogers`) — collaborator.
- Plus whichever coding agents either of us is running. Multiple agents may touch this repo in parallel; the journal is the coordination surface.
