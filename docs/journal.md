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
