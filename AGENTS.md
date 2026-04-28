# AGENTS.md

Guide for both humans and agentic coding tools (Claude Code, Codex, Cursor, etc.) working in this repo. `CLAUDE.md` is a symlink to this file — edit one, both update.

## What this repo is

A quantitative urban-analysis project. We compute lots of isochrones across a city and characterize how the road network deviates from straight-line distance: where it's anisotropic (highway corridors), where it's slow, where "close on a map" doesn't mean "close in time."

Method in one sentence: at each origin, fit an ellipse to the isochrone, extract local effective speeds + an anisotropy ratio, aggregate over a grid into maps + a single L^p summary. See [docs/math.md](docs/math.md) for the details.

Genre: urban planning / spatial analysis with real math. The collaborators are quant-fluent (one EE, one cities nerd) — math.md can be technical. Public-facing framing (this file, README) leads with the *city* question, not the geometry.

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
./scripts/fetch_extract.sh               # download the Austin OSM extract
docker compose up -d                     # bring up Valhalla on :8002 (first start builds tiles)
uv run python scripts/run_austin_grid.py --n 7 --minutes 10
uv run python scripts/plot_grid.py data/results/austin_7x7_10min.jsonl
```

Outputs go to `data/results/` (gitignored): a JSONL of per-origin fits and PNGs under `plots/`.

## Who's working here

- Adam (`AFriendinNeed1903`) — repo owner.
- Vivian Rogers (`vivian-rogers`) — collaborator.
- Plus whichever coding agents either of us is running. Multiple agents may touch this repo in parallel; the journal is the coordination surface.
