#!/usr/bin/env bash
# Run the 4 NYC foot grids in legacy-ring mode (1 centroid origin × 48 ring
# destinations) and deploy. K=48 jittered MC was too slow on NYC's dense
# foot graph (5 tiles/sec, ~3 days projected). Legacy-ring is 48x cheaper
# per tile.
#
# Assumes NYC OSRM tiles + docker compose are already up (skipping the
# tile-build step — they were built by the earlier killed run).

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/nyc_foot_legacy_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

CITY=nyc
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

echo "[$(ts)] === NYC foot legacy-ring pilot ==="

# Foot OSRM should already be up from earlier; if not, bring it back.
if ! curl -sf -o /dev/null --max-time 3 \
      "http://localhost:5002/nearest/v1/driving/0,0" 2>/dev/null; then
  echo "[$(ts)] === bringing NYC OSRM up ==="
  CITY=$CITY docker compose up -d
  wait_for_osrm 5002 || { echo "[$(ts)] !! foot OSRM down"; exit 1; }
fi

for r in "${FOOT_RADII[@]}"; do
  npz="data/${CITY}_foot_sq_r${r}.npz"; png="data/${CITY}_foot_sq_r${r}.png"
  echo "[$(ts)] ${CITY} foot r=${r} (legacy-ring)"
  uv run python scripts/circuity_grid.py --city "$CITY" \
        --grid-type square \
        --spacing "$FOOT_SPACING" --radius "$r" --n "$N_DESTS" \
        --tile-buffer-m "$FOOT_BUFFER_M" \
        --concurrency "$CONCURRENCY" \
        --sampling-mode legacy-ring \
        --no-full-matrix \
        --url http://localhost:5002 --npz "$npz" --out "$png" \
        && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
done

docker compose down >/dev/null 2>&1 || true

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -5

cd ..
git add pnorm/data/explorer.html pnorm/scripts/circuity_grid.py \
        pnorm/scripts/nyc_foot_legacy_and_deploy.sh
git diff --cached --quiet || git commit -m "NYC foot in legacy-ring mode (K=48 too slow for dense graph)

NYC's foot OSRM graph is dense enough that K=48 jittered-MC sampling
takes ~16 hours per foot grid (286k tiles × 2304 routes/tile, 8 cores
saturated). Switching NYC foot to legacy-ring: 1 tile-centroid origin
× 48 ring destinations. Same angular schedule, 48x fewer OSRM routes
per tile. Car grids stay K=48.

circuity_grid.py gains --sampling-mode {jittered-mc, legacy-ring}.
Other cities stay K=48 by default; NYC foot is the exception.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === NYC foot deploy finished ==="
