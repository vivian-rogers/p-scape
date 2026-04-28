# isochrone-metric

How much — and *where* — does getting around a city diverge from straight-line distance?

Every point in a city has a 10-minute drive isochrone around it. It's not a circle: it's stretched along highways, pinched by rivers, sliced by one-way grids, dilated by hills. We treat that shape as data. At each origin, we fit an **ellipse to the isochrone** and read off (a) the effective speed in each direction and (b) how anisotropic the network is at that point. Sweep across a grid and you get two fields over the city — an effective-speed map and an anisotropy map — plus a single L^p number summarizing how non-Euclidean the network is overall.

The point: get from "isochrone maps look cool" to a quantitative description of urban form that's directly comparable across cities, modes, and time.

## What this is good for

Things this lets us measure or argue about:

- **Where the network bends space**: corridor effects of major highways, river crossings, transit deserts; neighborhoods that are "close on a map but far in time."
- **Network non-isotropy as a scalar**: a single L^p number summarizing how much a city's effective metric deviates from Euclidean. Comparable across cities and over time.
- **Pre/post**: rerun after a road diet, a new highway, a transit line opening; the difference field is the effect.
- **Multimodal**: same pipeline against drive vs. transit vs. bike isochrones — anisotropy of *each*, plus the gap between them.

First study region: **Austin, TX**. Routing backend: **local Valhalla** in Docker on an OSM extract. Local because we want unlimited isochrones without rate limits or per-call cost.

## Read these next

- [AGENTS.md](AGENTS.md) — repo conventions, how to work here (read first; agentic tools should too).
- [docs/math.md](docs/math.md) — the ellipse fit, L^p aggregation, what's fragile.
- [docs/journal.md](docs/journal.md) — running session log.
- [docs/decisions/](docs/decisions/) — short ADRs for non-obvious choices.
- [CONTRIBUTING.md](CONTRIBUTING.md) — branch / commit / PR conventions.

## Setup

```sh
uv sync
cp .env.example .env
./scripts/fetch_extract.sh   # downloads the Austin OSM extract
docker compose up -d         # first start builds Valhalla tiles (a few minutes)
```

Then `http://localhost:8002/isochrone` is the routing endpoint. See `src/isochrone_metric/routing.py` for the Python wrapper, `src/isochrone_metric/tensor.py` for the per-point ellipse fit.
