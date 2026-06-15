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
#   BUFFER_M — expand bbox by this many meters before osmium extract (default 0).
#              Set to e.g. 17000 for car runs with 16 km destination rings so
#              ring endpoints stay inside the routable graph.
#
# Output:   data/osrm-${PROFILE}-${CITY}/${CITY}.osrm{,.*}

HERE="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${DATA_DIR:-$HERE/../data}"
PROFILE="${PROFILE:-car}"
CITY="${CITY:-austin}"
BUFFER_M="${BUFFER_M:-0}"
OSRM_DIR="$DATA_DIR/osrm-$PROFILE-$CITY"
OSRM_IMAGE="osrm/osrm-backend:latest"
OSMIUM_IMAGE="stefda/osmium-tool:latest"

# Look up the city's bbox + Geofabrik region from the catalog. If BUFFER_M > 0,
# expand the bbox by that many meters (degrees ≈ meters / 111_000, lon scaled
# by cos(lat)).
read REGION_PATH BBOX < <(
  cd "$HERE/.." && uv run --quiet python -c "
import math
from pnorm.cities import get_city
c = get_city('$CITY')
bbox = list(c.bbox)
buf_m = float('$BUFFER_M')
if buf_m > 0:
    lat_c = (bbox[1] + bbox[3]) / 2.0
    dlat = buf_m / 111_000.0
    dlon = buf_m / (111_000.0 * math.cos(math.radians(lat_c)))
    bbox = [bbox[0] - dlon, bbox[1] - dlat, bbox[2] + dlon, bbox[3] + dlat]
print(c.geofabrik_region, ','.join(f'{x:.6f}' for x in bbox))
"
)
REGION_BASENAME="$(basename "$REGION_PATH")"
EXTRACT_URL="https://download.geofabrik.de/${REGION_PATH}-latest.osm.pbf"
EXTRACT_FILE="$DATA_DIR/${REGION_BASENAME}-latest.osm.pbf"
# Bake the buffer into the cached PBF filename so different buffer sizes don't
# silently reuse each other's crop. Buffer=0 keeps the legacy filename for
# backward compat with existing tile dirs.
if [ "$BUFFER_M" = "0" ]; then
  CITY_PBF="$DATA_DIR/${CITY}.osm.pbf"
else
  CITY_PBF="$DATA_DIR/${CITY}_buf${BUFFER_M}.osm.pbf"
fi

mkdir -p "$DATA_DIR" "$OSRM_DIR"

echo "→ city=$CITY profile=$PROFILE region=$REGION_PATH bbox=$BBOX buffer_m=$BUFFER_M"

echo "→ 1/5 downloading $REGION_PATH OSM extract if missing…"
if [ ! -f "$EXTRACT_FILE" ]; then
  curl -fL "$EXTRACT_URL" -o "$EXTRACT_FILE"
else
  echo "   already have $EXTRACT_FILE"
fi

echo "→ 2/5 cropping to ${CITY} bbox ($BBOX)…"
CITY_PBF_NAME="$(basename "$CITY_PBF")"
if [ ! -f "$CITY_PBF" ]; then
  if command -v osmium >/dev/null 2>&1; then
    osmium extract -b "$BBOX" "$EXTRACT_FILE" -o "$CITY_PBF" --overwrite
  else
    docker run --rm -v "$DATA_DIR:/data" "$OSMIUM_IMAGE" \
      osmium extract -b "$BBOX" \
      "/data/${REGION_BASENAME}-latest.osm.pbf" \
      -o "/data/${CITY_PBF_NAME}" --overwrite
  fi
else
  echo "   already have $CITY_PBF"
fi

# Optional park-injection: synthesize highway=path chords through walkable
# park polygons and merge into the city PBF before OSRM extract. Triggered
# by INJECT_PARKS=yes on the foot profile. Adds ~2k nodes + ~2k ways per city.
if [ "${INJECT_PARKS:-no}" = "yes" ] && [ "$PROFILE" = "foot" ]; then
  echo "→ 2b/5 injecting synthetic park paths…"
  PARK_SYNTH="$DATA_DIR/${CITY}-parks-synth.osm"
  if uv run python "$HERE/synth_park_paths.py" \
        --input "$CITY_PBF" --output "$PARK_SYNTH"; then
    if [ -s "$PARK_SYNTH" ]; then
      MERGED="$DATA_DIR/${CITY}-with-parks.osm.pbf"
      docker run --rm -v "$DATA_DIR:/data" "$OSMIUM_IMAGE" \
        osmium merge "/data/${CITY}.osm.pbf" "/data/${CITY}-parks-synth.osm" \
        -o "/data/${CITY}-with-parks.osm.pbf" --overwrite
      CITY_PBF="$MERGED"
      echo "   merged park-augmented PBF: $MERGED"
    fi
  else
    echo "   !! park synthesis failed; falling back to plain PBF"
  fi
fi

cp -f "$CITY_PBF" "$OSRM_DIR/${CITY}.osm.pbf"

echo "→ 3/5 osrm-extract (${PROFILE} profile) → ${OSRM_DIR}"
# Use a tuned profile if scripts/<profile>-tuned.lua exists. Currently
# scripts/foot-tuned.lua tunes the foot profile for distance-cost routing,
# zero turn penalties, and a more permissive access whitelist; car profile
# inherits the container default.
TUNED_PROFILE="$HERE/${PROFILE}-tuned.lua"
if [ -f "$TUNED_PROFILE" ]; then
  echo "   using tuned profile: $TUNED_PROFILE"
  docker run --rm \
    -v "$OSRM_DIR:/data" \
    -v "$TUNED_PROFILE:/profile/${PROFILE}.lua:ro" \
    "$OSRM_IMAGE" \
    osrm-extract -p "/profile/${PROFILE}.lua" "/data/${CITY}.osm.pbf"
else
  docker run --rm -v "$OSRM_DIR:/data" "$OSRM_IMAGE" \
    osrm-extract -p "/opt/${PROFILE}.lua" "/data/${CITY}.osm.pbf"
fi

echo "→ 4/5 osrm-partition…"
docker run --rm -v "$OSRM_DIR:/data" "$OSRM_IMAGE" \
  osrm-partition /data/${CITY}.osrm

echo "→ 5/5 osrm-customize…"
docker run --rm -v "$OSRM_DIR:/data" "$OSRM_IMAGE" \
  osrm-customize /data/${CITY}.osrm

echo ""
echo "✓ tile build complete for ${CITY} (${PROFILE})."
echo "  next: cd $(dirname "$HERE") && CITY=$CITY docker compose up -d"
