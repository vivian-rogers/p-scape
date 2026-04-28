#!/usr/bin/env bash
# Download the Austin OSM extract used as Valhalla's input.
# Idempotent — skips if file already present.
set -euo pipefail

DEST_DIR="$(cd "$(dirname "$0")/.." && pwd)/data/valhalla"
URL="https://download.bbbike.org/osm/bbbike/Austin/Austin.osm.pbf"
DEST="$DEST_DIR/Austin.osm.pbf"

mkdir -p "$DEST_DIR"
if [[ -f "$DEST" ]]; then
  echo "Already have $DEST ($(du -h "$DEST" | cut -f1))"
  exit 0
fi

echo "Downloading $URL -> $DEST ..."
curl -L --fail -o "$DEST" "$URL"
echo "Done: $(du -h "$DEST" | cut -f1)"
