#!/usr/bin/env bash
set -euo pipefail

# Build OSRM tiles for Austin.
# Requires: docker running. Optional: native osmium-tool (falls back to docker).

HERE="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${DATA_DIR:-$HERE/../data}"
PROFILE="${PROFILE:-car}"
OSRM_DIR="$DATA_DIR/osrm-$PROFILE"
BBOX="${BBOX:--98.00,30.10,-97.55,30.55}"
REGION="${REGION:-texas}"
EXTRACT_URL="https://download.geofabrik.de/north-america/us/${REGION}-latest.osm.pbf"
OSRM_IMAGE="osrm/osrm-backend:latest"
OSMIUM_IMAGE="stefda/osmium-tool:latest"

mkdir -p "$DATA_DIR" "$OSRM_DIR"

echo "→ 1/5 downloading $REGION OSM extract if missing…"
if [ ! -f "$DATA_DIR/${REGION}-latest.osm.pbf" ]; then
  curl -fL "$EXTRACT_URL" -o "$DATA_DIR/${REGION}-latest.osm.pbf"
else
  echo "   already have $DATA_DIR/${REGION}-latest.osm.pbf"
fi

echo "→ 2/5 cropping to Austin bbox ($BBOX)…"
if [ ! -f "$DATA_DIR/austin.osm.pbf" ]; then
  if command -v osmium >/dev/null 2>&1; then
    osmium extract -b "$BBOX" \
      "$DATA_DIR/${REGION}-latest.osm.pbf" \
      -o "$DATA_DIR/austin.osm.pbf" --overwrite
  else
    docker run --rm -v "$DATA_DIR:/data" "$OSMIUM_IMAGE" \
      osmium extract -b "$BBOX" \
      "/data/${REGION}-latest.osm.pbf" \
      -o "/data/austin.osm.pbf" --overwrite
  fi
else
  echo "   already have $DATA_DIR/austin.osm.pbf"
fi

cp -f "$DATA_DIR/austin.osm.pbf" "$OSRM_DIR/austin.osm.pbf"

echo "→ 3/5 osrm-extract (${PROFILE} profile) → ${OSRM_DIR}"
docker run --rm -v "$OSRM_DIR:/data" "$OSRM_IMAGE" \
  osrm-extract -p /opt/${PROFILE}.lua /data/austin.osm.pbf

echo "→ 4/5 osrm-partition…"
docker run --rm -v "$OSRM_DIR:/data" "$OSRM_IMAGE" \
  osrm-partition /data/austin.osrm

echo "→ 5/5 osrm-customize…"
docker run --rm -v "$OSRM_DIR:/data" "$OSRM_IMAGE" \
  osrm-customize /data/austin.osrm

echo ""
echo "✓ tile build complete."
echo "  next: cd $(dirname "$HERE") && docker compose up -d osrm"
