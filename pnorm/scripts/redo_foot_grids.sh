#!/usr/bin/env bash
# Re-run Katy + DC foot grids with OSRM restart between each radius.
# The previous run died: both cities' first foot grid (r=200) partially
# worked, then r=400/800/1600 returned all-dropped data (n_valid=0/48
# for everything). Confirmed OSRM tiles are valid via manual /route test
# after the run — the container went into a bad state under sustained
# K=48 load. Restarting it between each grid is the workaround.
#
# Single bundled commit + Vercel deploy at the end.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/redo_foot_grids_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

FOOT_RADII=(200 400 800 1600)
FOOT_SPACING=75
N_DESTS=48
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

run_foot_grid_with_restart() {
  local CITY="$1" r="$2"
  # Bounce OSRM-foot to release accumulated memory / connection state.
  docker compose down >/dev/null 2>&1 || true
  CITY=$CITY docker compose up -d osrm-foot
  wait_for_osrm 5002 || { echo "[$(ts)]   !! $CITY foot OSRM down"; return 1; }

  npz="data/${CITY}_foot_sq_r${r}.npz"; png="data/${CITY}_foot_sq_r${r}.png"
  echo "[$(ts)] $CITY foot r=${r}"
  uv run python scripts/circuity_grid.py --city "$CITY" \
        --grid-type square \
        --spacing "$FOOT_SPACING" --radius "$r" --n "$N_DESTS" \
        --tile-buffer-m "$FOOT_BUFFER_M" \
        --concurrency "$CONCURRENCY" \
        --url http://localhost:5002 --npz "$npz" --out "$png" \
        && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
}

echo "[$(ts)] === redo_foot_grids starting ==="
while pgrep -f "circuity_grid\.py\|add_katy\.sh\|add_boulder\.sh\|fix_dc_polish" >/dev/null; do
  sleep 30
done
echo "[$(ts)] === clear; pausing 10 s for docker to settle ==="
sleep 10

# DC: re-run r=400/800/1600 (r=200 already healthy at 89%)
for r in 400 800 1600; do
  run_foot_grid_with_restart dc "$r"
done

# Katy: redo all 4 (r=200 only got 12%)
for r in 200 400 800 1600; do
  run_foot_grid_with_restart katy "$r"
done

docker compose down >/dev/null 2>&1 || true

echo
echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -10

cd ..
git add pnorm/data/explorer.html pnorm/scripts/redo_foot_grids.sh
git diff --cached --quiet || git commit -m "Redo DC + Katy foot grids with OSRM-restart-between-radii

The fix_dc_polish + add_katy runs landed bad foot data because OSRM
goes into a degenerate state under sustained K=48 load: all subsequent
/route calls return 0 valid rays. Manual /route test on the freshly-
restarted OSRM container returns valid distances, confirming the tiles
themselves are fine. Workaround: docker compose restart osrm-foot
between each radius, not just between cities.

Katy: all 4 foot grids redone (r=200 was 12%, others 0%).
DC: r=400/800/1600 redone (r=200 was already healthy at 89%).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === redo_foot_grids finished ==="
