# Method

Canonical statement of what we're computing. Code should match this; if it doesn't, fix one of them.

## Setup

Let Ω ⊂ ℝ² be a bounded region of geographic space (Austin metro for the first pass), with points written in a local equal-area-ish projection (UTM 14N for Austin) so that Euclidean distance d(x, y) = ‖x − y‖₂ is meaningful in meters.

A **routing function** τ : Ω × Ω → ℝ≥0 returns travel time (seconds) from origin x to destination y on the real network — Valhalla served from a local OSM extract. τ is not symmetric in general (one-ways) and is not a metric in the formal sense, but its small-scale behavior around each origin is what we care about.

An **isochrone** at origin x and time t is the level set
  I(x, t) = { y ∈ Ω : τ(x, y) ≤ t }.
Valhalla returns these as polygons.

## Local ellipse fit

The central object. At each x, we want a symmetric positive-definite 2×2 matrix g(x) such that for small displacements v,
  τ(x, x + v) ≈ √( vᵀ g(x) v ).

Geometrically: the level sets {v : vᵀ g(x) v = t²} are **ellipses**, and g(x) is the matrix of the best-fitting ellipse to the isochrone polygon at x.

What g encodes:
- **Eigenvectors** = principal axes (slow / fast directions of the local network).
- **Eigenvalues** = (1 / v_i)² where v_i is the effective speed along that axis. So:
  - Fast axis speed: 1 / √λ_min(g).
  - Slow axis speed: 1 / √λ_max(g).
  - Anisotropy ratio: √(λ_max / λ_min) = (slow-axis travel time) / (fast-axis travel time). Equals 1 in an isotropic grid; large near major corridors.
- **Determinant**: (det g)^(-1/4) is an effective isotropic speed (geometric mean of the two axis speeds).

How to fit. Project the isochrone polygon to the local meter CRS. For each boundary vertex at angle θᵢ from the origin and projected distance rᵢ, write
  rᵢ² ( (cos θᵢ)² g₁₁ + 2 cos θᵢ sin θᵢ g₁₂ + (sin θᵢ)² g₂₂ ) = t².
Stack the rows and solve in least squares for the three unknowns (g₁₁, g₁₂, g₂₂). Project to the PSD cone if the fit comes out slightly indefinite due to polygon noise.

Cost: **one isochrone call per origin**. So O(N²) origins → O(N²) calls — versus the naïve "compute τ between every pair of points" approach which is O(N⁴).

## Comparison to Euclidean

The Euclidean reference is g_E = (1/v̄²) I, where v̄ is some chosen reference speed (regional free-flow average, or whatever lets us compare cities cleanly).

Local deviation field:
  Δ(x) := g(x) − g_E.
Decompose into:
- **Scalar part** ½ tr(Δ): how much slower (or faster) than the reference, isotropically.
- **Deviatoric part** Δ − ½ tr(Δ) I: traceless symmetric — pure anisotropy. Magnitude is the spectral norm.

## Global L^p summary

A single number summarizing "how non-Euclidean is this network":
  ‖τ − d‖_p := ( ∫_Ω ‖Δ(x)‖_F^p dx )^(1/p)
where ‖·‖_F is Frobenius. p → ∞ picks up worst-case anisotropy spots (the bottleneck bridge, the freeway exit). p = 1 is a mean. We'll likely report p ∈ {1, 2, ∞}.

Per-component versions (just the scalar slow-down, just the anisotropy) are also useful and trivial to compute from the same Δ field.

## Things to be careful about

- **Asymmetry**: τ(x, y) ≠ τ(y, x). The ellipse fit symmetrizes implicitly (an ellipse has no preferred direction). If we want directional asymmetry, we'd need a richer object — see "open questions."
- **Non-smoothness**: real τ has discontinuities at network features (bridge out, ferry schedule). g(x) will be noisy near these; some smoothing of the field is warranted.
- **Projection distortion**: do all geometry in a local meter CRS, not lat/lon. UTM 14N (EPSG:32614) for Austin.
- **Polygon resolution**: Valhalla returns polygons at finite resolution. The fit's accuracy is bounded by polygon density, not by τ itself. Using a larger contour t (say, 10 min vs. 2 min) gives more boundary points and a more stable fit, at the cost of "small-displacement" approximation quality.
- **Choice of t**: too small and the polygon has too few vertices; too large and the ellipse approximation breaks down. Probably worth fitting at a couple of t values and comparing.

## Connection to differential geometry (note for the curious)

The object g(x) is exactly a Riemannian metric on Ω, and the isochrones-as-ellipses claim is the local-quadratic approximation to its geodesic balls. Treating directional asymmetry would push us to a **Finsler metric**. We're not pursuing the diffgeo machinery here — there's no need to compute geodesics, curvature, or covariant derivatives for the urban questions we care about — but the language is occasionally a useful shorthand and we'll borrow it where it clarifies.

## Open questions

- Best p for the global summary? Probably worth reporting a curve.
- Asymmetry: τ(x,y) ≠ τ(y,x). Average vs. fit a richer object?
- Multimodal: drive vs. transit vs. bike, and the gaps between.
- Time-of-day: τ really depends on departure time. First pass uses a single representative weekday morning; later, a small set of time slices.
- What's the right reference v̄? Regional mean free-flow speed is one choice; "the same Euclidean for all cities so we can compare" is another.
