#!/usr/bin/env bash
# Single-shot deploy that ALWAYS rebuilds the explorer first.
#
# The bug that motivated this: edit explorer_template.html, run
# `vercel deploy --prod`, ship the stale pre-edit explorer.html. The
# stale HTML had the old RasterField field names reading from the new
# payload field names → empty map. Easy to fall into when iterating fast.
#
# Standard manual deploy is now:
#   cd pnorm && bash ./scripts/deploy.sh
#
# Auto-commit the rebuilt explorer.html + push to origin BEFORE deploying so
# the deployed asset is always reproducible from a public git SHA.
#
# Optional first arg: skip-commit (just rebuild + deploy without committing).

set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."
ts() { date +%H:%M:%S; }

SKIP_COMMIT="${1:-}"

echo "[$(ts)] === rebuilding explorer.html ==="
uv run python scripts/build_explorer.py | tail -5

if [ "$SKIP_COMMIT" != "skip-commit" ]; then
  cd ..
  if ! git diff --quiet pnorm/data/explorer.html; then
    echo "[$(ts)] === committing rebuilt explorer.html ==="
    git add pnorm/data/explorer.html
    git commit -m "Rebuild explorer.html

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>" || true
    git push origin main 2>&1 | tail -3
  else
    echo "[$(ts)] === explorer.html unchanged; nothing to commit ==="
  fi
  cd pnorm
fi

cd ..
echo "[$(ts)] === vercel deploy --prod ==="
vercel deploy --prod --yes 2>&1 | grep -iE "ready|url|error" | tail -5
echo "[$(ts)] === done ==="
