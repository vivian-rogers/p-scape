#!/usr/bin/env bash
# Add Katy + Fulshear, TX end-to-end: build tiles → K=48 grids → rebuild
# → commit → deploy. Texas PBF already on disk so no Geofabrik download
# is required — should run quickly.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/add_katy_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

CITY=katy
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

echo "[$(ts)] === Katy add: starting ==="
while pgrep -f "circuity_grid\.py\|add_madison\.sh\|add_boulder\.sh\|k48_overnight_push\.sh\|fix_catalog_sweep\.sh" >/dev/null; do
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
        pnorm/scripts/add_katy.sh pnorm/data/explorer.html
git diff --cached --quiet || git commit -m "Add Katy + Fulshear, TX to pscape (K=48 jittered MC)

West-of-Houston exurban sprawl. Bbox includes:
  - Old Katy / Katy MUD downtown core (the original 1893 grid around
    Avenue B & 1st St)
  - Mason Rd commercial corridor (east edge)
  - Cinco Ranch + LaCenterra master-planned suburbs (central)
  - Fulshear's newer subdivisions (west edge)
  - I-10 corridor bisecting east-west

Expected to be the most extreme low-p example in the catalog:
'loop-and-lollipop' arterial-fed cul-de-sac form is dominant outside
the small old Katy grid. ~16 × 21 km bbox.

K=48 jittered MC, 3 car (1/4/16 km) + 4 foot (200/400/800/1600 m).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === Katy add finished ==="
