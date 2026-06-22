#!/usr/bin/env bash
# Run Charlotte K=48 pilot, then rebuild explorer + commit + push + deploy.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/charlotte_and_deploy_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

echo "[$(ts)] === Charlotte K=48 pilot starting ==="
CITY=charlotte bash "$HERE/rerun_city_sq.sh" \
  || echo "[$(ts)] !! Charlotte rerun failed; deploying without it"

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -5

cd ..
git add pnorm/data/explorer.html pnorm/src/pnorm/cities.py \
        pnorm/scripts/build_explorer.py pnorm/scripts/charlotte_and_deploy.sh
git diff --cached --quiet || git commit -m "Add Charlotte, NC on K=48 jittered MC

Uptown + four wards + South End + Dilworth + Myers Park + Plaza
Midwood + NoDa. The Uptown grid is rotated ~30° from cardinal axes
to follow the old Tryon Path / Indian Trading Path; the four wards
around Trade & Tryon each maintain their own subgrid alignment.
Outside Uptown the network transitions to suburban quickly.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === Charlotte deploy finished ==="
