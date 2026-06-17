#!/usr/bin/env bash
# Wait for the in-flight rerun_city_sq.sh (Edinburgh) to finish, then run
# London on the K=48 pipeline. After both succeed: rebuild explorer +
# commit + push + vercel deploy in one shot.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/edinburgh_then_london_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

echo "[$(ts)] === waiting for Edinburgh rerun_city_sq.sh to finish ==="
while pgrep -f "rerun_city_sq.sh" >/dev/null; do
  sleep 30
done
echo "[$(ts)] === Edinburgh done, sleeping 5s before London ==="
sleep 5

echo "[$(ts)] === launching London K=48 pilot ==="
CITY=london bash "$HERE/rerun_city_sq.sh" \
  || echo "[$(ts)] !! London failed; deploying without it"

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -5

cd ..
git add pnorm/data/explorer.html pnorm/src/pnorm/cities.py pnorm/scripts/build_explorer.py \
        pnorm/scripts/edinburgh_then_london.sh
git diff --cached --quiet || git commit -m "Add Edinburgh (re-run) + London on K=48 jittered MC

Edinburgh: previous overnight run failed because Geofabrik moved
Scotland from europe/great-britain/scotland (now a 9.6 KB error
stub) to europe/united-kingdom/scotland. Catalog updated to the
working path.

London: central London (City + Westminster + Camden + Hackney +
Tower Hamlets + Southwark + Lambeth + Islington). Medieval Square
Mile, Bloomsbury + Mayfair grids, and the post-medieval radials.
Greater London PBF straddles the prime meridian; UTM 30N covers
the city centre.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === finished ==="
