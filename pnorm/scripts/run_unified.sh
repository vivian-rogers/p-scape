#!/usr/bin/env bash
# End-to-end run for unified-bbox analysis: austin, nyc, dc, venice.
#
# - Retiles NYC (its catalog bbox just changed)
# - Builds tiles for new cities (DC, Venice)
# - Runs car (250 m, r ∈ {1, 2, 3} km) + foot (75 m, r ∈ {0.2, 0.4, 0.8} km)
#   on each city's catalog bbox.
# - Renders all p-maps with seismic_r, vmin=0, vmax=2.
#
# Run from pnorm/. Uses CITY env var on docker compose to swap one city's
# OSRM tiles in at a time.

set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

ts() { date +%H:%M:%S; }

echo "[$(ts)] === Phase 1: rebuild NYC tiles (new bbox) ==="
rm -rf data/osrm-car-nyc data/osrm-foot-nyc data/nyc.osm.pbf
CITY=nyc PROFILE=car  ./scripts/build_tiles.sh
CITY=nyc PROFILE=foot ./scripts/build_tiles.sh

echo "[$(ts)] === Phase 2: build DC tiles ==="
CITY=dc PROFILE=car  ./scripts/build_tiles.sh
CITY=dc PROFILE=foot ./scripts/build_tiles.sh

echo "[$(ts)] === Phase 3: build Venice foot tiles ==="
CITY=venice PROFILE=foot ./scripts/build_tiles.sh

run_grids() {
  local city="$1"
  local has_car="${2:-yes}"
  echo "[$(ts)] -- $city: switch compose --"
  docker compose down >/dev/null 2>&1 || true
  CITY="$city" docker compose up -d $([ "$has_car" = "no" ] && echo "osrm-foot")
  sleep 6
  if [ "$has_car" = "yes" ]; then
    for r in 1000 2000 3000; do
      uv run python scripts/circuity_grid.py --city "$city" \
        --spacing 250 --radius "$r" --n 48 \
        --url http://localhost:5001 \
        --npz "data/${city}_car_r${r}.npz" \
        --out "data/${city}_car_r${r}.png" 2>&1 | grep -E "grid:|saved" | head -2
    done
  fi
  for r in 200 400 800; do
    uv run python scripts/circuity_grid.py --city "$city" \
      --spacing 75 --radius "$r" --n 48 \
      --url http://localhost:5002 \
      --npz "data/${city}_foot_r${r}.npz" \
      --out "data/${city}_foot_r${r}.png" 2>&1 | grep -E "grid:|saved" | head -2
  done
}

render_maps() {
  local city="$1"
  local has_car="${2:-yes}"
  if [ "$has_car" = "yes" ]; then
    uv run python scripts/circuity_map_multi.py --city "$city" \
      --npz "data/${city}_car_r1000.npz" "data/${city}_car_r2000.npz" "data/${city}_car_r3000.npz" \
      --out "data/${city}_car_p.html" \
      --field effective_p --cmap seismic_r --vmin 0 --vmax 2 2>&1 | tail -1
  fi
  uv run python scripts/circuity_map_multi.py --city "$city" \
    --npz "data/${city}_foot_r200.npz" "data/${city}_foot_r400.npz" "data/${city}_foot_r800.npz" \
    --out "data/${city}_foot_p.html" \
    --field effective_p --cmap seismic_r --vmin 0 --vmax 2 2>&1 | tail -1
}

echo "[$(ts)] === Phase 4: grids ==="
run_grids austin yes
run_grids nyc yes
run_grids dc yes
run_grids venice no

echo "[$(ts)] === Phase 5: render maps ==="
render_maps austin yes
render_maps nyc yes
render_maps dc yes
render_maps venice no

echo "[$(ts)] === done ==="
