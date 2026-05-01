# Setup

Local OSRM backend for τ(x, y) queries over Austin.

## One-time

1. Install [OrbStack](https://orbstack.dev/) (Docker runtime for macOS). Start it — `docker info` should work.
2. From `pnorm/`:
   ```sh
   uv sync
   chmod +x scripts/build_tiles.sh
   ./scripts/build_tiles.sh
   ```
   This downloads the Texas Geofabrik extract (~700 MB), crops to the Austin bbox via osmium, then runs the OSRM `extract → partition → customize` pipeline. ~5–15 min on a modern laptop. Everything lands in `data/` (gitignored).

## Running

```sh
docker compose up -d osrm                 # serves on http://localhost:5000
uv run python scripts/smoke_test.py       # 500 pairs, writes data/smoke.png
docker compose down                       # when done
```

Check it's alive:
```sh
curl 'http://localhost:5000/route/v1/driving/-97.7431,30.2672;-97.7355,30.2849?overview=false' | jq '.routes[0].duration'
```
Should return a number of seconds (downtown Austin to UT, roughly).

## Customizing

- Different region: `REGION=california ./scripts/build_tiles.sh` + edit bbox.
- Different bbox: `BBOX=-97.9,30.2,-97.6,30.45 ./scripts/build_tiles.sh`.
- Different profile (bike/foot): edit the `-p /opt/car.lua` flag in `scripts/build_tiles.sh` and the `docker-compose.yml` command.

## Troubleshooting

- **`osmium-tool` image won't pull:** `brew install osmium-tool` on the host and rerun; the script prefers native osmium when present.
- **`osrm-extract` OOMs on large regions:** either (a) crop the bbox tighter, or (b) run Docker with more RAM in OrbStack settings.
- **Port 5000 already in use:** change the host port in `docker-compose.yml` (`"5001:5000"`).
- **Router returns `NoRoute`:** origin or destination snapped to a disconnected graph component (rare in a car profile over a metro).
