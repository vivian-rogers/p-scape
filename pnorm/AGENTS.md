# AGENTS.md — `pnorm/` track

Read this first if you're picking up the `pnorm/` subproject. (The parent
`isochrone-metric/` has its own `AGENTS.md` covering a separate track —
they coexist; see [README.md](README.md) for the relationship.)

## What this is, in one paragraph

We compute an *effective L^p exponent* per location in a city by routing
many destinations on a Euclidean ring around each origin and averaging
the network-distance / straight-line-distance ratio (the "mean
circuity"). We invert that ratio against a closed-form integral
$M(p) = (2/\pi) \int_0^{\pi/2} (\cos^p\theta + \sin^p\theta)^{1/p}\,d\theta$
to get a single shape parameter `p(x)` per cell.  `p ≈ 1` ↔ Manhattan
grid, `p ≈ 2` ↔ Euclidean, `p < 1` ↔ cul-de-sac sprawl.  We render the
field as a folium hex-tile heatmap with togglable ring-radius layers.
Six cities are in the catalog; five have been fully run (Austin, NYC,
Houston, SF, Barcelona).

The full mathematical writeup with closed-form derivations and 5-city
findings table lives in **[`docs/methodology.pdf`](docs/methodology.pdf)** —
read that for the why and the math. This file is the *operational*
guide.

## Current state (2026-05-04)

- 6 cities in the catalog: `austin, nyc, houston, sf, chicago, boston, barcelona`.
  5 fully analyzed (chicago and boston are catalog-only — tiles not built).
- Tiles for `austin, nyc, houston, sf, barcelona` exist on this machine
  under `pnorm/data/osrm-{car,foot}-<city>/`. Each city has both car
  and foot graphs.
- Headline result: Barcelona Eixample, walking, r=800 m → median p =
  1.07 (≥90 % of cells beat a perfect Manhattan grid). Austin/Houston
  walking medians sit around 0.89–0.91 at the same scale.
- Latest map renders use `--cmap seismic_r --vmin 0 --vmax 2` (red at
  low p, white at p=1, blue at high p). Files: `data/{city}_{car,foot}_p.html`.
- Rendering convention: the script auto-flips palette direction so
  "good cells stay cool/dark" across cmap × field combinations.

For full session-by-session history see **[`docs/journal.md`](docs/journal.md)**.
Always append a new entry there after a meaningful chunk of work.

## Repo layout (`pnorm/`)

```
AGENTS.md                  # ← you are here
README.md                  # short overview + Vivian heads-up about parallel tracks
docker-compose.yml         # one OSRM stack at a time, parameterized by CITY env var
pyproject.toml             # uv-managed; deps: numpy/scipy/matplotlib/pyproj/folium/branca/...
scripts/
  build_tiles.sh           # CITY=<key> PROFILE=<car|foot> ./build_tiles.sh
  circuity_grid.py         # --city <key> --spacing N --radius R → npz
  circuity_map_multi.py    # multi-radius folium map; supports --field effective_p, --cmap seismic_r/spectral/inferno
  circuity_probe.py        # single-origin diagnostic ring + 3-panel matplotlib plot
  circuity_map.py          # legacy single-layer map (mostly superseded by _multi)
  smoke_test.py            # one-shot OD scatter plot (Framework F sanity check)
src/pnorm/
  __init__.py
  cities.py                # ← THE catalog. {key, name, bbox, utm_epsg, geofabrik_region, center, default_zoom}
  geo.py                   # to_utm/to_lonlat with switchable UTM zone via set_utm_epsg() or use_city()
  grid.py                  # hex grid in UTM
  osrm.py                  # /route + /table client; returns durations, distances, snapped endpoints
  circuity.py              # CircuityResult dataclass + ring_destinations() + circuity_from_origin()
  sampling.py              # stratified OD pair sampler (used by smoke_test.py only)
  lp_inversion.py          # M(p) numerical integration + PCHIP inverse table
docs/
  methodology.{typ,pdf}    # canonical write-up — read this for the math
  journal.md               # append-only session log; newest on top
  plan.md                  # original 6-framework plan from before circuity reframe
  data-acquisition.md      # backend survey from project bootstrap
  setup.md                  # installation + first-run instructions
  figures/m_of_p.png       # M(p) curve + Lp unit balls; embedded in methodology.pdf
data/                      # gitignored — OSM extracts, OSRM tiles, npz, html outputs
```

## How to set up from scratch

1. Install [OrbStack](https://orbstack.dev) (or Docker Desktop).
2. Install uv: `brew install uv`.
3. From `pnorm/`: `uv sync`.
4. Build tiles for at least one city (≈10 min total per city per profile):
   ```sh
   CITY=austin PROFILE=car  ./scripts/build_tiles.sh
   CITY=austin PROFILE=foot ./scripts/build_tiles.sh
   ```
5. Bring up the OSRM stack:
   ```sh
   CITY=austin docker compose up -d   # serves on :5001 (car), :5002 (foot)
   ```
6. Smoke-test with `curl 'http://localhost:5001/route/v1/driving/-97.7431,30.2672;-97.7355,30.2849?overview=false'`.

For the full setup walkthrough see [`docs/setup.md`](docs/setup.md).

## How to run an analysis

A single end-to-end city analysis is roughly:

```sh
# 1. tiles (one-time)
CITY=<key> PROFILE=car  ./scripts/build_tiles.sh
CITY=<key> PROFILE=foot ./scripts/build_tiles.sh

# 2. swap OSRM to that city
docker compose down && CITY=<key> docker compose up -d

# 3. car grid, multiple radii
for r in 1000 2000 3000; do
    uv run python scripts/circuity_grid.py --city <key> \
        --spacing 250 --radius $r --n 48 \
        --url http://localhost:5001 \
        --npz data/<key>_car_r${r}.npz \
        --out data/<key>_car_r${r}.png
done

# 4. foot grid (downtown only — full-bbox foot at 50 m is ~100k cells per layer)
for r in 200 400 800; do
    uv run python scripts/circuity_grid.py --city <key> \
        --bbox=<lon_min,lat_min,lon_max,lat_max> \
        --spacing 50 --radius $r --n 48 \
        --url http://localhost:5002 \
        --npz data/<key>_foot_core_r${r}.npz \
        --out data/<key>_foot_core_r${r}.png
done

# 5. render p-maps (current default cmap)
uv run python scripts/circuity_map_multi.py --city <key> \
    --npz data/<key>_car_r1000.npz data/<key>_car_r2000.npz data/<key>_car_r3000.npz \
    --field effective_p --cmap seismic_r --vmin 0 --vmax 2 \
    --out data/<key>_car_p.html
```

The grid script saves the active UTM EPSG into the npz so the map
script restores it on read — no projection-mixing footguns across
cities.

## How to add a new city

Single dict entry in `src/pnorm/cities.py`. Fields:

- `key` — short identifier used in CLI flags and filenames.
- `name` — display name.
- `bbox` — `(min_lon, min_lat, max_lon, max_lat)`. Crop tight; OSM
  extracts and tile sizes scale super-linearly with bbox area.
- `utm_epsg` — EPSG of the UTM zone covering the bbox. Wrong zone
  silently corrupts distance computations. Look up at
  [epsg.io](https://epsg.io); `32600 + zone_number` for North; `32700
  + zone_number` for South.
- `geofabrik_region` — path under `download.geofabrik.de/`. E.g.
  `north-america/us/california`, `europe/spain`.
- `center` — `(lat, lon)` for folium default view.
- `default_zoom` — folium zoom level.

Then build tiles and run as above. No other code changes needed.

## Methods, briefly (full version in `docs/methodology.pdf`)

- For each origin `x` and ring radius `R`, place N=48 destinations
  uniformly on the Euclidean ring. Issue one OSRM `/table` request
  with `annotations=duration,distance` and `return_snapped=True`.
- Compute `d_euclid` from the **snapped** endpoint coords (not the
  ring point) so the ratio is between actual graph endpoints.
- Drop destinations whose snap offset > 25 % of `R` (graph too sparse
  to give a meaningful probe).
- Aggregate to mean circuity `C(x; R) = mean(d_route / d_euclid)`.
- Invert against `M(p)`:
  - `M(1) = 4/π ≈ 1.273` (Manhattan grid)
  - `M(2) = 1` (Euclidean)
  - `M(∞) = 2√2/π ≈ 0.900` (Chebyshev)
  - General `p` is non-elementary; we evaluate via Simpson and invert
    with PCHIP. Round-trip error ≤ 1e-8.
- Render as folium hex polygons in the city's UTM, colored by `p`.

## Gotchas (things that broke us before)

1. **macOS port 5000 = AirPlay Receiver.** OSRM compose uses 5001/5002
   for this reason. If you change ports, beware AirTunes silently
   intercepting requests with HTTP 403.
2. **Working-directory confusion.** Almost every script needs `cwd =
   pnorm/` to find `pnorm/src/pnorm/...` via `uv run`. Background
   tasks must `cd` explicitly; the parent dir has its own pyproject and
   `uv run` from there will rebuild the wrong env.
3. **One OSRM per city.** `docker-compose.yml` mounts the city's tile
   dir at runtime via `${CITY}` env var. Switching cities = `docker
   compose down && CITY=<new> docker compose up -d`. Don't try to
   serve two cities simultaneously without renaming services.
4. **Snap correction is load-bearing.** Without it, circuity can dip
   below 1 (unphysical). Already implemented in `circuity.py`; if
   you write new sampling code, port the same logic.
5. **UTM zone matters.** UTM 14N (Austin's default) gives ≈ 30 %
   distance distortion in NYC. Always set the city's epsg via
   `use_city()` or pass `--city <key>`.
6. **Extracts are big.** `north-america/us/california-latest.osm.pbf`
   is 1.2 GB; `texas` is 470 MB. They live in `pnorm/data/` and are
   gitignored. Re-runs reuse them.
7. **HTML render size.** A 50 m × 200 m hex grid at NYC scale is
   65k cells → 60 MB HTML. Browsers render it but slowly.

## Conventions for the next agent

- **Append to `docs/journal.md`** after any meaningful work. Newest
  on top, terse format. The journal is the coordination surface
  across sessions.
- **Update `docs/methodology.{typ,pdf}`** if you change the math,
  the inversion, or the cartography defaults. Re-render with
  `typst compile docs/methodology.typ docs/methodology.pdf`.
- **Don't commit `data/`.** It's gitignored. Reproducibility lives
  in scripts that re-fetch and re-build.
- **Don't introduce a third routing engine, file format, or
  language.** OSRM + Python + folium is the stack.
- **Don't break the parent track.** `src/isochrone_metric/` is a
  separate, sibling project on its own pipeline (Valhalla, Riemannian
  ellipse fits). The two coexist intentionally; the parent's `AGENTS.md`
  documents that side.
- **Push frequently.** Commits in this repo follow the conventions
  in the parent's [CONTRIBUTING.md](../CONTRIBUTING.md): imperative
  subject ≤ 72 chars, body explains *why* if non-obvious.

## What we'd do next

The current open list (also in the journal):

1. Re-run Houston with a wider bbox (out to Beltway 8) to capture the
   sprawl signature that's outside the Inner Loop.
2. Add Paris (Haussmann boulevards) and Amsterdam (canal grid) as the
   next European entries.
3. Build a stand-alone comparison-table renderer: load all `<city>_*_r*.npz`
   under `data/`, print a tidy median-p table by city × mode × radius.
4. Allow per-cell rotation `α(x)` jointly fit with `p(x)` so a
   neighborhood organized around a 45° highway doesn't artificially
   read as low p. Generalizes `M(p)` to a rotated 2-D Minkowski
   functional.
5. Reconcile with the Riemannian / ellipse fit on the parent track:
   the ellipse is the special case `p = 2` of an anisotropic
   Minkowski-norm fit that also recovers `p`.
