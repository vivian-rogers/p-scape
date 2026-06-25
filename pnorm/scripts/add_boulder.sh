#!/usr/bin/env bash
# Add Boulder, CO end-to-end: build tiles → K=48 grids → rebuild → commit → deploy.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/add_boulder_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

CITY=boulder
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

echo "[$(ts)] === Boulder add: starting ==="

# Wait for any in-flight runs to clear before mutating docker.
while pgrep -f "circuity_grid\.py\|add_madison\.sh\|k48_overnight_push\.sh\|fix_dc_barcelona" >/dev/null; do
  echo "[$(ts)] (waiting for in-flight jobs)"
  sleep 30
done

docker compose down >/dev/null 2>&1 || true

if [ ! -f "data/osrm-car-${CITY}/${CITY}.osrm" ]; then
  echo "[$(ts)] === building car tiles (buffer ${CAR_BUFFER_M} m) ==="
  CITY=$CITY PROFILE=car BUFFER_M=$CAR_BUFFER_M ./scripts/build_tiles.sh \
        || { echo "[$(ts)] !! car tile build failed"; exit 1; }
else
  echo "[$(ts)] (car tiles already built — skipping)"
fi

if [ ! -f "data/osrm-foot-${CITY}/${CITY}.osrm" ]; then
  echo "[$(ts)] === building foot tiles (buffer ${FOOT_BUFFER_M} m) ==="
  CITY=$CITY PROFILE=foot BUFFER_M=$FOOT_BUFFER_M ./scripts/build_tiles.sh \
        || { echo "[$(ts)] !! foot tile build failed"; exit 1; }
else
  echo "[$(ts)] (foot tiles already built — skipping)"
fi

echo "[$(ts)] === bringing OSRM up for $CITY ==="
CITY=$CITY docker compose up -d
wait_for_osrm 5001 || { echo "[$(ts)] !! car OSRM down"; exit 1; }
wait_for_osrm 5002 || { echo "[$(ts)] !! foot OSRM down"; exit 1; }

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

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -10

cd ..
git add pnorm/src/pnorm/cities.py pnorm/scripts/build_explorer.py \
        pnorm/scripts/add_boulder.sh pnorm/data/explorer.html
git diff --cached --quiet || git commit -m "Add Boulder, CO to pscape (K=48 jittered MC)

Downtown core (Pearl St pedestrian mall + CU campus) on the standard
plains-side grid + curvilinear suburbs to the north/east + topographic
distortion against the Flatirons foothills on the west. Bbox: (-105.31,
39.95, -105.15, 40.10) ≈ 13.6 × 16.7 km — covers downtown, CU, North
Boulder, Gunbarrel, and the foothill transition. The east-west
gradient in p_eff should be visible: grid in the urban core, falling
off as streets bend around topography.

K=48 jittered MC, 3 car (1/4/16 km) + 4 foot (200/400/800/1600 m).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === Boulder add finished ==="
