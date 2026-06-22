#!/usr/bin/env bash
# Wait for Charlotte to finish, then run Charlottesville, rebuild explorer,
# commit + push + deploy.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/charlottesville_after_charlotte_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

echo "[$(ts)] === waiting for Charlotte's rerun_city_sq.sh to finish ==="
while pgrep -f "rerun_city_sq.sh" >/dev/null; do
  sleep 30
done
echo "[$(ts)] === Charlotte done, pausing 10s for Docker to settle ==="
sleep 10

echo "[$(ts)] === Charlottesville K=48 pilot starting ==="
CITY=charlottesville bash "$HERE/rerun_city_sq.sh" \
  || echo "[$(ts)] !! Charlottesville rerun failed; deploying without it"

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -5

cd ..
git add pnorm/data/explorer.html pnorm/src/pnorm/cities.py \
        pnorm/scripts/build_explorer.py pnorm/scripts/charlottesville_after_charlotte.sh
git diff --cached --quiet || git commit -m "Add Charlottesville, VA on K=48 jittered MC

UVA's Academical Village (Jefferson's 1817 grid) + Downtown Mall
(pedestrian-only since 1976) + Belmont + Fifeville + the hillside
residential rings. Streets follow topography outside the planned
cores; major roads radiate from Court Square.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === Charlottesville deploy finished ==="
