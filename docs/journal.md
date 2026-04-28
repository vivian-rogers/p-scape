# Journal

Append-only log. Newest entries on top. Format:

```
## YYYY-MM-DD — short title
**Who:** name (+ tool, e.g. "Adam + Claude Code")
**Done:**
- bullet
**Next:**
- bullet
**Blocked / open:**
- bullet (or "none")
```

Keep entries short. The point is to give the next session (human or agent) enough to pick up without re-reading the whole repo.

---

## 2026-04-28 — Reframe: lead with the urban question, not the diffgeo
**Who:** Adam + Claude Code (Vivian feedback)
**Done:**
- Rewrote README, AGENTS.md, docs/math.md, and the GitHub repo description to lead with the urban / spatial-analysis question. Diffgeo is now a one-paragraph aside in math.md, not the framing.
- Math content is unchanged: ellipse fit at each origin, scalar+deviatoric decomposition, L^p over the city. Just spoken differently — "ellipse to the isochrone", "effective speed", "anisotropy ratio" — instead of "Riemannian metric / geodesic ball".
- Genre is *urban planning / spatial-mathematics academia*, not a math paper. Both collaborators are quant-fluent so math.md can stay technical; only the headline framing changed.
**Next:**
- Continue: real-data smoke against the Valhalla endpoint, then a small-grid Austin viz (effective-speed + anisotropy fields).
**Blocked / open:**
- None.

## 2026-04-28 — Valhalla up
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Installed OrbStack (Apple Silicon, both collaborators on AS).
- Pulled `ghcr.io/gis-ops/docker-valhalla/valhalla:latest`.
- Downloaded Austin OSM extract (BBBike, ~64MB) to `data/valhalla/Austin.osm.pbf`.
- `docker-compose.yml` at repo root; `scripts/fetch_extract.sh` for the .pbf.
- `docker compose up -d` → tiles built in ~minutes → `http://localhost:8002/isochrone` returns clean polygons (5/10/15-min from downtown Austin: 336 / 1194 / 3557 boundary points).
**Next:**
- Thin Python wrapper in `src/isochrone_metric/routing.py` for the isochrone POST.
- `fit_local_tensor(polygon, origin, t)` — least-squares fit of g(x). Test on a synthetic ellipse first, then real Austin data.
- A first notebook visualizing the tensor field over a small grid.
**Blocked / open:**
- None.

## 2026-04-28 — Repo bootstrap
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Created private repo `AFriendinNeed1903/isochrone-metric` and pushed initial scaffold (pyproject, package stub, README, .gitignore, .env.example).
- Invited Vivian (`vivian-rogers`) as collaborator with push access.
- `uv sync` succeeds; deps locked. Stack: numpy, scipy, shapely, geopandas, pyproj, rasterio, matplotlib, folium, requests, tqdm, scikit-fmm.
- Wrote canonical math doc, AGENTS.md/CLAUDE.md, CONTRIBUTING.md, first two ADRs.
**Next:**
- Install OrbStack (Docker on macOS).
- Pull/run Valhalla via `gis-ops/docker-valhalla`, build tiles on an Austin OSM extract (BBBike or Geofabrik-cropped).
- Smoke-test the isochrone endpoint from a notebook.
- Implement `fit_local_tensor(isochrone_polygon, origin)` against one synthetic + one real isochrone.
**Blocked / open:**
- None — Docker install is the next user-action gate.
