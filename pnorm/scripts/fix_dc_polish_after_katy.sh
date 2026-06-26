#!/usr/bin/env bash
# Queued behind add_katy.sh:
#   Phase 1 — DC structural fix: rebuild tiles from full US PBF (no merge
#     dance — the MD+VA+DC merge attempt died on duplicate node IDs at
#     state borders). Re-run all 7 K=48 grids. Expected coverage: 80%+.
#   Phase 2 — Boulder + Madison foot r=200 polish with --origin-retries
#     to lift them from 43-49% → 70%+.
#
# Single bundled commit + Vercel deploy at the end.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/fix_dc_polish_${TS}.log"
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
ORIGIN_RETRIES=4
MIN_VALID_RAYS_FRAC=0.25

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

echo "[$(ts)] === fix_dc_polish starting; waiting on katy to finish ==="
while pgrep -f "add_katy\.sh\|circuity_grid\.py" >/dev/null; do
  sleep 30
done
echo "[$(ts)] === katy done; pausing 10 s for docker to settle ==="
sleep 10

# ─────────────────────────────────────────────────────────────────
# Phase 1 — DC: rebuild from full US PBF, then rerun all 7 grids
# ─────────────────────────────────────────────────────────────────
echo
echo "================================================================"
echo "[$(ts)] PHASE 1: DC structural fix (US PBF source)"
echo "================================================================"

docker compose down >/dev/null 2>&1 || true
rm -rf data/osrm-car-dc data/osrm-foot-dc
rm -f data/dc_buf17000.osm.pbf data/dc_buf2000.osm.pbf data/dc_combined.osm.pbf

echo "[$(ts)] === building DC car tiles (buffer ${CAR_BUFFER_M} m, from US PBF) ==="
CITY=dc PROFILE=car BUFFER_M=$CAR_BUFFER_M ./scripts/build_tiles.sh \
      || { echo "[$(ts)] !! DC car tile build failed"; exit 1; }

echo "[$(ts)] === building DC foot tiles (buffer ${FOOT_BUFFER_M} m, from US PBF) ==="
CITY=dc PROFILE=foot BUFFER_M=$FOOT_BUFFER_M ./scripts/build_tiles.sh \
      || { echo "[$(ts)] !! DC foot tile build failed"; exit 1; }

echo "[$(ts)] === bringing OSRM up for dc ==="
CITY=dc docker compose up -d
wait_for_osrm 5001 || { echo "[$(ts)] !! DC car OSRM down"; exit 1; }
wait_for_osrm 5002 || { echo "[$(ts)] !! DC foot OSRM down"; exit 1; }

for r in "${CAR_RADII[@]}"; do
  npz="data/dc_car_sq_r${r}.npz"; png="data/dc_car_sq_r${r}.png"
  echo "[$(ts)] dc car r=${r}"
  uv run python scripts/circuity_grid.py --city dc \
        --grid-type square \
        --spacing "$CAR_SPACING" --radius "$r" --n "$N_DESTS" \
        --tile-buffer-m "$CAR_BUFFER_M" \
        --concurrency "$CONCURRENCY" \
        --url http://localhost:5001 --npz "$npz" --out "$png" \
        && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
done

for r in "${FOOT_RADII[@]}"; do
  npz="data/dc_foot_sq_r${r}.npz"; png="data/dc_foot_sq_r${r}.png"
  echo "[$(ts)] dc foot r=${r}"
  uv run python scripts/circuity_grid.py --city dc \
        --grid-type square \
        --spacing "$FOOT_SPACING" --radius "$r" --n "$N_DESTS" \
        --tile-buffer-m "$FOOT_BUFFER_M" \
        --concurrency "$CONCURRENCY" \
        --url http://localhost:5002 --npz "$npz" --out "$png" \
        && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
done

docker compose down >/dev/null 2>&1 || true

# ─────────────────────────────────────────────────────────────────
# Phase 2 — Polish: Boulder + Madison foot r=200 with origin-retries
# ─────────────────────────────────────────────────────────────────
for CITY in boulder madison; do
  echo
  echo "================================================================"
  echo "[$(ts)] PHASE 2: $CITY foot r=200 polish (origin-retries)"
  echo "================================================================"

  CITY=$CITY docker compose up -d osrm-foot
  wait_for_osrm 5002 || { echo "[$(ts)] !! $CITY foot OSRM down; skip"; docker compose down >/dev/null 2>&1; continue; }

  npz="data/${CITY}_foot_sq_r200.npz"; png="data/${CITY}_foot_sq_r200.png"
  echo "[$(ts)] $CITY foot r=200 (legacy-ring + retries=${ORIGIN_RETRIES} + min_frac=${MIN_VALID_RAYS_FRAC})"
  uv run python scripts/circuity_grid.py --city "$CITY" \
        --grid-type square \
        --spacing "$FOOT_SPACING" --radius 200 --n "$N_DESTS" \
        --tile-buffer-m "$FOOT_BUFFER_M" \
        --concurrency "$CONCURRENCY" \
        --sampling-mode legacy-ring \
        --origin-retries "$ORIGIN_RETRIES" \
        --min-valid-rays-frac "$MIN_VALID_RAYS_FRAC" \
        --no-full-matrix \
        --url http://localhost:5002 --npz "$npz" --out "$png" \
        && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"

  docker compose down >/dev/null 2>&1 || true
done

# ─────────────────────────────────────────────────────────────────
# Deploy
# ─────────────────────────────────────────────────────────────────
echo
echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -10

cd ..
git add pnorm/data/explorer.html \
        pnorm/src/pnorm/cities.py \
        pnorm/scripts/fix_dc_polish_after_katy.sh
git diff --cached --quiet || git commit -m "DC structural fix (US PBF source) + Boulder/Madison foot r=200 polish

DC was using north-america/us/district-of-columbia, a 20 MB PBF
covering ONLY DC. Buffer-cropping past the DC border added no OSM
data, so car r=16000 = 0% coverage and all foot grids were stuck
at 43-45% (89% of non-water bbox-edge cells failed to snap). Tried
osmium-merge of MD + VA + DC; merge produces duplicate node IDs at
the state borders which osmium-extract rejects. Falling back to the
full US PBF (same fix NYC ended up with). Already on disk so no
extra download.

Boulder + Madison foot r=200 had 43% / 49% coverage. The NYC trick
(--origin-retries 4 --min-valid-rays-frac 0.25 in legacy-ring mode)
reruns just that radius to rescue tiles whose centroid lands on
un-routable terrain (Boulder Flatirons cells, Madison ag-fringe
cells). Expected lift to 65-75%.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === fix_dc_polish finished ==="
