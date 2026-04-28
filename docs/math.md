# Mathematical formulation

This is the canonical statement of what we're computing. Code should match this; if it doesn't, fix one of them.

## Setup

Let Ω ⊂ ℝ² be a bounded region of geographic space (Austin metro for the first pass), with points written in some local projection (e.g. UTM 14N) so that Euclidean distance d(x, y) = ‖x − y‖₂ is meaningful in meters.

A **routing function** τ : Ω × Ω → ℝ≥0 returns travel time (seconds) from origin x to destination y on a real transportation network. τ need not be symmetric (one-way streets) and is not, in general, a metric — but we will treat its symmetrized small-scale behavior as one.

An **isochrone** at origin x and time t is the level set
  I(x, t) = { y ∈ Ω : τ(x, y) ≤ t }.
This is what routing engines like Valhalla return (typically as a polygon).

## Local effective-time tensor

The central object. At each x, we want a symmetric positive-definite 2×2 matrix g(x) — a Riemannian metric on the tangent plane T_x Ω — such that for small displacements v,
  τ(x, x + v) ≈ √( vᵀ g(x) v ).

**Interpretation.** The level sets {v : vᵀ g(x) v = t²} are ellipses; we are saying isochrones are *locally elliptical* and g(x) is the matrix of the best-fitting ellipse at origin x. The eigenvectors of g(x) give the slow/fast directions; the eigenvalue ratio measures local anisotropy (highway corridors → high anisotropy; isolated grid → ≈ isotropic).

**How to fit.** Given an isochrone polygon I(x, t) for some small t, sample its boundary at angles θᵢ to get rays of length rᵢ(θᵢ). Each ray contributes a constraint
  rᵢ² ( (cos θᵢ)² g₁₁ + 2 cos θᵢ sin θᵢ g₁₂ + (sin θᵢ)² g₂₂ ) = t².
Solve in least squares for the three unknowns (g₁₁, g₁₂, g₂₂) subject to positive-definiteness.

One isochrone call per origin x. **O(N²) origins → O(N²) calls**, vs. the naïve O(N⁴) of doing pairwise τ.

## Comparison to Euclidean

The Euclidean reference is g_E = (1/v̄²) I, where v̄ is some reference speed (e.g. average free-flow speed in the region). Then √(vᵀ g_E v) = ‖v‖ / v̄.

Local deviation field:
  Δ(x) := g(x) − g_E.
We can decompose Δ into:
- **scalar part** (1/2) tr(Δ): how much slower/faster than reference, isotropically.
- **deviatoric part** Δ − (1/2) tr(Δ) I: anisotropy, traceless symmetric. Magnitude is the spectral norm.

## Global L^p norm

To get a single number summarizing how non-Euclidean the network is over Ω,
  ‖τ − d‖_p := ( ∫_Ω ‖Δ(x)‖_F^p dx )^(1/p)
where ‖·‖_F is Frobenius. For p → ∞ this picks up the worst-case anisotropy spot (the bridge bottleneck, the freeway exit). For p = 1 it's a mean. We'll likely report p ∈ {1, 2, ∞}.

## Things to be careful about

- **Asymmetry**: τ(x, y) ≠ τ(y, x). The local quadratic-form fit symmetrizes implicitly. If we care about asymmetry, we'd fit a more general object (Finsler metric) instead — flag for later.
- **Non-smoothness**: real τ has discontinuities at network features (bridge out, ferry schedule). The tensor field g(x) will be noisy near these; smoothing matters.
- **Projection distortion**: do all geometry in a local projection, not lat/lon. UTM 14N is fine for Austin.
- **Isochrone polygon quality**: Valhalla returns polygons that are coarse approximations. The fit's accuracy is bounded by polygon resolution, not by τ itself.

## Open questions

- Best p? Maybe report a curve.
- How to treat directional asymmetry rigorously — Finsler vs. averaging?
- Multimodal: is τ "by car"? Add transit/walk and compare?
- Time-of-day: τ is really τ(x, y, t_of_day). For a first pass we'll use a single representative weekday morning.
