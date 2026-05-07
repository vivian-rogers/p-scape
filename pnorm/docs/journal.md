# pnorm journal

Append-only. Newest on top. Same format as parent.

---

## 2026-05-06 — "Isochrome" redesign via Claude Design; build script reads external template
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Adam took the existing `data/explorer.html` to Claude Design (research preview at claude.ai, Opus 4.7 vision), iterated on a beautiful end-user-facing redesign branded "Isochrome — A field guide to street geometry". Warm-paper palette, Space Grotesk + Newsreader + JetBrains Mono type, chip-style controls, intro overlay with Houston/Manhattan/Barcelona tour cards, hover card with effective-p + percentile, mobile-aware layout.
- Saved the Claude Design output as `scripts/explorer_template.html`, swapping its inline placeholder data for a single injection sentinel `/*__PAYLOAD_JSON__*/null`. Template is 39 KB.
- Rewrote `scripts/build_explorer.py`: dropped the embedded `HTML_TEMPLATE` raw-string (470 lines), now reads `scripts/explorer_template.html` from disk and injects the payload at the sentinel. Payload shape unchanged — `{layers, cities, pretty, centers, radii}` already matched what Claude Design's comment block specified, so no logic changes were needed.
- File went from 521 → 150 lines. Rebuild verified: 36 layers, 620,144 cells, 15.8 MB output.

**Why:** Adam's guiding star for the project is a viral, friendly, end-user web tool (eventually hosted, eventually with neighborhood-picker / business-siting use cases). Vivian's is the arXiv paper. Both visions share the same artifact + same data pipeline; the design split keeps the explorer presentation editable in Claude Design without forking from Vivian's reproducible-from-data pipeline. To re-skin in the future: edit `scripts/explorer_template.html` (or replace it with a fresh Claude Design export, preserving the sentinel), then rerun `uv run python scripts/build_explorer.py`.

**Caveats / known cosmetic issues to address next session:**
- Intro tour cards have hardcoded `p̄ ≈ 0.62 / 1.04 / 1.18` for Houston / Manhattan / Barcelona — Claude Design's placeholder copy, not yet wired to real data. The real medians from this build are: Houston car r=1km = 0.59, NYC foot r=800m = 0.92, Barcelona foot r=800m = 1.07. Decide whether to wire live or hand-curate to keep the tour copy clean.
- Claude Design's placeholder used city keys `new_york` / `washington_dc`; our `cities.py` uses `nyc` / `dc`. Dropdowns are populated from real keys so it works, but if/when we rename for the public-facing version, do it in `src/pnorm/cities.py` + `PRETTY` in `build_explorer.py`.

**Next:**
- Adam will look at the result, give visual/UX feedback, and we'll iterate — either back through Claude Design for visual changes or directly in code for behavior changes.
- Once the design is settled: host it (GitHub Pages would do — single self-contained HTML, no backend). That's the precondition for the viral-tool track.
- Open queue from prior journal entries still stands (wider Houston bbox, Paris/Amsterdam additions, cross-city comparison-table renderer, per-cell rotation+anisotropy fit).

**Blocked / open:**
- None.

---

## 2026-05-03 — Houston, SF, Barcelona end-to-end; 5-city comparison
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Added Barcelona to the catalog (UTM 31N, EPSG 32631; bbox covering Eixample + Old City + Gràcia).
- Ran the same pipeline on Houston (Inner Loop bbox), SF, Barcelona. Same settings as Austin/NYC for direct comparability: car at 250 m × radii {1, 2, 3} km on the city bbox; foot at 50 m × radii {200, 400, 800} m on a tight downtown bbox.
- Updated `docs/methodology.{typ,pdf}` with a cross-city comparison section + summary table.

**Headline result — 5-city comparison, foot r=800 m, median p:**

| city      | median p | p10  | p90  |
|-----------|----------|------|------|
| Austin    | 0.89     | 0.69 | 0.99 |
| Houston   | 0.91     | 0.70 | 1.00 |
| NYC       | 0.97     | 0.89 | 1.06 |
| SF        | 1.00     | 0.95 | 1.05 |
| Barcelona | **1.07** | **1.00** | **1.11** |

Barcelona's Eixample is a structural outlier — at r=800 m the *p10* reaches 1.00, meaning ≥90% of cells beat a perfect Manhattan grid. We are recovering Cerdà's chamfered-octagon block geometry directly off the routing graph (the diagonal lines of sight at every intersection add an extra travel direction beyond pure rectilinear).

**Foot vs car gap is widest in dense old cities.** Barcelona foot − car at comparable radii ≈ 0.47; NYC ≈ 0.35; Austin ≈ 0.38. One-way patterns, contraflow bike lanes, and the recent Barcelona _superilles_ all penalize cars without penalizing walkers.

**Houston (Inner Loop only) is grid-y, not sprawl-y.** Median car p = 0.59 at r=1 km is comparable to NYC; the famous Houston sprawl is outside our bbox. A wider Houston run out to Beltway 8 would likely halve the metric.

**Next:**
- Wider Houston bbox to validate the "sprawl outside the loop" hypothesis.
- One more European city — Paris (Haussmann boulevards) and Amsterdam (canal grid) are both natural extensions.
- A stand-alone comparison-table renderer (single Python script that loads multiple npz files and prints a tidy stats table without the user assembling it by hand).

**Blocked / open:**
- Houston `houston_car_p.html` is 76 MB (28k cells per layer × 3 layers). Useable but slow on lower-end hardware. Consider downsampling for the visual layer while keeping the full grid for stats.

---

## 2026-05-01 — Multi-city: catalog + NYC end-to-end
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Added `pnorm.cities` catalog with 6 entries: `austin, nyc, houston, sf, chicago, boston`. Each carries bbox, UTM EPSG, Geofabrik region path, default folium center/zoom.
- Made `pnorm.geo` UTM-zone-switchable: `set_utm_epsg(epsg)` flips the active projection. `cities.use_city(key)` is the one-call setup. Default stays UTM 14N (Austin) for backwards compat.
- `build_tiles.sh` now takes `CITY=<key>` env var; bbox + Geofabrik region come from the catalog. Output goes to `data/osrm-${PROFILE}-${CITY}/${CITY}.osrm`.
- `docker-compose.yml` parameterized: `CITY=<key> docker compose up -d` mounts the right tile dir on each service. One city loaded at a time; `down` then `up` to swap.
- `circuity_grid.py` and `circuity_map_multi.py` accept `--city <key>`. Grid script saves the active `utm_epsg` into the npz; map script restores it on read so cells render correctly across cities without manual flag-juggling.
- Renamed pre-existing Austin tile dirs to `data/osrm-{car,foot}-austin/` to fit the new convention. Existing Austin npz files still work (UTM 14N is the default).
- Built NYC tiles (Geofabrik new-york → osmium crop to bbox `(-74.04, 40.68, -73.86, 40.83)` → osrm extract / partition / customize). Both car and foot.
- NYC analysis run: car at spacing 250 m × radii {1, 2, 3} km on the full bbox; foot at spacing 50 m × radii {200, 400, 800} m on a Manhattan-only bbox `(-74.02, 40.70, -73.93, 40.79)`.
- Renders: `data/nyc_car_p.html` (6.7 MB, 7k cells), `data/nyc_foot_p.html` (62 MB, 63k cells, Manhattan-only).

**Stats — NYC Manhattan vs Austin UT/downtown core (foot, identical settings):**

| radius | NYC median p | Austin median p | NYC p90 | Austin p90 |
|--------|-------------|----------------|---------|------------|
| 200 m  | 0.84        | 0.71           | 0.99    | 0.92       |
| 400 m  | 0.93        | 0.79           | 1.01    | 0.95       |
| 800 m  | **0.97**    | 0.89           | **1.06**| 0.99       |

At r=800 m Manhattan walking is essentially p=1 (Manhattan grid, fittingly). The p90 > 1 means meaningful chunks of Manhattan are **better than a perfect grid** — long-avenue diagonals (Broadway, Bowery) cutting across the rectangle.

**NYC car vs NYC foot, same metro:**
| radius | car p | foot p (smaller bbox) |
|--------|-------|------------------------|
| 1 km   | 0.62  | (foot 800 m: 0.97)     |
| 3 km   | 0.68  | —                      |

Drivers do worse than walkers in Manhattan — one-way streets, bridge bottlenecks, Hudson/East River as barriers. The opposite signal from Austin where car > foot at most scales.
**Next:**
- Render NYC p-maps with Spectral, vmin=0.25, vmax=1.5, mirroring Austin's color treatment. Compare medians side-by-side: Austin car r=1km median p=0.51 → what does Manhattan look like?
- Build tiles for one more city — Houston is the natural foil to NYC (extreme sprawl vs. extreme density).
- Eventually: a small comparison script that loads multiple cities' npz files and prints a stats table (median p, p10, p90, etc.) for cross-city ranking.
**Blocked / open:**
- Existing Austin npz files don't carry the `utm_epsg` field (they predate the catalog). The map script falls back to the module default (UTM 14N) which happens to be correct for them. New runs are self-describing.
- For Manhattan walking grids, default 50 m spacing on the full NYC bbox would be ~100k cells per layer. We narrow to a Manhattan-only bbox to keep the HTML manageable; future improvement is to make a per-city walking_bbox optional.

---

## 2026-05-01 — Spectral colormap, UT/downtown high-res walking map
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Added `--cmap spectral` option to `circuity_map_multi.py`. RdYlBu/Spectral 11-stop palette; cmap reversal logic now keys on field × palette so "good is blue / bad is red" holds for any combination. Re-rendered all four prior maps with vmin=0, vmax=2 fixed range — natural reading of where each cell sits between sprawl (red) and Euclidean (blue).
- Built **`data/foot_ut_p.html`** — high-res walking p-map of UT/downtown:
  - bbox `(-97.78, 30.25, -97.71, 30.31)` — Lady Bird Lake → Hyde Park, MoPac → I-35.
  - **Spacing 50 m**, hexes ~57 m wide. ~33k cells across three layers.
  - Three radii: **r=200 m** (block-scale, 2.5-min walk), **r=400 m** (5-min), **r=800 m** (10-min).
  - Centered on UT Tower at zoom 14; pan/zoom to compare campus, capitol, Hyde Park, downtown, East Riverside.
- Stats: urban-core median p is meaningfully higher than the wider metro:
  | radius | n cells | median p | p25 / p75 |
  |--------|---------|----------|-----------|
  | 200 m  | 13 346  | 0.71     | 0.57 / 0.83 |
  | 400 m  | 11 457  | 0.79     | 0.67 / 0.89 |
  | 800 m  |  8 112  | 0.89     | 0.79 / 0.96 |
  At r=800 m the upper quartile crosses p=1, i.e. those cells are *better than Manhattan grid* on a 10-min walking shed.
**Next:**
- Look at the map. Specifically diffs:
  - The UT Speedway pedestrianization should show as a corridor of higher p along ~30.286 N–S.
  - Capitol grounds should be a dead spot at small r (closed perimeter) but improve fast at r=800 m once you can route around it.
  - Hyde Park grid (~30.305) should be uniformly high p.
  - Lamar / I-35 / MoPac crossings should appear as red bands.
- If patterns are clean, the natural follow-up is a foot−car diff map at r=400 m to visualize pedestrian-hostility.
**Blocked / open:**
- 32 MB HTML for `foot_ut_p.html`. Modern browsers handle it but slow on lower-end hardware.

---

## 2026-05-01 — From circuity to effective p
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Promoted Adam's framing to a per-cell shape parameter. Defined the average L^p norm of a Euclidean unit-circle direction:

  M(p) = (1/(2π)) ∫₀^{2π} (|cos θ|^p + |sin θ|^p)^{1/p} dθ
       = (2/π) ∫₀^{π/2} (cos^p θ + sin^p θ)^{1/p} dθ.

  Closed form at p=1 (4/π), p=2 (1), p→∞ (2√2/π); strictly decreasing on (0,∞) by Hölder; non-elementary in general (substituting u=tan θ gives ∫(1+u^p)^{1/p}/(1+u²)^{3/2} du, which doesn't yield to elementary antidifferentiation for non-integer p).
- Implemented `pnorm.lp_inversion`:
  - `mean_circuity_of_p(p)` — Simpson over 4097 nodes, error ≤ 1e-9.
  - `p_of_circuity(C)` — PCHIP monotone-spline inverse over a geometric grid p ∈ [0.3, 3], cached. Round-trip recovers p to ~1e-8.
  - First-order expansion around p=2 (M(p) ≈ 1 − 0.231·(p−2)) included as a back-of-envelope check; not used in the inverse.
- Extended `circuity_map_multi.py` with `--field effective_p`. Tooltip now shows both circuity and p; colormap is reversed inferno so bright = low p (sprawl), dark = high p (Euclidean-like).
- Re-rendered four p-field maps: `data/{car_p_multi,foot_p_multi,foot_p_multi_hires,car_p_hires}.html`.

**Sample inversion behavior:**
| Empirical C | Effective p | Reading |
|-------------|-------------|---------|
| 1.05        | 1.62        | very Euclidean — dense walkable grid |
| 1.27        | 1.00        | exactly Manhattan grid |
| 1.50        | 0.78        | beyond grid — subdivisions |
| 2.00        | 0.57        | non-convex accessibility |
| 5.00        | 0.32        | cul-de-sac / barrier-dominated |

**Distributions across Austin:**
- Car r=1km median **p = 0.51** — typical neighborhood is roughly L^{0.5}, *worse* than a Manhattan grid.
- Car r=5km median p = 0.75 — even at freeway scales, Austin trails Euclidean noticeably.
- Foot r=500m median p = 0.61, foot r=2km median 0.82 — pedestrians do better than drivers at every scale.

**Next:**
- Foot − car diff map at matched r (e.g. r=1km) to isolate pedestrian-hostility.
- Identify and label outlier cells (p > 1) — these are the genuinely walkable / drivable patches.
- Possibly add a closed-form rational approximation of M⁻¹ for any consumers who don't want scipy as a dep.
**Blocked / open:**
- HTML files still ~15–20 MB. Same caveat as before; vector-tile or pre-aggregate eventually.
- The L^p framing still assumes axis-aligned isotropy. Highway-at-45° will pull p down spuriously. Eventual fix: per-cell rotation α(x) before fit.

---

## 2026-04-29 — Walking profile + high-res multi-radius maps
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Added second OSRM service (`osrm-foot`, :5002) alongside `osrm-car` (:5001). Tile build extended to take `PROFILE=foot|car` env var; output now in `data/osrm-$PROFILE/`. Foot graph: 926k nodes / 4.1M edges (≈2x car — sidewalks, paths, footbridges).
- Wider bbox: `(-97.88, 30.12, -97.58, 30.50)` — captures airport, south-of-Slaughter, north to Parmer, east past SH-130, west to Bee Cave.
- Car circuity grids at 500 m spacing, r ∈ {1, 2, 3, 5} km. Foot circuity grids at 500 m, r ∈ {0.5, 1, 2} km. Plus high-res 250 m grids at one radius each (car r=1km, 19k cells; foot r=500m, 20k cells).
- Four folium maps emitted:
  - `data/car_multi.html` — car, toggleable radii
  - `data/foot_multi.html` — foot, toggleable radii
  - `data/car_hires.html` — car at 250 m spacing, r=1 km only
  - `data/foot_hires.html` — foot at 250 m spacing, r=500 m only
- Stats table: for both modes, circuity monotonically improves with radius. Short-range is where subdivisions hurt.
**Next:**
- **Diff map**: foot − car circuity at r=1km, to isolate what pedestrians pay extra (freeway crossings, gated subdivisions). This is the urban-design-signal-of-greatest-interest.
- Quantile-based color scale (currently vmin/vmax are hand-picked; percentile would auto-scale per layer).
- Journal / plan update to reflect that the circuity-field framing has displaced the p-fit as the primary deliverable. We're no longer really fitting an L^p norm; we're computing a scalar field derived from the norm ratio. Worth acknowledging in plan.md.
**Blocked / open:**
- HTML files are ~15–20 MB. Fine for local browser; too big to toss into a PR without LFS. Long-term: either pre-aggregate or vector-tile.

---

## 2026-04-29 — Circuity reframe; end-to-end works
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Resolved port conflict: macOS AirPlay Receiver squats :5000 (returns AirTunes 403). Moved OSRM to **localhost:5001**. Updated `docker-compose.yml`; scripts default to 5001.
- Austin tiles built: 485k nodes / 1.86M edges. ~15 MB/s Geofabrik download, osmium crop via docker (no native osmium), `extract → partition → customize` in ~1–2 min total. Total `data/osrm/` footprint ~100 MB.
- Reframed primary metric per Adam's request. New `src/pnorm/circuity.py`:
  - `ring_destinations(origin, radius, n)` — n points on a ring of fixed radius.
  - `circuity_from_origin(origin, radius, n, osrm)` — one `/table` call with `annotations=duration,distance` returning (t, d_route, d_euclid, θ) per destination.
  - `CircuityResult.summary()` → {n, mean/median excess_m, mean/median/p95 circuity}.
- Extended `OSRM.table` to accept `annotations="duration,distance"` and return tuple; old callers unaffected.
- `scripts/circuity_probe.py` — CLI with landmark names (downtown, ut_tower, mueller, domain, circle_c) or raw lon,lat. Three-panel plot: circuity vs θ, excess vs θ, map of destinations colored by circuity.
- Initial Austin results (5 km ring, 72 destinations each):

  | origin    | mean circuity | mean excess |
  |-----------|---------------|-------------|
  | downtown  | 1.33          | 1.64 km     |
  | mueller   | 1.41          | 2.07 km     |
  | circle_c  | 1.46          | 2.31 km     |
  | domain    | 1.50          | 2.51 km     |

  Downtown grid is cleanly the best. Domain (NW suburb, freeway-stitched) is the worst. Signatures match intuition: downtown map shows a hot-spot due-east (Colorado River crossing → bridge detour) and NW (MoPac/Shoal Creek barrier); Domain shows a broad hot band spanning 90°–210° (S and SE — the freeway loops are far).

**Next:**
- Grid of origins (hex or regular) over Austin. Per origin compute mean circuity. Map it. *This is the money chart.* Budget: ~1000 origins × 72 dests = 72k OSRM evaluations, trivially a few minutes locally.
- Multi-radius sweep per origin (r ∈ {1, 2, 5, 10} km). Short-radius circuity isolates local street grid; long-radius picks up freeway/river topology.
- Small refactor: cache results to `data/*.parquet` so grid runs are resumable.
- (Later) ties back to plan.md framework A/B: the circuity-vs-θ curve *is* the angular speed profile; fitting a (rotation α, p) to it per origin recovers framework B with a better-conditioned objective than isochrone-polygon fitting.

**Blocked / open:**
- OSRM container image is linux/amd64 running under Rosetta. Benign, just noisy warnings.
- `max-table-size 10000` set in compose; current ring probes use ~73 coords; fine.
- Circuity is a *distance* ratio, not a *time* ratio. Distinct from the original τ/(d/v̄) framing. Both are interesting — time-ratio = circuity × (free-flow speed / actual speed). Decide later whether to report one, the other, or both.

---

## 2026-04-28 — OSRM path wired up
**Who:** Adam + Claude Code (Opus 4.7)
**Done:**
- Committed to OSRM-in-Docker (option 2 from data-acquisition.md). Wrote `docker-compose.yml` (serves on :5000, `--max-table-size 10000`).
- `scripts/build_tiles.sh`: fetches Geofabrik Texas extract, crops to Austin bbox via osmium (host-native or dockerized), runs extract → partition → customize. All output under `data/` (gitignored).
- `src/pnorm/`: `geo.py` (UTM 14N transformers, Austin bbox), `osrm.py` (thin `/route` + `/table` client), `sampling.py` (stratified OD pairs — uniform origin, uniform heading × distance, rejecting out-of-bbox rather than picking two uniform bbox points, which would over-sample long diagonals).
- `scripts/smoke_test.py` (Framework F): 500 OD pairs via `/table`, plots R = τ·v̄/d vs heading with p ∈ {0.5, 1, 1.5, 2} closed-form curves overlaid (both full-circle and folded to [0°, 90°]). v̄ pinned as 95th-percentile of d/τ to reduce the v̄↔p trade-off.
- [docs/setup.md](setup.md) written.
**Next:**
- User-action: install OrbStack, run `./scripts/build_tiles.sh`, then `docker compose up -d osrm` and `uv run python scripts/smoke_test.py`. Eyeball the plot. Expected: cluster near p ≈ 1.2–1.6 for a freeway-heavy metro, dipping lower in long-haul suburb pairs.
- If the scatter looks sane: Framework A proper — 10–50k pairs, NLS fit of (v̄, p), stratify by trip length.
- Consider turning `--max-table-size` down or batching smaller once we know the p99 call latency.
**Blocked / open:**
- OrbStack install is the gate; none after that.
- `--max-table-size 10000` is generous — harmless for a laptop, worth noting if we containerize further.
