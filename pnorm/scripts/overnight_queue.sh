#!/usr/bin/env bash
# Overnight queue: chain the K=48 jittered MC pipeline through a list of
# brand-new cities. Designed to be kicked off from pnorm/ under caffeinate:
#
#   caffeinate -d -i -s -u bash ./scripts/overnight_queue.sh
#
# Flow:
#   1. Wait for any in-flight rerun_vienna_sq.sh process to complete (the
#      Vienna bbox-expansion rerun was running when this queue was
#      authored — don't trip over its docker compose ports).
#   2. For each city: invoke rerun_city_sq.sh with CITY=<key>. Failures of
#      one city don't break the others.
#   3. After all cities done: rebuild explorer.html once, then git commit +
#      push + vercel deploy. Single deploy at the end avoids 8 separate
#      production deployments overnight.
#
# Existing 20+ K=1 cities are NOT touched. Only adds 8 new cities to the
# catalog.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/overnight_queue_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

# In order of confidence — Amsterdam first because the user explicitly
# named it, biggest cities (Detroit, Phoenix) deferred to mid-queue so a
# quick win lands first.
QUEUE=(
  amsterdam
  copenhagen
  kyoto
  edinburgh
  slc
  buenos_aires
  phoenix
  detroit
)

echo "[$(ts)] === overnight_queue starting; log → $LOG ==="
echo "[$(ts)] === queue: ${QUEUE[*]} ==="

# Wait for Vienna rerun (if running) to finish so docker ports free up.
echo "[$(ts)] === waiting for any rerun_vienna_sq.sh to finish ==="
while pgrep -f "rerun_vienna_sq\.sh" >/dev/null; do
  sleep 30
done
echo "[$(ts)] === Vienna queue clear ==="

# Give docker a moment to settle after Vienna's `docker compose down`.
sleep 5

for CITY in "${QUEUE[@]}"; do
  echo
  echo "================================================================"
  echo "[$(ts)] CITY: $CITY"
  echo "================================================================"
  CITY="$CITY" bash "$HERE/rerun_city_sq.sh" \
    || echo "[$(ts)] !! $CITY rerun failed; moving on"
done

echo
echo "[$(ts)] === all cities done; bringing OSRM down ==="
docker compose down >/dev/null 2>&1 || true

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -5

# Commit + push + deploy. The single overnight deploy bundles all
# successful cities. If some failed, build_explorer.py simply skips
# their layers and the deploy ships whatever did succeed.
cd ..
git add pnorm/data/explorer.html pnorm/src/pnorm/cities.py \
        pnorm/scripts/build_explorer.py pnorm/scripts/rerun_city_sq.sh \
        pnorm/scripts/overnight_queue.sh
git diff --cached --quiet || git commit -m "Overnight K=48 city additions: ${QUEUE[*]}

Eight new cities run on the K=48 jittered MC pipeline overnight. Existing
20 K=1 cities untouched. See per-city stats in the explorer.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

cd "$HERE/.."
echo "[$(ts)] === overnight queue complete ==="
