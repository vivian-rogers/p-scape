#!/usr/bin/env bash
# Rerun ALL 4 NYC foot grids in legacy-ring mode with:
#   - 120s timeout (was 30s — fixes r=1600 catastrophe)
#   - origin retries up to 4 (rescues tiles whose centroid lands in water/
#     parks/private parcels — NYC's huge bbox has lots of those)
#   - min_valid_rays_frac=0.25 (accept tiles where 12/48 rays survive, not 24)
#
# Goal: lift foot coverage from ~50-56% to ~80%+. Single deploy at end.
# Waits for the K=48 fast queue to release docker first.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."
TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/nyc_foot_redo_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

FOOT_RADII=(200 400 800 1600)
FOOT_SPACING=75
N_DESTS=48
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

echo "[$(ts)] === waiting for fast queue + any other circuity_grid jobs to finish ==="
while pgrep -f "k48_fast_queue\.sh\|circuity_grid\.py" >/dev/null; do
  sleep 30
done
echo "[$(ts)] === queue clear; pausing 10s for docker to settle ==="
sleep 10

echo "[$(ts)] === bringing NYC OSRM-foot up ==="
docker compose down >/dev/null 2>&1 || true
CITY=nyc docker compose up -d osrm-foot
wait_for_osrm 5002 || { echo "[$(ts)] !! foot OSRM down"; exit 1; }

for r in "${FOOT_RADII[@]}"; do
  npz="data/nyc_foot_sq_r${r}.npz"; png="data/nyc_foot_sq_r${r}.png"
  echo "[$(ts)] nyc foot r=${r} (legacy-ring + retries=${ORIGIN_RETRIES} + min_frac=${MIN_VALID_RAYS_FRAC})"
  uv run python scripts/circuity_grid.py --city nyc \
        --grid-type square \
        --spacing "$FOOT_SPACING" --radius "$r" --n "$N_DESTS" \
        --tile-buffer-m "$FOOT_BUFFER_M" \
        --concurrency "$CONCURRENCY" \
        --sampling-mode legacy-ring \
        --origin-retries "$ORIGIN_RETRIES" \
        --min-valid-rays-frac "$MIN_VALID_RAYS_FRAC" \
        --no-full-matrix \
        --url http://localhost:5002 --npz "$npz" --out "$png" \
        && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
done

docker compose down >/dev/null 2>&1 || true

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -5

cd ..
git add pnorm/data/explorer.html pnorm/scripts/circuity_grid.py \
        pnorm/scripts/nyc_foot_redo.sh pnorm/src/pnorm/osrm.py
git diff --cached --quiet || git commit -m "NYC foot redo: origin retries + relaxed thresholds + 120s timeout

First NYC foot pass lost a lot of cells:
  r=200/400/800: 50-56% coverage  (centroid-only origin failing snap)
  r=1600: 0.2% coverage           (30s timeouts)

circuity_grid.py legacy-ring mode now supports:
  --origin-retries N            try N jittered points if centroid fails
  --min-valid-rays-frac F       lower the per-tile valid-ray threshold

NYC foot rerun: --origin-retries 4 --min-valid-rays-frac 0.25, plus
the 120s AsyncOSRM timeout. Expected coverage now ~80%+ instead of
~55%. The K=48 jittered-mc default for other cities is unaffected
(retries flag is no-op when not in legacy-ring mode).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === NYC foot redo deploy finished ==="
