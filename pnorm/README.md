# pnorm

OSRM-driven pipeline that derives an effective L^p exponent at every
location in a city. We **promote p to a free parameter** of the local
norm rather than committing to a Riemannian (p = 2) fit.

## Quickstart

```sh
uv sync
CITY=austin PROFILE=car  ./scripts/build_tiles.sh   # ~5–15 min, one-time per (city, profile)
CITY=austin PROFILE=foot ./scripts/build_tiles.sh
CITY=austin docker compose up -d                    # serves on :5001 (car), :5002 (foot)
uv run python scripts/smoke_test.py
```

Full setup: [docs/setup.md](docs/setup.md).

## Cities

City presets live in [`src/pnorm/cities.py`](src/pnorm/cities.py). Each carries a bbox,
the right UTM zone for distance work, the Geofabrik region path that contains it, and
a default folium map view.

| Key      | Region         | UTM    | Bbox-ish coverage                                |
|----------|----------------|--------|--------------------------------------------------|
| austin   | Texas          | 14N    | metro core: airport → Parmer, Bee Cave → SH-130  |
| nyc      | New York       | 18N    | Manhattan + adjacent Bk / Qns / South Bronx      |
| houston  | Texas          | 15N    | downtown + Inner Loop                             |
| sf       | California     | 10N    | SF proper (peninsula tip)                         |
| chicago  | Illinois       | 16N    | Loop + North Side                                 |
| boston   | Massachusetts  | 19N    | Boston proper                                     |

Switch via `CITY=<key>` on `build_tiles.sh` and `docker compose up`, and `--city <key>`
on `circuity_grid.py` / `circuity_map_multi.py`.  Only one city's tiles are mounted by
the OSRM containers at a time — `docker compose down` then bring up with the new CITY
to switch.

Adding a city: append an entry to `cities.py` (key, bbox, UTM EPSG, Geofabrik region path,
folium center+zoom).  No other code changes needed.

## Docs

- [docs/plan.md](docs/plan.md) — six candidate frameworks (A–F), ranked.
- [docs/data-acquisition.md](docs/data-acquisition.md) — backend survey; why we landed on OSRM.
- [docs/setup.md](docs/setup.md) — Docker + OSRM + Austin tile build.
- [docs/journal.md](docs/journal.md) — running log.

_(An earlier sibling Riemannian-ellipse-fit track lived at the parent
repo level; it was removed in May 2026. Earlier commits in this repo's
history retain that code if you ever need it.)_
