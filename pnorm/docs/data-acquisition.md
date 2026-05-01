# How to actually get τ(x, y) and isochrones

Companion to [plan.md](plan.md). The plan assumes we can cheaply call a routing function; this doc is the honest survey of how.

**TL;DR — recommendation:** Run **OSRM** locally in Docker for the τ-matrix work (Frameworks A/D/F). Add **Valhalla** in Docker later only when we need polygon isochrones (Framework B). Hosted APIs are fine for a < 2k-pair smoke test but can't carry the real experiment.

## What we actually need

Two distinct queries, worth separating because backends differ:

1. **Pairwise travel time τ(x, y).** Scalar per OD pair. Lots of them (10k–1M for a decent Framework A fit across Austin). What we really want is the **many-to-many matrix** endpoint — `/table` in OSRM, `/sources_to_targets` in Valhalla — which amortizes graph search.
2. **Isochrone polygon I(x, t).** A polygon (or multi-contour set) per origin. Needed for Framework B (per-origin p(x) field). O(N_origins) calls, not O(N²).

Framework A only needs #1. Framework B needs #2. Frameworks D/F/E overlap.

**Order of magnitude — Austin, rough:**
- Framework A smoke test: 1–5k random OD pairs. Trivial.
- Framework A real: 50k pairs stratified by length × direction. Still small.
- Framework B field: ~500–5000 origins on a hex grid, one isochrone each. Also small.
- Framework C or big B with multiple t values: grows to ~10k isochrone calls. Still tractable locally; hopeless on free tiers.

## Options, ranked

### 1. OSRM in Docker (recommended for Framework A)

Open-source C++ routing engine. Tile-builds are fast, `/table` is blisteringly fast (ms per entry for small matrices).

- **Pros:** Fastest local option. `/table` returns a full N×M time matrix in one call. Stable Docker image (`osrm/osrm-backend`). Well-documented HTTP API.
- **Cons:** **No first-class isochrone endpoint.** You can fake isochrones by querying a dense grid of destinations with `/table` from each origin, then contouring — works fine for our purposes actually, and has the bonus of avoiding Valhalla's polygon-coarseness issue. No turn restrictions as rich as Valhalla; fine for time estimates at the scale we care about.
- **Setup:** `docker run osrm/osrm-backend osrm-extract -p car.lua /data/austin.osm.pbf` → `osrm-partition` → `osrm-customize` → `osrm-routed --algorithm mld`. Three commands, ~minutes for Austin.
- **Scale:** Unlimited. Your laptop, no rate limit. A 500×500 matrix in a few seconds.

### 2. Valhalla in Docker (parent project's pick; good for Framework B)

What ADR 0001 in the parent project chose. Has a real `/isochrone` endpoint that returns polygons directly.

- **Pros:** Polygon isochrones out of the box. Multimodal (drive/bike/walk/transit with GTFS). `gis-ops/docker-valhalla` image handles extract → tiles → server in one compose file.
- **Cons:** Tile build is heavier (tens of minutes for Austin metro; longer for larger). Polygon quality is coarse — generalized contours, not exact level sets. Docs are rougher than OSRM.
- **Setup:** `docker compose up` with the gis-ops image, point `tile_dir` at a volume, drop an OSM extract in, wait.
- **Scale:** Also unlimited. Matrix calls via `/sources_to_targets` are slower than OSRM but still fine.

### 3. GraphHopper in Docker

Java-based, has isochrones, comparable to Valhalla.

- **Pros:** Also has isochrones. Some people prefer its quality.
- **Cons:** Heavier runtime, Java stack. Free version has limitations vs. the commercial tier. Less momentum in the open-source community recently.
- **Verdict:** Skip unless OSRM + Valhalla both disappoint.

### 4. Self-compute isochrones from routed shortest-path trees

Skip the `/isochrone` endpoint entirely. Use OSRM `/table` against a dense destination grid per origin, then contour in Python (matplotlib `contour`, `skimage.measure.find_contours`, or `scikit-fmm` — the parent project already pulled in the last one).

- **Pros:** Works with OSRM alone. Contour resolution is *our* choice, not the engine's. Produces smoother/cleaner polygons than Valhalla's default. Unifies both query types under one backend.
- **Cons:** Need to pick a grid resolution trade-off (denser = slower but better fit). Writing the contour step ourselves (~30 lines).
- **Verdict:** This is actually my top pick for Framework B if we've already got OSRM up. Means we only run one engine.

### 5. Hosted OpenRouteService (ORS) — free tier

`openrouteservice.org`. Free API key after signup.

- **Pros:** Zero setup. Has `/isochrones` and `/matrix`. Good docs.
- **Cons:** Free tier ≈ 2,000 requests/day, 500 matrix locations/request, 5 isochrones/request. Meaning a real Framework A run blows the quota on day one; Framework B is out of reach. Rate-limited hard.
- **Verdict:** Fine for the initial 200-pair R(θ) scatter plot. Nothing more.

### 6. Mapbox / Google / HERE / TomTom

Hosted, commercial.

- **Pros:** Production quality. Good isochrone output.
- **Cons:** Metered. Mapbox Matrix costs per element; at 50k pairs you're paying real money for what Docker gives you free. Google's Distance Matrix is ~$5 per 1k elements. Google doesn't have a public isochrone endpoint at all.
- **Verdict:** No. The whole point of local is avoiding this.

### 7. Full in-house: OSM → NetworkX/igraph → Dijkstra

Skip routing engines entirely. Load OSM with `osmnx`, build a graph, run `networkx.single_source_dijkstra` per origin.

- **Pros:** Maximal control. We own the graph. Easy to modify edge weights for experiments ("what if this bridge were closed").
- **Cons:** Slower than OSRM by 10–100x at our scale. OSMnx's graph-building is itself slow. Reinventing the wheel.
- **Verdict:** Tempting for counterfactual experiments later (remove a highway, re-fit p). Not the first step.

## Decision criteria

| If we need…                        | Use                             |
|------------------------------------|---------------------------------|
| < 2k OD pairs, today, no setup     | Hosted ORS free tier            |
| Many OD matrix (Framework A/D/F)   | OSRM in Docker                  |
| Polygon isochrones (Framework B)   | Option (4): OSRM + self-contour, OR Valhalla |
| Counterfactuals (edit the network) | OSMnx + NetworkX (option 7)     |

## Concrete path forward

**Step 0** — one-time setup:
1. Install OrbStack (already called out in parent journal).
2. Grab an Austin OSM extract from BBBike or Geofabrik (Texas extract cropped to a bbox).
3. `docker run osrm/osrm-backend` through the extract → partition → customize → serve sequence. Expose on `localhost:5000`.

**Step 1** — smoke test (half a day):
- 500 random OD pairs within the Austin bbox.
- Hit `/table` batched. Compute R(x, y) = τ / (d/v̄).
- Plot R vs. θ (heading). Overlay closed-form curves for p ∈ {0.5, 1, 1.5, 2}.
- Eyeball whether Austin clusters near a particular p.

**Step 2** — fit global p (Framework A):
- Same data, more of it (10–50k pairs). NLS fit of (v̄, p).
- Sensitivity: stratify by trip length, by time-of-day (if backend supports), by direction.

**Step 3** — local field (Framework B) — only after 1 & 2:
- Hex grid of origins over Austin. Per origin, either:
  - (a) run Valhalla `/isochrone` (polygon directly), or
  - (b) run OSRM `/table` against a dense destination grid and contour.
- Fit (v(x), p(x), α(x)) per origin. Map it.

While ORS was mentioned as a backup: don't bother unless Docker install is genuinely blocked. The 2k/day ceiling means Step 2 onwards is impossible on the free tier, and mixing backends mid-experiment would just introduce another variable.

## Gotchas worth knowing up front

- **Projection.** All geometry in UTM 14N (EPSG:32614), per parent ADR 0002. Hosted APIs take lat/lon; convert at the boundary.
- **Reference speed v̄.** Pin it before fitting p, or v̄ ↔ p will trade off. Easiest pin: median of τ/d on long, highway-dominated OD pairs.
- **Asymmetry.** OSRM and Valhalla both honor one-ways. τ(x,y) ≠ τ(y,x). Decide per-framework whether to symmetrize (avg of both directions) or keep directional.
- **Sampling bias on random OD pairs.** A uniform-random bbox pair is biased toward long diagonal trips. Stratify length and direction explicitly.
- **Time-of-day.** OSRM ignores it (free-flow only). Valhalla has historical-traffic support but it's extra config. For v1, free-flow is fine and keeps the comparison clean.
- **OSM extract freshness.** Extracts from BBBike update daily; Geofabrik daily. A stale extract is fine — road topology doesn't shift fast. Don't sweat it.
