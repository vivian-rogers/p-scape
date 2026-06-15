#!/usr/bin/env bash
# Full-catalog rerun on the square-grid + 4-metric overhaul. Per city:
#   - tear down any running OSRM
#   - re-crop city PBF with BUFFER_M=17000 (car) / 2000 (foot) so the 16 km
#     car ring stays inside the routable graph
#   - osrm-extract / partition / customize
#   - bring up city OSRM
#   - 3 car grids @ {1, 4, 16} km, 4 foot grids @ {0.2, 0.4, 0.8, 1.6} km
#     using --grid-type square --tile-buffer-m, writing to <city>_<mode>_sq_r<R>.npz
# After every city: rebuild data/explorer.html.
#
# Legacy <city>_<mode>_r<R>.npz files are left in place — build_explorer.py
# prefers _sq_ when present and falls back to legacy otherwise, so cities
# that fail or are skipped here keep their old layers visible.
#
# Run from pnorm/:
#   caffeinate -i nohup ./scripts/rerun_all_sq.sh > /dev/null 2>&1 &
#
# Designed for overnight / multi-day execution. Expect ~1-3 hr per medium city,
# ~3-6 hr per large city. NYC and Lansing already done in pilots — skipped.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/rerun_all_sq_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

# (city_key, has_car). NYC + Lansing already piloted; everything else is queued.
# Boston (catalog-only, never built) and Venice (foot-only, no car routing
# possible on the islands) are included with explicit has_car flags.
CITIES=(
  "austin       yes"
  "houston      yes"
  "sf           yes"
  "la           yes"
  "chicago      yes"
  "boston       yes"
  "barcelona    yes"
  "paris        yes"
  "dc           yes"
  "seattle      yes"
  "east_bay     yes"
  "bruges       yes"
  "karlsruhe    yes"
  "rome         yes"
  "tokyo        yes"
  "mexico_city  yes"
  "brasilia     yes"
  "london_on    yes"
  "villages     yes"
  "venice       no"
)

CAR_RADII=(1000 4000 16000)
FOOT_RADII=(200 400 800 1600)
CAR_SPACING=250
FOOT_SPACING=75
N_DESTS=48
CAR_BUFFER_M=17000
FOOT_BUFFER_M=2000

wait_for_osrm() {
  local port="$1" tries=60
  for i in $(seq 1 "$tries"); do
    if curl -sf -o /dev/null --max-time 3 \
        "http://localhost:${port}/nearest/v1/driving/0,0" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "[$(ts)]   !! OSRM on :${port} never responded after $((tries*2))s"
  return 1
}

run_city() {
  local city="$1" has_car="$2"
  echo
  echo "================================================================"
  echo "[$(ts)] CITY: $city  (car=$has_car)"
  echo "================================================================"

  docker compose down >/dev/null 2>&1 || true

  # Clear caches so tile build picks up the buffered bbox.
  rm -rf "data/${city}.osm.pbf" "data/${city}_buf"*.osm.pbf \
         "data/${city}-with-parks.osm.pbf" \
         "data/osrm-car-${city}" "data/osrm-foot-${city}"

  if [ "$has_car" = "yes" ]; then
    echo "[$(ts)] === $city: building car tiles (buffer ${CAR_BUFFER_M} m) ==="
    CITY=$city PROFILE=car BUFFER_M=$CAR_BUFFER_M ./scripts/build_tiles.sh \
      || { echo "[$(ts)] !! $city car tiles failed; skipping"; return; }
  fi

  echo "[$(ts)] === $city: building foot tiles (buffer ${FOOT_BUFFER_M} m) ==="
  CITY=$city PROFILE=foot BUFFER_M=$FOOT_BUFFER_M ./scripts/build_tiles.sh \
    || { echo "[$(ts)] !! $city foot tiles failed; skipping"; return; }

  echo "[$(ts)] === $city: starting OSRM ==="
  if [ "$has_car" = "yes" ]; then
    CITY=$city docker compose up -d
    wait_for_osrm 5001 || { echo "[$(ts)] !! $city car OSRM down; skip"; return; }
  else
    CITY=$city docker compose up -d osrm-foot
  fi
  wait_for_osrm 5002 || { echo "[$(ts)] !! $city foot OSRM down; skip"; return; }

  if [ "$has_car" = "yes" ]; then
    for r in "${CAR_RADII[@]}"; do
      local npz="data/${city}_car_sq_r${r}.npz"
      local png="data/${city}_car_sq_r${r}.png"
      echo "[$(ts)] $city car r=${r}"
      uv run python scripts/circuity_grid.py --city "$city" \
            --grid-type square \
            --spacing "$CAR_SPACING" --radius "$r" --n "$N_DESTS" \
            --tile-buffer-m "$CAR_BUFFER_M" \
            --url http://localhost:5001 --npz "$npz" --out "$png" \
            && echo "[$(ts)]   ok" || echo "[$(ts)]   !! $city car r=${r} failed"
    done
  fi

  for r in "${FOOT_RADII[@]}"; do
    local npz="data/${city}_foot_sq_r${r}.npz"
    local png="data/${city}_foot_sq_r${r}.png"
    echo "[$(ts)] $city foot r=${r}"
    uv run python scripts/circuity_grid.py --city "$city" \
          --grid-type square \
          --spacing "$FOOT_SPACING" --radius "$r" --n "$N_DESTS" \
          --tile-buffer-m "$FOOT_BUFFER_M" \
          --url http://localhost:5002 --npz "$npz" --out "$png" \
          && echo "[$(ts)]   ok" || echo "[$(ts)]   !! $city foot r=${r} failed"
  done
}

echo "[$(ts)] === rerun_all_sq starting; log → $LOG ==="

if ! docker info >/dev/null 2>&1; then
  echo "[$(ts)] !! docker not running."; exit 1
fi

for line in "${CITIES[@]}"; do
  set -- $line
  run_city "$1" "$2"

  # Rebuild explorer.html after each city so partial progress is visible.
  echo "[$(ts)] === $1 done; rebuilding explorer.html ==="
  uv run python scripts/build_explorer.py 2>&1 | tail -3
done

echo
echo "[$(ts)] === all cities done; bringing OSRM down ==="
docker compose down >/dev/null 2>&1 || true

echo "[$(ts)] === final explorer rebuild ==="
uv run python scripts/build_explorer.py | tail -5

echo "[$(ts)] === finished. summary log → $LOG ==="
