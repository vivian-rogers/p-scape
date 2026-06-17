#!/usr/bin/env bash
# Champaign–Urbana pilot on the K=48 jittered MC pipeline. First-time city,
# so this builds OSRM tiles from the Illinois extract before running grids.
# All 7 grids end-to-end ≈ 35-50 min (size ~25-30k foot cells, similar to Lansing).
#
# Run from pnorm/:
#   caffeinate -d -i -s -u bash ./scripts/rerun_champaign_sq.sh

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/rerun_champaign_sq_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

CITY=champaign
CAR_RADII=(1000 4000 16000)
FOOT_RADII=(200 400 800 1600)
CAR_SPACING=250
FOOT_SPACING=75
N_DESTS=48
CAR_BUFFER_M=17000
FOOT_BUFFER_M=2000
CONCURRENCY=16

wait_for_osrm() {
  local port="$1" tries=60
  for i in $(seq 1 "$tries"); do
    if curl -sf -o /dev/null --max-time 3 \
        "http://localhost:${port}/nearest/v1/driving/0,0" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

echo "[$(ts)] === rerun_champaign_sq starting; log → $LOG ==="

if ! docker info >/dev/null 2>&1; then
  echo "[$(ts)] !! docker not running."; exit 1
fi

docker compose down >/dev/null 2>&1 || true

# Fresh city — make sure no stale crops are lying around.
rm -rf data/${CITY}.osm.pbf data/${CITY}_buf*.osm.pbf \
       data/osrm-car-${CITY} data/osrm-foot-${CITY}

echo "[$(ts)] === building car tiles (buffer ${CAR_BUFFER_M} m) ==="
CITY=$CITY PROFILE=car BUFFER_M=$CAR_BUFFER_M ./scripts/build_tiles.sh \
  || { echo "[$(ts)] !! car tiles failed"; exit 1; }

echo "[$(ts)] === building foot tiles (buffer ${FOOT_BUFFER_M} m) ==="
CITY=$CITY PROFILE=foot BUFFER_M=$FOOT_BUFFER_M ./scripts/build_tiles.sh \
  || { echo "[$(ts)] !! foot tiles failed"; exit 1; }

echo "[$(ts)] === starting ${CITY} OSRM (--threads 8) ==="
CITY=$CITY docker compose up -d
wait_for_osrm 5001 || { echo "[$(ts)] !! car OSRM down"; exit 1; }
wait_for_osrm 5002 || { echo "[$(ts)] !! foot OSRM down"; exit 1; }

for r in "${CAR_RADII[@]}"; do
  npz="data/${CITY}_car_sq_r${r}.npz"; png="data/${CITY}_car_sq_r${r}.png"
  echo "[$(ts)] ${CITY} car r=${r}"
  uv run python scripts/circuity_grid.py --city "$CITY" \
        --grid-type square \
        --spacing "$CAR_SPACING" --radius "$r" --n "$N_DESTS" \
        --tile-buffer-m "$CAR_BUFFER_M" \
        --concurrency "$CONCURRENCY" \
        --url http://localhost:5001 --npz "$npz" --out "$png" \
        && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
done

for r in "${FOOT_RADII[@]}"; do
  npz="data/${CITY}_foot_sq_r${r}.npz"; png="data/${CITY}_foot_sq_r${r}.png"
  echo "[$(ts)] ${CITY} foot r=${r}"
  uv run python scripts/circuity_grid.py --city "$CITY" \
        --grid-type square \
        --spacing "$FOOT_SPACING" --radius "$r" --n "$N_DESTS" \
        --tile-buffer-m "$FOOT_BUFFER_M" \
        --concurrency "$CONCURRENCY" \
        --url http://localhost:5002 --npz "$npz" --out "$png" \
        && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
done

docker compose down >/dev/null 2>&1 || true

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -3

echo "[$(ts)] === finished. ==="
