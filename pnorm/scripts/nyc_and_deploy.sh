#!/usr/bin/env bash
# Rerun NYC on the expanded 5-borough + NJ bbox with K=48 jittered MC,
# then commit + push + deploy. First-time bbox-expansion run needs fresh
# OSRM tiles since the previous tile dir was sized for a much smaller bbox.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

TS="$(date +%Y%m%d_%H%M%S)"
LOG="data/nyc_and_deploy_${TS}.log"
mkdir -p data
exec > >(tee -a "$LOG") 2>&1
ts() { date +%H:%M:%S; }

# Aggressive clean — the new bbox is several times larger than the previous
# one, so OSRM tiles + cached crops need to be regenerated from scratch.
echo "[$(ts)] === cleaning stale NYC artifacts (old bbox) ==="
rm -rf data/nyc.osm.pbf data/nyc_buf*.osm.pbf data/nyc_combined.osm.pbf \
       data/osrm-car-nyc data/osrm-foot-nyc \
       data/nyc_*_sq_*.npz data/nyc_*_sq_*.png

echo "[$(ts)] === NYC K=48 expanded-bbox pilot ==="
CITY=nyc bash "$HERE/rerun_city_sq.sh" \
  || echo "[$(ts)] !! NYC rerun failed; deploying without it"

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -5

cd ..
git add pnorm/data/explorer.html pnorm/src/pnorm/cities.py \
        pnorm/scripts/build_tiles.sh pnorm/scripts/nyc_and_deploy.sh
git diff --cached --quiet || git commit -m "Rerun NYC on K=48 with 5-borough + NJ bbox

Expanded NYC bbox from the Manhattan-centric (-74.03, 40.66, -73.85, 40.85)
to a five-borough + Hudson-waterfront (-74.25, 40.50, -73.83, 40.92) ≈
35 × 46 km. Covers:
  - Manhattan
  - all of Brooklyn (south to Coney Island)
  - full Staten Island (St. George ferry → Tottenville)
  - Jersey City / Hoboken / Weehawken / Newark edge
  - South Bronx
  - western Queens

The NJ side of the Hudson lives in a separate Geofabrik PBF
(north-america/us/new-jersey). build_tiles.sh now supports a
geofabrik_extras catalog field — downloads the extra region(s),
osmium-merges them with the primary before the bbox crop. NYC is the
first user; others may follow (London bbox is also borderline).

K=48 jittered MC across all 7 grids (replaces the previous K=1 NYC
data from the overnight catalog rerun).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main 2>&1 | tail -3
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url" | tail -3

echo "[$(ts)] === NYC deploy finished ==="
