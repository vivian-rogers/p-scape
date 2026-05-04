# Setup

Local OSRM stack for τ(x, y) and d_route(x, y) queries. One city loaded
at a time, swapped via `CITY=<key>`. The catalog of supported keys
lives in [`../src/pnorm/cities.py`](../src/pnorm/cities.py); see
[`AGENTS.md`](../AGENTS.md) for the operational handoff.

## One-time prerequisites

1. Install [OrbStack](https://orbstack.dev) (Docker runtime for macOS).
   Start it — `docker info` should work.
2. Install `uv`:
   ```sh
   brew install uv
   ```
3. From `pnorm/`:
   ```sh
   uv sync
   chmod +x scripts/build_tiles.sh
   ```

## Build tiles for a city

`build_tiles.sh` takes two env vars:

- `CITY` — key from the catalog (e.g. `austin`, `nyc`, `barcelona`)
- `PROFILE` — `car` | `foot` | `bicycle`

```sh
CITY=austin PROFILE=car  ./scripts/build_tiles.sh
CITY=austin PROFILE=foot ./scripts/build_tiles.sh
```

The script downloads the right Geofabrik regional extract (cached after
first run), crops it to the city's bbox via `osmium-tool` (host-native
or via Docker), then runs `osrm-extract → osrm-partition → osrm-customize`
for the requested profile. Output:

```
pnorm/data/
  <region>-latest.osm.pbf       # Geofabrik extract, reused across cities in same region
  <city>.osm.pbf                # cropped to city bbox
  osrm-car-<city>/<city>.osrm*  # car tiles
  osrm-foot-<city>/<city>.osrm* # foot tiles
```

Approximate timing: 1–2 min download (cached), 30 s crop, 1–3 min car
extract/partition/customize, 3–5 min foot.

## Run the OSRM stack

```sh
CITY=austin docker compose up -d
```

This starts two containers:
- `pnorm-osrm-car` on `localhost:5001` (mounting `data/osrm-car-${CITY}`)
- `pnorm-osrm-foot` on `localhost:5002` (mounting `data/osrm-foot-${CITY}`)

Verify:

```sh
curl 'http://localhost:5001/route/v1/driving/-97.7431,30.2672;-97.7355,30.2849?overview=false' | jq .routes[0].duration
```

Should return a number of seconds (downtown Austin → UT, ~5 min).

To switch cities:

```sh
docker compose down
CITY=nyc docker compose up -d
```

## Run the analysis

Smallest end-to-end check:

```sh
uv run python scripts/smoke_test.py --url http://localhost:5001
```

Real run (per the [`AGENTS.md`](../AGENTS.md) recipe):

```sh
uv run python scripts/circuity_grid.py --city austin \
    --spacing 250 --radius 1000 --n 48 \
    --url http://localhost:5001 \
    --npz data/austin_car_r1000.npz \
    --out data/austin_car_r1000.png

uv run python scripts/circuity_map_multi.py --city austin \
    --npz data/austin_car_r1000.npz \
    --field effective_p --cmap seismic_r --vmin 0 --vmax 2 \
    --out data/austin_car_p.html
open data/austin_car_p.html
```

## Troubleshooting

- **macOS port 5000 returns 403 / Server: AirTunes**. AirPlay Receiver
  squats port 5000. We bind to `:5001` and `:5002` for this reason.
  If you change ports, beware AirTunes silently intercepting.
- **`docker compose up` fails with "Bind for 0.0.0.0:5001 failed: port
  is already allocated"**. An old container is still running. `docker
  compose down`, then up.
- **`osmium` Docker image won't pull**. Install host-native via
  `brew install osmium-tool`; the build script prefers it when present.
- **`osrm-extract` OOMs on large regions**. Crop the bbox tighter
  (smaller bbox in `cities.py`), or give Docker more RAM in OrbStack
  settings.
- **uv installs the wrong deps / parent project**. Make sure you're in
  `pnorm/` when you run `uv sync` or `uv run`. The parent
  `isochrone-metric/` directory has its own pyproject.

## Customizing

Different region / bbox: add an entry to [`../src/pnorm/cities.py`](../src/pnorm/cities.py)
following the existing pattern. No other code changes needed.

Different profile: edit the `PROFILE` env var on `build_tiles.sh`.
OSRM ships `car.lua`, `foot.lua`, and `bicycle.lua` profiles in the
container at `/opt/`.
