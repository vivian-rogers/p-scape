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

## 2026-04-28 — End of session, pickup notes
**Who:** Adam + Claude Code
**State of the world:**
- End-to-end pipeline works: Valhalla on `localhost:8002`, Python wrapper, ellipse fit (6/6 synthetic tests green), 7×7 grid runner, three plot types, sample figures in `docs/figures/`. See [the previous entry](#2026-04-28--first-austin-grid--viz-end-to-end) for results.
- Vivian has write access, no commits from her yet.
- OrbStack + `isochrone-metric-valhalla` container running locally on Adam's Mac. Fine to leave up; `docker compose stop` from repo root to halt.

**One loose end (do this first next session):**
- `data/results/` is still tracked in git from an earlier commit; gitignore now excludes it but the existing files weren't untracked. Run:
  ```sh
  git rm -rf --cached data/results && git commit -m "chore: untrack data/results/" && git push
  ```

**Pickup queue (priority order):**
1. **Debug viz** — for one origin (e.g., the max-anisotropy spot, ratio 4.46), draw the actual isochrone polygon and the fitted ellipse on the same axes. Sanity check that the fit is doing what we think it is. Add as `scripts/debug_one_origin.py`.
2. **Edge-of-extract investigation** — the western column of the 7×7 grid is suspiciously slow. Check whether the BBBike "Austin" extract is clipped through that area; if so, swap to a wider Geofabrik Texas extract cropped to a generous Austin bbox.
3. **Scale up** — 21×21 and 41×41 grids. Time them. Should still be < 1 minute on the local Valhalla.
4. **Global L^p number** — implement the actual ‖τ − d‖_p computation from a grid-of-fits + a chosen reference speed v̄. Report at p ∈ {1, 2, ∞}.
5. **Asymmetry probe** — pick a few origins and visualize τ(x→y) vs τ(y→x) on the boundary. Decide whether to keep the symmetric ellipse or move to Finsler.

**Open questions / notes for whoever picks this up (incl. Vivian):**
- Reference speed v̄ is undetermined. Free-flow regional mean is a sensible default; for cross-city comparison we may want a fixed v̄ across all cities.
- Best contour t for the fit: 10 min worked. Worth running at 5 / 10 / 15 min on the same grid and seeing if the recovered g is consistent (small displacement assumption).
- Time-of-day: currently using Valhalla defaults. Real τ is τ(x, y, t_of_day). First pass is fine without it; later, slice by departure time.
- The reframe (urban-first, diffgeo-as-aside) hasn't been ack'd by Vivian yet — she may want further changes to README/AGENTS/math.md.

## 2026-04-28 — First Austin grid + viz, end-to-end
**Who:** Adam + Claude Code
**Done:**
- `src/isochrone_metric/grid.py`: threaded fetch+fit over an arbitrary list of origins, persists to JSONL.
- `scripts/run_austin_grid.py`: 7×7 grid over a central-Austin bbox at 10 min. Ran 49 origins, 0 errors, ~1.5s end-to-end against local Valhalla.
- `scripts/plot_grid.py`: three figures per run — ellipse field, effective-speed scatter, anisotropy scatter (log color).
- Sample run committed to `docs/figures/` so it's visible in GitHub without re-running.
- First numbers: median effective speed 31 mph, range 11–38 mph; median anisotropy 1.38, max 4.46. Edge of the bbox shows speed dropoff — partly real (out of urban core), partly a hint that we're approaching the OSM extract boundary and should keep that in mind when interpreting edges.
- Set repo-local git identity (Adam Altmejd) so commits don't read as the global "Dogs Playing Poker."
**Next:**
- Sanity check: at the slowest / most anisotropic origins, eyeball the actual isochrone polygon and the fitted ellipse together. (A debug viz that draws polygon + ellipse for one origin.)
- Edge-of-extract: the western column is suspiciously slow. Is the extract clipped through Austin's western suburbs? Investigate, possibly bump to a Geofabrik Texas extract cropped wider.
- Bigger grids — 21×21, 41×41 — and time how long they take. Should still be < a minute locally.
- Compute the global L^p number(s).
**Blocked / open:**
- None.

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

## 2026-04-28 — p-as-design-metric framing (parallel pnorm/ track)
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Captured Adam's framing: promote `p` in an effective L^p norm to a free parameter and treat it as an urban-design diagnostic. Working hypothesis: p ≈ 2 is desirable; grids sit near p = 1; suburbs can go below 1 (non-convex accessibility balls, no longer a true norm).
- Wrote [docs/p-as-design-metric.md](p-as-design-metric.md): six candidate frameworks (A–F) ranked, recommended order A → D → B → C → E, open questions including reconciliation with `math.md`'s Riemannian-only fit.
- Spun up sibling subproject under `pnorm/` to develop this independently of the ellipse/Riemannian track. `pnorm/` has its own routing infra (OSRM car + foot), its own circuity grids, and its own journal. The two tracks should be reconciled later; for now they coexist.
**Next:**
- Framework F+A smoke test: detour-ratio R(θ) scatter + global isotropic p fit for Austin. Can start with a small hosted-ORS sample or a tiny Valhalla run once Docker is up.
- Once isochrone infra is alive (existing `math.md` plan), framework B (per-origin p(x) field) becomes primary and `math.md` needs a pass to position the Riemannian fit as the p=2 specialization.
**Blocked / open:**
- Docker/Valhalla still the gate for anything beyond a toy A-run on the parent track. (`pnorm/` runs its own OSRM containers separately on :5001 / :5002.)
- p < 1 case: need to pick naming — "quasi-norm," "Minkowski functional," or just "shape parameter."

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
