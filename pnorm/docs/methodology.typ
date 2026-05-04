#set page(
  paper: "us-letter",
  margin: (x: 1.2in, y: 1.0in),
  numbering: "1",
  footer: context [
    #set text(size: 8pt, fill: rgb("888"))
    #counter(page).display() / #context counter(page).final().first()
    #h(1fr)
    pnorm methodology
  ],
)
#set text(font: "New Computer Modern", size: 10.5pt)
#set par(justify: true, leading: 0.65em)
#show heading.where(level: 1): set text(weight: "bold", size: 14pt)
#show heading.where(level: 2): set text(weight: "bold", size: 11.5pt)
#show heading.where(level: 1): it => [#v(0.6em) #it #v(0.3em)]
#show heading.where(level: 2): it => [#v(0.4em) #it #v(0.1em)]
#show raw: set text(font: "JetBrains Mono", size: 9pt)
#show link: it => underline(text(fill: rgb("#1f5fa8"), it))

#align(center)[
  #text(size: 18pt, weight: "bold")[Effective $L^p$ exponent of an urban\
  travel-network: methodology]
  #v(0.3em)
  #text(size: 10pt, fill: rgb("555"))[
    `pnorm/` track of `isochrone-metric` · 2026-05
  ]
]

#v(0.5em)

#align(center, box(width: 75%, fill: rgb("F4F1EA"), inset: 10pt, radius: 4pt)[
  #set par(justify: true)
  #set text(size: 9.5pt)
  *Abstract.*
  We model a city's drivable / walkable network as if it were locally an
  isotropic $L^p$ Minkowski functional and report a scalar shape parameter
  $p(x)$ at each origin. The procedure is: sample destinations on a
  Euclidean ring of fixed radius around $x$, compute the OSRM-routed mean
  ratio of network distance to straight-line distance (the *mean
  circuity*), then invert against the closed-form integral
  $M(p)$ that gives the average $L^p$ magnitude of a Euclidean
  unit-circle direction. $M(p) = 4/π$ at $p=1$ (Manhattan grid) and
  $M(p) = 1$ at $p=2$ (Euclidean); for general $p$ the integral is
  non-elementary, so we invert numerically. The output is a
  per-origin scalar field $p(x) ∈ (0, ∞)$ rendered as an interactive
  heatmap. We apply the pipeline to Austin and to Manhattan; Manhattan's
  walking core lands at $p approx 1$ as expected, with the upper
  quartile crossing $p = 1$ at the 10-minute walkshed --- "better than a
  perfect grid" courtesy of long avenues like Broadway.
])

= Motivation

A long tradition in urban-form analysis treats a city's road network as a
deformation of straight-line geometry: every pair of points can be reached
by a path on the network, but the distance you actually travel exceeds
the straight-line distance by some factor. The two ends of that spectrum
are well known. A perfect rectilinear grid (Manhattan, Salt Lake City,
parts of Chicago) forces axis-aligned travel and the network distance is
the $ell_1$ taxicab norm $|Delta x| + |Delta y|$. An open plane with
no constraints permits straight-line travel and the network distance is
the $ell_2$ Euclidean norm $sqrt(Delta x^2 + Delta y^2)$. Most actual
cities sit somewhere in between, and any one neighborhood may be closer
to one extreme than another.

We make that intermediate position quantitative by *fitting an $L^p$
exponent* to the local network. The hypothesis to test is whether $p$,
viewed as a free parameter of the unit-ball shape rather than an
aggregation exponent over the city, is a useful single-number diagnostic
for the urban-design question "how circuitous is travel here?". Higher
$p$ (closer to 2) means rounder unit balls and access closer to a true
Euclidean disk; lower $p$ means progressively more star-shaped accessible
sets and more circuitous travel; $p < 1$ means the unit ball is
non-convex, formally not a norm but a quasi-norm, the regime of
cul-de-sac sprawl.

= From travel-time to mean circuity

For an origin $x$ and a sampling radius $R$ we place $N$ destinations
$y_i = x + R(cos theta_i, sin theta_i)$ uniformly on the Euclidean ring
of radius $R$ around $x$. We obtain network distances $d_"route"(x, y_i)$
from the local OSRM service (#link("https://project-osrm.org")[`project-osrm.org`])
and define the *mean circuity* at $x$ as

$ C(x; R) = 1/N sum_(i=1)^N (d_"route"(x, y_i)) / (d_"euc"(x, y_i)). $

Two snap-related corrections matter at the granularity we work at:

#set enum(numbering: "1.")
+ OSRM snaps both endpoints to the nearest node in the routable graph.
  If the snapped destination ends up *closer* to $x$ than the requested
  ring point, $d_"route"$ is measured between snapped endpoints but
  $d_"euc"$ would still equal $R$ if naively computed --- and the ratio
  goes below $1$, which is unphysical. We compute $d_"euc"$ from the
  snapped endpoint coordinates returned by OSRM, ensuring
  $C >= 1$ by construction.
+ When the snapped destination lies far from the requested ring point
  (sparse graph, parks, water), the probe is uninformative. We drop any
  destination whose snap offset exceeds $25%$ of $R$.

After these corrections $C(x; R)$ averages over the $tilde.op 30$--$60$
surviving rays and is a stable function of the ring radius $R$.

= Effective $L^p$ norm: definition

Let $v(theta) = (cos theta, sin theta)$ be a point on the Euclidean unit
circle. Its $L^p$ magnitude is $norm(v(theta))_p = (|cos theta|^p +
|sin theta|^p)^(1/p)$. Define

$ M(p) := 1/(2 pi) integral_0^(2 pi) (|cos theta|^p + |sin theta|^p)^(1/p) dif theta = 2/pi integral_0^(pi/2) (cos^p theta + sin^p theta)^(1/p) dif theta, $

the mean over directions, where the second equality uses the symmetry
of $|cos theta|^p + |sin theta|^p$ under $theta arrow.r theta + pi/2$.

#strong[Interpretation.] If the network behaves locally like a
centered, isotropic, axis-aligned $L^p$ Minkowski functional with the
same scale as Euclidean, then a Euclidean ring of destinations has
average network-distance equal to $M(p)$. Equating the empirical mean
circuity $C(x; R)$ to $M(p)$ defines the effective $L^p$ exponent at
$x$:

$ p(x) := M^(-1)(C(x; R)). $

#figure(
  image("figures/m_of_p.png", width: 100%),
  caption: [
    Left: the forward map $M(p)$. Strictly decreasing from $infinity$
    at $p arrow.r 0^+$ through $4/pi$ at $p = 1$ and $1$ at $p = 2$,
    asymptoting to $2 sqrt(2) / pi approx 0.900$ as $p arrow.r infinity$.
    Right: $L^p$ unit balls in 2-D for representative $p$. At $p = 1$
    the ball is a diamond (Manhattan); $p = 2$ a circle (Euclidean);
    $p = 4$ a rounded square; $p = 0.5$ a non-convex four-pointed star
    (the "no diagonals" cul-de-sac regime).
  ]
)

= Closed forms, monotonicity, asymptotics

#strong[Closed-form values.]

$ M(1) &= 4/pi approx 1.27324 quad &("Manhattan grid") \
M(2) &= 1 quad &("Euclidean") \
M(infinity) &= 2 sqrt(2) / pi approx 0.90032 quad &("Chebyshev / L"^infinity ")") $

The values at $p = 1$ and $p = infinity$ follow from elementary
integration: at $p = 1$, $integral_0^(pi/2) (cos theta + sin theta) dif
theta = 2$; at $p = infinity$ the integrand becomes $max(cos theta,
sin theta)$, and splitting at $pi/4$ gives $integral_0^(pi/4) cos theta
+ integral_(pi/4)^(pi/2) sin theta = sqrt(2)$. The case $p = 2$ is
trivial: $sqrt(cos^2 + sin^2) = 1$.

#strong[Monotonicity.] For any fixed nonzero vector $w in RR^n$, the map
$p arrow.r norm(w)_p$ is strictly decreasing on $(0, infinity)$
(a direct consequence of Hölder; see e.g. #emph[Hardy, Littlewood, Pólya, "Inequalities", §2.10]).
Integrating preserves the monotonicity, so $M : (0, infinity) arrow.r (2
sqrt(2) / pi, infinity)$ is a strictly decreasing bijection. The inverse $p(C)$ is
therefore well-defined for any $C in (2 sqrt(2) / pi, infinity)$.

#strong[Asymptotics.] First-order expansion around $p = 2$:

$ M(p) approx 1 + alpha (p - 2), quad alpha = 1/pi integral_0^(pi/2) (cos^2 theta ln cos theta + sin^2 theta ln sin theta) dif theta approx -0.2310. $

So $M(p) approx 1 - 0.231(p - 2)$, which gives $M(1) approx 1.231$
versus the exact $4 / pi approx 1.273$ --- about $3.3%$ low. Useful as a
back-of-envelope sanity check, not for the inverse map.

As $p arrow.r 0^+$, $|cos theta|^p arrow.r 1$ and $|sin theta|^p
arrow.r 1$ pointwise (off the axes), so the inner sum approaches $2$
and $(dot)^(1/p) arrow.r infinity$. The metric grows unboundedly: $M$
diverges in the limit of pure axis-only travel.

= Non-elementarity and numerical inversion

The substitution $u = tan theta$ transforms the integral into

$ M(p) = 2/pi integral_0^infinity (1 + u^p)^(1/p) / (1 + u^2)^(3/2) dif u, $

which is elementary at $p in {1, 2, infinity}$ but not for general
real $p$ --- the factor $(1 + u^p)^(1/p)$ obstructs elementary
antidifferentiation. We therefore evaluate $M$ numerically and
invert via interpolation:

#set enum(numbering: "1.")
+ Compute $M(p)$ on a geometric grid $p in [0.30, 3.0]$ using
  composite Simpson with $4097$ nodes over $[0, pi/2]$. Empirical
  error against the closed-form values at $p in {1, 2}$ is below
  $10^(-9)$.
+ Build a monotone-cubic (PCHIP) interpolant of $p$ as a function of
  $C = M(p)$ across the table. Round-trip $C arrow.r p arrow.r M(p) =
  C$ recovers $p$ to $approx 10^(-8)$.
+ Clamp inputs outside the table range to the nearest endpoint.

The inverse table is built once per process (cached) and applies to
$tilde.op 10^5$ cells in milliseconds.

= Pipeline

The pipeline turns a city bounding box into an interactive scalar field
$p(x)$ rendered as a folium hex-tile heatmap. The pieces:

#set list(marker: ([•], [‣]))

- *OSM data.* Geofabrik regional extracts (e.g.
  `north-america/us/new-york-latest.osm.pbf`), cropped to the city
  bbox by `osmium-tool`. One extract per city.
- *Routing engine.* OSRM 5.26 (#link("https://project-osrm.org")[`project-osrm.org`])
  in Docker. We build separate tile sets per profile: `car`
  uses the standard `car.lua` profile and `foot` uses `foot.lua`.
  The car tiles serve on `localhost:5001` and the foot tiles on
  `:5002`, swapped by city via `CITY=<key> docker compose up -d`.
- *Sampling.* For each origin $x$ in a hexagonal grid (configurable
  spacing, typically $50$--$500$ m) and each chosen ring radius $R$,
  we issue one OSRM `/table` request to a single source and $N$
  destinations on the ring (typically $N = 48$). The endpoint
  returns the snapped source and destination coordinates plus the
  network distance and duration matrix.
- *Aggregation.* We compute $C(x; R)$ via the snap-corrected formula
  above, drop snap-offset outliers, and accept the cell if at least
  $3$ rays survive.
- *Field assembly.* The grid is stored as a structured numpy `.npz`
  bundle: cell centers in both UTM and lon/lat, `mean_circuity`,
  `mean_excess_m`, `n_valid`, the hex spacing, ring radius, and the
  active UTM EPSG code. The presence of `utm_epsg` makes downstream
  rendering self-describing across cities.
- *Inversion.* The map renderer applies $p(C) = M^(-1)(C)$ per cell.

== Hex grid geometry

We use pointy-top hex tiling in UTM coordinates. With center-to-center
spacing $s$ along a row and rows offset by $s/2$, the row pitch is
$s sqrt(3) / 2$. Each hex has side length $r = s / sqrt(3)$.
Insetting the bbox by $R + 500 m$ keeps the destination ring inside
the OSM extract for every interior cell.

== UTM zone selection

Distance computations are done in the local UTM zone of each city
(EPSG codes 32614 for Austin, 32618 for NYC, etc.). UTM has $< 0.1%$
distance distortion within its $6 degree$ longitudinal band; using the
*wrong* zone (e.g. UTM 14 N for NYC) introduces $> 30%$ errors and
silently corrupts the metric. The catalog in
`pnorm/src/pnorm/cities.py` pins one zone per city, and
`use_city(key)` switches the geometry module's projection.

= Cartography

The map renderer (`scripts/circuity_map_multi.py`) writes a folium HTML
with togglable layers, one per ring radius. Each cell is a hex polygon
colored by its $p$ value. Two colormaps:

- *Inferno* (default): low $p$ = bright yellow, high $p$ = dark.
  Direct semantic match to "hot = bad".
- *Spectral*: low $p$ = red, mid = yellow, high $p$ = blue. Better for
  cross-city diagnostics; the divergent palette puts $p approx 1$
  (Manhattan) at the colorless midline so departures in either
  direction read clearly.

The renderer auto-flips palette direction for negative-orientation
fields (e.g. raw circuity, where high = bad) so the convention "good
cells stay blue / dark" holds across combinations.

We default to a fixed colorbar range ($v_min = 0.25, v_max = 1.5$ in
the field plots) so cells are directly comparable across maps.

= City catalog

`pnorm/src/pnorm/cities.py` registers a fixed catalog. Each entry
pins six fields:

#table(
  columns: (auto, 1fr, auto, auto, auto, auto),
  align: (left, left, left, left, left, left),
  inset: 5pt,
  stroke: 0.5pt + rgb("#ccc"),
  table.header[*Key*][*City*][*UTM*][*Geofabrik region*][*Default zoom*][*Bbox extent*],
  [`austin`], [Austin, TX], [14N], [`us/texas`], [11], [airport → Parmer],
  [`nyc`], [New York City], [18N], [`us/new-york`], [12], [Manhattan + adjacent boroughs],
  [`houston`], [Houston, TX], [15N], [`us/texas`], [11], [downtown + Inner Loop],
  [`sf`], [San Francisco], [10N], [`us/california`], [12], [SF proper],
  [`chicago`], [Chicago, IL], [16N], [`us/illinois`], [11], [Loop + North Side],
  [`boston`], [Boston, MA], [19N], [`us/massachusetts`], [12], [Boston proper],
  [`barcelona`], [Barcelona, ES], [31N], [`europe/spain`], [13], [Eixample + Old City + Gràcia],
)

Adding a new city is a single dict entry plus a tile build:

```sh
CITY=portland PROFILE=car  ./scripts/build_tiles.sh
CITY=portland PROFILE=foot ./scripts/build_tiles.sh
docker compose down && CITY=portland docker compose up -d
uv run python scripts/circuity_grid.py --city portland --spacing 250 \
    --radius 1000 --npz data/portland_car_r1000.npz
```

= Findings

#strong[Austin (UT / downtown / Hyde Park core, foot, $50 m$ spacing).]

#table(
  columns: (auto, auto, auto, auto, auto),
  align: (left, right, right, right, right),
  inset: 5pt,
  stroke: 0.5pt + rgb("#ccc"),
  table.header[*Radius*][*Cells*][*Median* $p$][*p25 / p75*][*p90*],
  [200 m], [13 346], [0.71], [0.57 / 0.83], [0.92],
  [400 m], [11 457], [0.79], [0.67 / 0.89], [0.95],
  [800 m], [8 112],  [0.89], [0.79 / 0.96], [0.99],
)

#strong[New York City (Manhattan-tight bbox, foot, $50 m$ spacing).]

#table(
  columns: (auto, auto, auto, auto, auto),
  align: (left, right, right, right, right),
  inset: 5pt,
  stroke: 0.5pt + rgb("#ccc"),
  table.header[*Radius*][*Cells*][*Median* $p$][*p25 / p75*][*p90*],
  [200 m], [23 214], [0.84], [0.65 / 0.94], [0.99],
  [400 m], [22 095], [0.93], [0.80 / 0.99], [1.01],
  [800 m], [17 723], [0.97], [0.89 / 1.02], [1.06],
)

The Manhattan median crosses $p = 1$ at the $10$-minute walkshed,
with the upper quartile pushing through it. The $p_(90) approx 1.06$
is genuinely above pure Manhattan grid --- the long avenue
diagonals of Broadway and Bowery (and the Greenwich Village skew
streets) cut across the rectangle and pull access toward Euclidean.
Austin at the same setting plateaus at $p approx 0.89$; the
pre-1920 streetcar grids of Hyde Park / North Loop / parts of UT
are visibly more circular than the post-war additions.

#strong[Drivers vs. pedestrians: opposite signals across cities.]

#table(
  columns: (auto, auto, auto, auto),
  align: (left, right, right, right),
  inset: 5pt,
  stroke: 0.5pt + rgb("#ccc"),
  table.header[*City*][*Mode*][*Radius*][*Median* $p$],
  [Austin],  [car],  [1 km],   [0.51],
  [Austin],  [foot], [800 m],  [0.89],
  [NYC],     [car],  [1 km],   [0.62],
  [NYC],     [foot], [800 m],  [0.97],
)

In Austin, drivers do *worse* than walkers locally (cul-de-sac
penalty hits cars hard, walkers can cut through parks). In Manhattan,
the same direction holds but the gap is much wider --- $0.62$ versus
$0.97$. Manhattan one-way streets, the bridges/tunnels as the only
inter-borough crossings, and the rivers as hard barriers all bite the
car network specifically.

= Cross-city comparison

We ran the pipeline on five cities under fixed settings: car at $250 m$
hex spacing × radii $\{1, 2, 3\} k m$ on the city's full bbox, foot at
$50 m$ spacing × radii $\{200, 400, 800\} m$ on a tight downtown bbox.
A summary at the longest radius for each mode:

#table(
  columns: (auto, auto, auto, auto, auto, auto, auto),
  align: (left, right, right, right, right, right, right),
  inset: 5pt,
  stroke: 0.5pt + rgb("#ccc"),
  table.header(
    [*City*],
    [*Car median* $p$ \ ($r=1 k m$)],
    [*Car median* $p$ \ ($r=3 k m$)],
    [*Foot median* $p$ \ ($r=800 m$)],
    [*Foot* $p_(10)$ \ ($r=800 m$)],
    [*Foot* $p_(90)$ \ ($r=800 m$)],
    [*Note*],
  ),
  [Austin],    [0.51], [0.67], [0.89], [0.69], [0.99], [post-war grid + suburbs],
  [Houston],   [0.59], [0.76], [0.91], [0.70], [1.00], [Inner Loop bbox; sprawl is outside],
  [NYC],       [0.62], [0.68], [0.97], [0.89], [1.06], [Manhattan-tight bbox],
  [SF],        [0.69], [0.82], [1.00], [0.95], [1.05], [strict grid + Market diagonal],
  [Barcelona], [0.60], [0.77], [*1.07*], [*1.00*], [*1.11*], [Eixample + chamfered corners],
)

Several patterns are worth flagging:

#set enum(numbering: "1.")

+ *Barcelona's Eixample is a structural outlier.* At a $10$-minute
  walkshed, the *p-tenth percentile* of the Eixample/Old City bbox
  reaches $p = 1.00$: at least $90%$ of cells beat a perfect
  Manhattan grid. The median of $p = 1.07$ is consistent with the
  empirical signature of Cerdà's $113 m × 113 m$ chamfered-octagon
  blocks, which add a diagonal line of sight at every intersection.
  We are recovering the geometric advantage that the urban-form
  literature has attributed to Cerdà's plan since at least Solà-Morales
  (1978) #footnote[Solà-Morales, M. de.
  _Cerdà / Ensanche._ Universitat Politècnica de Catalunya, 1978.],
  but reading it directly off the routing graph rather than off the
  cadastral plan.

+ *Drivers and walkers diverge most in the densest cities.* In Austin
  the median driver-walker gap (foot $p$ minus car $p$ at comparable
  radii) is $0.38$. In NYC it is $0.35$. In Barcelona it is $0.47$ ---
  the largest of the set. The walking grid in dense old European
  cities is intentionally easier than the driving grid; the
  one-way pattern, contraflow bike lanes, and the recent
  _superilles_ closures all penalize cars without penalizing
  walkers.

+ *SF has the highest car* $p$ *of the five.* Despite topographic
  challenges, San Francisco's strict grid produces the most
  Euclidean *driving* network in the set: $p = 0.69$ at $r = 1 k m$,
  rising to $p = 0.82$ at $r = 3 k m$. The hills don't show up in
  the metric because the metric is over network distance only;
  vertical elevation isn't penalized.

+ *Houston's Inner Loop is grid-y; the sprawl is outside the bbox.*
  Within I-610 we read $p = 0.59 / 0.76$ for car, slightly better
  than Austin's metro. The well-known sprawl signature would emerge
  at a wider bbox out to Beltway 8; we did not run it.

+ *Walking-radius gradient.* In every city, the median $p$ rises
  monotonically with the ring radius. The interpretation: at small
  $r$ the local detour pattern dominates (a single cul-de-sac
  matters), while at large $r$ those detours average out and the
  metric reads the city's freeway / arterial topology. Cities differ
  most at small $r$: Austin foot at $r = 200 m$ is $p = 0.71$,
  Barcelona at the same setting is $p = 0.92$, a $30%$ gap that
  shrinks to half that by $r = 800 m$.

#figure(
  table(
    columns: (auto, auto, auto, auto, auto, auto),
    align: (left, right, right, right, right, right),
    inset: 5pt,
    stroke: 0.5pt + rgb("#ccc"),
    table.header(
      [*City*], [foot $r = 200 m$], [foot $r = 400 m$], [foot $r = 800 m$],
      [car $r = 1 k m$], [car $r = 3 k m$],
    ),
    [Austin],    [0.71], [0.79], [0.89], [0.51], [0.67],
    [Houston],   [0.76], [0.83], [0.91], [0.59], [0.76],
    [NYC],       [0.84], [0.93], [0.97], [0.62], [0.68],
    [SF],        [0.87], [0.95], [1.00], [0.69], [0.82],
    [Barcelona], [0.92], [1.00], [1.07], [0.60], [0.77],
  ),
  caption: [
    Median effective $p$ across radii and modes for the five cities
    run to date. Cities are ordered by foot $p$ at $r = 800 m$.
    Bold-text observations: Barcelona's foot grid above $p = 1$ at
    every radius beyond $400 m$, SF's car grid converging on
    $p approx 0.85$, the consistent gap of $0.3$--$0.5$ between foot
    and car within a single city.
  ]
)

= Caveats and future work

#set enum(numbering: "1.")
+ *Axis-aligned isotropy assumption.* The closed-form $M(p)$ assumes
  the local network's unit ball is axis-aligned. A neighborhood
  organized around a $45 degree$ highway will fit a small $p$ for
  the wrong reason. The next refinement is a per-cell rotation
  $alpha(x)$ optimized jointly with $p$, generalizing $M(p)$ to a
  rotated 2-D Minkowski functional.

+ *Static, all-day routing.* OSRM uses static edge weights (no
  congestion). Time-of-day variation matters for "real" walking and
  driving; the present pipeline gives a free-flow snapshot.

+ *Pedestrian network completeness.* OSRM's `foot` profile relies on
  OSM tags. Missing sidewalks, ferry-only crossings, and
  pedestrian-permissive private paths all introduce noise that
  degrades $p$. NYC, with high OSM coverage, fares better than less
  well-mapped cities.

+ *Cross-city normalization.* Reporting $p$ on a fixed colorbar
  range makes cities visually comparable, but the correct
  normalization for, say, "what's the typical $p$ at a $5$-min
  walkshed across all U.S. metros" is an empirical question we
  have not yet posed.

+ *Reconciliation with the parent Riemannian track.* The sibling
  `src/isochrone_metric/` track fits a Riemannian tensor $g(x)$ to
  an isochrone polygon and works with $p = 2$ implicitly (every
  unit ball is an ellipse). The two should be reconciled
  eventually: the Riemannian fit can be cast as the special-case
  $p = 2$ branch of a more general anisotropic Minkowski-norm fit
  that also recovers $p$.

= Reproducibility

All inputs derive from public OSM extracts and a fixed OSRM version.
The full pipeline runs locally (no rate-limited APIs). The catalog,
projection switch, tile build script, OSRM Docker compose,
ring-sampling code, $M$-inversion code, and folium renderer are all
in `pnorm/`, with a running journal at `pnorm/docs/journal.md`.

For one city end-to-end:

```sh
CITY=<key> PROFILE=car  ./scripts/build_tiles.sh  # ~5 min
CITY=<key> PROFILE=foot ./scripts/build_tiles.sh  # ~10 min
CITY=<key> docker compose up -d
uv run python scripts/circuity_grid.py --city <key> \
    --spacing 250 --radius 1000 --npz data/<key>_r1000.npz
uv run python scripts/circuity_map_multi.py --city <key> \
    --npz data/<key>_r1000.npz \
    --field effective_p --cmap spectral \
    --vmin 0.25 --vmax 1.5 \
    --out data/<key>_p.html
```
