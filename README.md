# isochrone-metric

Treat travel-time as a Riemannian-style metric on geographic space and study how it deviates from the Euclidean norm.

For a routing function τ(x, y), at each origin x we fit a local quadratic form g(x) such that τ(x, x+v) ≈ √(vᵀ g(x) v) — i.e., we treat isochrones as locally-elliptical geodesic balls. Aggregating g(x) − g_E(x) over Ω gives a global L^p measure of how non-Euclidean the network is, plus a field showing *where* the deviation lives.

First study region: **Austin, TX**. Routing backend: local Valhalla in Docker on an OSM extract.

## Read these next

- [AGENTS.md](AGENTS.md) — repo conventions, how to work here (read first; agentic tools should too).
- [docs/math.md](docs/math.md) — canonical mathematical formulation.
- [docs/journal.md](docs/journal.md) — running session log.
- [docs/decisions/](docs/decisions/) — ADRs for non-obvious choices.
- [CONTRIBUTING.md](CONTRIBUTING.md) — branch / commit / PR conventions.

## Setup

```sh
uv sync
cp .env.example .env
```

Routing infrastructure (Docker + Valhalla + OSM extract) is in progress; see the latest journal entry.
