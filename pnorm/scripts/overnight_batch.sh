#!/usr/bin/env bash
# Overnight batch (2026-07-02): build new catalog cities sequentially.
# Order: no-download cities first (Texas/Colorado wishlist towns, Freiburg,
# Rotterdam — their region PBFs are already on disk), then wishlist Europe
# (Berlin, Prague), then the H4 A/B extras. Each city ~1 hr. A failed city
# does not stop the queue.
set -u
cd /Users/wrogers/Documents/school/fun/metric/isochrone-metric/pnorm

CITIES=(fredericksburg bastrop fairplay freiburg rotterdam berlin prague saint_malo le_havre nuremberg)

QLOG="data/overnight_batch_$(date +%Y%m%d_%H%M%S).log"
echo "=== overnight batch START $(date) ===" | tee -a "$QLOG"
echo "queue: ${CITIES[*]}" | tee -a "$QLOG"

for c in "${CITIES[@]}"; do
  echo "=== [$(date +%H:%M:%S)] >>> starting $c ===" | tee -a "$QLOG"
  CITY="$c" bash scripts/rerun_city_sq.sh
  rc=$?
  echo "=== [$(date +%H:%M:%S)] <<< $c finished rc=$rc ===" | tee -a "$QLOG"
done

# Rebuild the explorer once all cities are done so new layers appear.
echo "=== [$(date +%H:%M:%S)] rebuilding explorer ===" | tee -a "$QLOG"
uv run python scripts/build_explorer.py 2>&1 | tail -5 | tee -a "$QLOG"
echo "=== overnight batch DONE $(date) ===" | tee -a "$QLOG"
