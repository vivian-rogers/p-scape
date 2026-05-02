#!/usr/bin/env bash
set -euo pipefail

# Build OSRM tiles for a city in pnorm/cities.py.
# Requires: docker running. Optional: native osmium-tool (falls back to docker).
#
# Usage:   CITY=nyc PROFILE=foot ./scripts/build_tiles.sh
# Env:
#   CITY     — key from pnorm/cities.py (default: austin)
#   PROFILE  — car | foot | bicycle (default: car)
#   DATA_DIR — root data dir (default: pnorm/data)
#
# Output:   data/osrm-${PROFILE}-${CITY}/${CITY}.osrm{,.*}

HERE="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${DATA_DIR:-$HERE/../data}"
PROFILE="${PROFILE:-car}"
CITY="${CITY:-austin}"
OSRM_DIR="$DATA_DIR/osrm-$PROFILE-$CITY"
OSRM_IMAGE="osrm/osrm-backend:latest"
OSMIUM_IMAGE="stefda/osmium-tool:latest"

# Look up the city's bbox + Geofabrik region from the catalog.
read REGION_PATH BBOX < <(
  cd "$HERE/.." && uv run --quiet python -c "
from pnorm.cities import get_city
c = get_city('$CITY')
print(c.geofabrik_region, ','.join(f'{x:.6f}' for x in c.bbox))
"
)
REGION_BASENAME="$(basename "$REGION_PATH")"
EXTRACT_URL="https://download.geofabrik.de/${REGION_PATH}-latest.osm.pbf"
EXTRACT_FILE="$DATA_DIR/${REGION_BASENAME}-latest.osm.pbf"
CITY_PBF="$DATA_DIR/${CITY}.osm.pbf"

mkdir -p "$DATA_DIR" "$OSRM_DIR"

echo "→ city=$CITY profile=$PROFILE region=$REGION_PATH bbox=$BBOX"

echo "→ 1/5 downloading $REGION_PATH OSM extract if missing…"
if [ ! -f "$EXTRACT_FILE" ]; then
  curl -fL "$EXTRACT_URL" -o "$EXTRACT_FILE"
else
  echo "   already have $EXTRACT_FILE"
fi

echo "→ 2/5 cropping to ${CITY} bbox ($BBOX)…"
if [ ! -f "$CITY_PBF" ]; then
  if command -v osmium >/dev/null 2>&1; then
    osmium extract -b "$BBOX" "$EXTRACT_FILE" -o "$CITY_PBF" --overwrite
  else
    docker run --rm -v "$DATA_DIR:/data" "$OSMIUM_IMAGE" \
      osmium extract -b "$BBOX" \
      "/data/${REGION_BASENAME}-latest.osm.pbf" \
      -o "/data/${CITY}.osm.pbf" --overwrite
  fi
else
  echo "   already have $CITY_PBF"
fi

cp -f "$CITY_PBF" "$OSRM_DIR/${CITY}.osm.pbf"

echo "→ 3/5 osrm-extract (${PROFILE} profile) → ${OSRM_DIR}"
docker run --rm -v "$OSRM_DIR:/data" "$OSRM_IMAGE" \
  osrm-extract -p /opt/${PROFILE}.lua /data/${CITY}.osm.pbf

echo "→ 4/5 osrm-partition…"
docker run --rm -v "$OSRM_DIR:/data" "$OSRM_IMAGE" \
  osrm-partition /data/${CITY}.osrm

echo "→ 5/5 osrm-customize…"
docker run --rm -v "$OSRM_DIR:/data" "$OSRM_IMAGE" \
  osrm-customize /data/${CITY}.osrm

echo ""
echo "✓ tile build complete for ${CITY} (${PROFILE})."
echo "  next: cd $(dirname "$HERE") && CITY=$CITY docker compose up -d"
