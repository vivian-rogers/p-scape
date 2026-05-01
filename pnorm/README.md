# pnorm

Sibling experiment to the parent `isochrone-metric` project. Same raw idea (travel-time geometry on a city), but this track **promotes p to a free parameter** of the local norm rather than committing to a Riemannian (p = 2) fit.

## Quickstart

```sh
uv sync
./scripts/build_tiles.sh        # ~5–15 min, one-time
docker compose up -d osrm
uv run python scripts/smoke_test.py
```

Full setup: [docs/setup.md](docs/setup.md).

## Docs

- [docs/plan.md](docs/plan.md) — six candidate frameworks (A–F), ranked.
- [docs/data-acquisition.md](docs/data-acquisition.md) — backend survey; why we landed on OSRM.
- [docs/setup.md](docs/setup.md) — Docker + OSRM + Austin tile build.
- [docs/journal.md](docs/journal.md) — running log.

Parent project's math doc (`../docs/math.md`) is **not** canonical here.
