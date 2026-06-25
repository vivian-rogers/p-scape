#!/usr/bin/env bash
# Three jobs in one overnight bundle:
#   1. DC repair       (re-run K=48 grids; OSRM tiles already valid)
#   2. Barcelona repair (same)
#   3. SF as new K=48 city (existing tiles already buf17000 + buf2000)
#
# All three already have OSRM tile dirs on disk so we skip the tile-build
# step. The previous fast-queue run produced empty/sparse layers for DC
# and Barcelona that the manual /route check (post-incident) showed was a
# transient run-time failure, not a tile problem. Rerun = fix.
#
# Single bundled commit + Vercel deploy at the end.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/fix_dc_barcelona_add_sf_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

CAR_RADII=(1000 4000 16000)
FOOT_RADII=(200 400 800 1600)
CAR_SPACING=250
FOOT_SPACING=75
N_DESTS=48
CAR_BUFFER_M=17000
FOOT_BUFFER_M=2000
CONCURRENCY=16

QUEUE=(dc barcelona sf)

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

run_city() {
  local CITY="$1"
  echo
  echo "================================================================"
  echo "[$(ts)] CITY: $CITY"
  echo "================================================================"

  if [ ! -d "data/osrm-car-${CITY}" ] && [ ! -d "data/osrm-foot-${CITY}" ]; then
    echo "[$(ts)] !! no OSRM tile dirs for $CITY — skipping"
    return
  fi

  docker compose down >/dev/null 2>&1 || true
  CITY=$CITY docker compose up -d
  HAS_CAR="yes"
  if ! wait_for_osrm 5001; then
    echo "[$(ts)] !! $CITY car OSRM not up; foot-only"
    HAS_CAR="no"
  fi
  wait_for_osrm 5002 || { echo "[$(ts)] !! $CITY foot OSRM down; skip"; return; }

  if [ "$HAS_CAR" = "yes" ]; then
    for r in "${CAR_RADII[@]}"; do
      npz="data/${CITY}_car_sq_r${r}.npz"; png="data/${CITY}_car_sq_r${r}.png"
      echo "[$(ts)] $CITY car r=${r}"
      uv run python scripts/circuity_grid.py --city "$CITY" \
            --grid-type square \
            --spacing "$CAR_SPACING" --radius "$r" --n "$N_DESTS" \
            --tile-buffer-m "$CAR_BUFFER_M" \
            --concurrency "$CONCURRENCY" \
            --url http://localhost:5001 --npz "$npz" --out "$png" \
            && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
    done
  fi

  for r in "${FOOT_RADII[@]}"; do
    npz="data/${CITY}_foot_sq_r${r}.npz"; png="data/${CITY}_foot_sq_r${r}.png"
    echo "[$(ts)] $CITY foot r=${r}"
    uv run python scripts/circuity_grid.py --city "$CITY" \
          --grid-type square \
          --spacing "$FOOT_SPACING" --radius "$r" --n "$N_DESTS" \
          --tile-buffer-m "$FOOT_BUFFER_M" \
          --concurrency "$CONCURRENCY" \
          --url http://localhost:5002 --npz "$npz" --out "$png" \
          && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
  done

  docker compose down >/dev/null 2>&1 || true
}

echo "[$(ts)] === fix_dc_barcelona_add_sf starting; queue: ${QUEUE[*]} ==="
echo "[$(ts)] === waiting for any in-flight jobs to finish ==="
while pgrep -f "circuity_grid\.py\|add_madison\.sh\|k48_overnight_push\.sh\|nyc_foot_redo\.sh" >/dev/null; do
  sleep 30
done
echo "[$(ts)] === queue clear; pausing 10 s for docker to settle ==="
sleep 10

for CITY in "${QUEUE[@]}"; do
  run_city "$CITY"
done

echo
echo "[$(ts)] === all queued cities done ==="

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -10

cd ..
git add pnorm/data/explorer.html pnorm/scripts/fix_dc_barcelona_add_sf.sh
git diff --cached --quiet || git commit -m "Repair DC + Barcelona K=48 layers; add SF on K=48

DC and Barcelona K=48 grids previously landed empty / sparse (0 valid
cells in barcelona foot all-radii, dc car r=16000, etc). Manual /route
test against the OSRM tile dirs after the incident showed the tiles
themselves were valid — the failure was transient at run time
(probably docker memory pressure or a queue collision). Reran K=48
jittered MC against the existing tile dirs; both cities now have
proper coverage.

SF is the smallest of the four remaining sprawl-five cities. Full
K=48 run on the existing buf17000 + buf2000 tiles, no rebuild.

After this push the remaining K=1 cities are chicago, houston, la —
each their own dedicated overnight.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === fix_dc_barcelona_add_sf finished ==="
