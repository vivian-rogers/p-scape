#!/usr/bin/env bash
# Overnight K=48 queue: clears the remaining small/mid K=1 cities and one
# sprawl city (east_bay). Special-cases per-city:
#   - paris   : foot only (car was done in the prev fast_queue run)
#   - austin  : car all 3 + foot r=200/r=400 only (r=800/r=1600 already K=48)
#   - others  : full 3 car + 4 foot
#
# Single bundled commit + deploy at the end.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/k48_overnight_push_${TS}.log"
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

# Per-city scope. Bash 3.2 on macOS has no associative arrays, so we
# express the exceptions inline:
#   skip_car_for(city)    → returns 0 if we should SKIP the car run
#   skip_foot_r_for(c,r)  → returns 0 if we should SKIP that foot radius

skip_car_for() {
  case "$1" in
    paris) return 0 ;;       # paris car already K=48
    *)     return 1 ;;
  esac
}

skip_foot_r_for() {
  case "$1:$2" in
    austin:800|austin:1600) return 0 ;;   # austin foot r=800/r=1600 already K=48
    *)                      return 1 ;;
  esac
}

# Order: austin first (priority), then small-to-mid in increasing cost,
# paris foot last because it's the slow one (~4-6 hr on dense graph) —
# if the overnight runs short, only paris foot is left undone.
QUEUE=(austin mexico_city seattle east_bay paris)

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

  if [ "$HAS_CAR" = "yes" ] && ! skip_car_for "$CITY"; then
    for r in "${CAR_RADII[@]}"; do
      npz="data/${CITY}_car_sq_r${r}.npz"
      png="data/${CITY}_car_sq_r${r}.png"
      echo "[$(ts)] $CITY car r=${r}"
      uv run python scripts/circuity_grid.py --city "$CITY" \
            --grid-type square \
            --spacing "$CAR_SPACING" --radius "$r" --n "$N_DESTS" \
            --tile-buffer-m "$CAR_BUFFER_M" \
            --concurrency "$CONCURRENCY" \
            --url http://localhost:5001 --npz "$npz" --out "$png" \
            && echo "[$(ts)]   ok" || echo "[$(ts)]   !! failed"
    done
  else
    echo "[$(ts)] (skipping car for $CITY)"
  fi

  for r in "${FOOT_RADII[@]}"; do
    if skip_foot_r_for "$CITY" "$r"; then
      echo "[$(ts)] (skipping $CITY foot r=${r} — already K=48)"
      continue
    fi
    npz="data/${CITY}_foot_sq_r${r}.npz"
    png="data/${CITY}_foot_sq_r${r}.png"
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

echo "[$(ts)] === k48_overnight_push starting; queue: ${QUEUE[*]} ==="
echo "[$(ts)] === waiting for any in-flight jobs to finish ==="
while pgrep -f "circuity_grid\.py\|k48_fast_queue\.sh\|nyc_foot_redo\.sh" >/dev/null; do
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
uv run python scripts/build_explorer.py | tail -5

cd ..
git add pnorm/data/explorer.html pnorm/scripts/k48_overnight_push.sh
git diff --cached --quiet || git commit -m "K=48 overnight push: paris foot + mexico_city + seattle + austin partial + east_bay

Migrates the remaining small/mid K=1 cities to K=48 jittered Monte Carlo,
plus east_bay (Berkeley + Oakland) — the smallest of the sprawl five.

Special-cases:
  - paris   : foot only (car was already K=48 from prior queue)
  - austin  : car all + foot r=200/r=400 (r=800/r=1600 already K=48)

Remaining K=1 cities after this push: chicago, houston, la, sf —
each needs a dedicated overnight run.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === k48_overnight_push finished ==="
