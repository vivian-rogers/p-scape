# p as an urban-design metric

Companion to [math.md](math.md). Captures a different framing Adam proposed on 2026-04-28: treat the **p** in an effective L^p norm as a **structural property of a region's transportation network**, and use it as a diagnostic for urban design.

`math.md` (as currently written) fits a local **Riemannian** tensor g(x) — i.e., the local unit ball is always an ellipse (implicitly L^2). The L^p there is only the aggregation exponent over Ω. This doc is about promoting p to a free parameter *inside* the local norm itself. If we end up going this route, we should reconcile the two docs.

## Framing

Working claim: the "effective" L^p that best fits a region's travel-time geometry is a handle on urban design.

- **p ≈ 2** — isotropic, "circular" accessibility. Dense mixed grids, multiple redundant routes, no sharp bottlenecks. Hypothesized to be desirable.
- **p ≈ 1** — Manhattan / taxicab. Strict orthogonal grid with no diagonals. Many grid-only cities sit here.
- **p < 1** — non-convex accessibility balls (astroid-ish). Suburbs with cul-de-sacs, single-access subdivisions, one-bridge neighborhoods. Strictly speaking **not a norm** (triangle inequality fails, ball non-convex) — call it a quasi-norm or a Finsler/Minkowski functional. Most likely the regime of interest for "car-brained sprawl" diagnostics.
- **p → ∞** — Chebyshev. A single dominant direction dictates time regardless of the other axis. Probably degenerate for road networks but useful as a limit.

## Operational definition (the diagnostic)

Given a routing function τ(x, y) and Euclidean geometry on Ω:

For OD pair (x, y), define the **detour ratio**
  R(x, y) := τ(x, y) / (‖y − x‖₂ / v̄)
where v̄ is a reference speed for the region. R ≥ 1 almost always; R = 1 iff the network supports straight-line travel at reference speed.

Under a pure isotropic L^p model, τ(x, x+v) = ‖v‖_p / v̄, so
  R(x, x+v) = ‖v‖_p / ‖v‖_2 = (|cos θ|^p + |sin θ|^p)^(1/p)   for p ≥ 1, θ = angle of v.
This is the key scalar relation. Fit p from many (R_i, θ_i) samples.

For p < 1 the same expression still defines a (quasi-)ball shape, though ‖·‖_p is no longer a norm. We'll still call it "p" because the numeric fit is well-defined and interpretable.

Anisotropy (highway corridors) breaks the simple form. Two ways to handle: (i) allow a rotation α(x) so axes align with a dominant direction, (ii) fold anisotropy into a separate matrix factor and keep p as the shape-only parameter. See Frameworks B and C below.

## Frameworks to try, ranked

**A. Global isotropic p, fit from OD pairs.** Sample M random OD pairs across the region. Compute τ via Valhalla `/route` (or `/sources_to_targets` matrix). Fit (v̄, p) jointly by nonlinear least squares against the R(θ) relation above.
- *Pros:* one number for the region; cheapest experiment; doesn't require isochrones. Direct answer to "is this city closer to L^1 or L^2?"
- *Cons:* collapses all heterogeneity (downtown grid vs. suburb) into one number; can't tell if p is low because of real anisotropy or because of actual non-convexity.

**B. Local p from isochrone shape (per-origin).** At each origin x, pull one isochrone I(x, t). Sample boundary rays r(θ_i). Under a local isotropic L^p with speed v(x):
  r(θ) = v(x) · t · (|cos θ|^p + |sin θ|^p)^(−1/p).
Fit (v(x), p(x)) per origin. Optionally a rotation α(x). Produces a **field** p(x) over Ω — the money chart.
- *Pros:* uses the isochrone infrastructure directly; preserves the O(N²) budget math.md is built around; generalizes math.md's elliptical fit (p=2 is a special case).
- *Cons:* 2–3 params per polygon with ~20–60 boundary samples; polygon coarseness caps the fit; edge effects near Ω boundary.

**C. Anisotropic L^p (matrix + p).** τ(x, x+v) ≈ ‖A(x) v‖_p / v(x). A is 2×2 PD (3 dof), p is scalar. Most general local Minkowski fit.
- *Pros:* handles highway corridor *and* ball-shape simultaneously; proper superset of math.md's Riemannian fit.
- *Cons:* identifiability concerns with ~40 boundary samples; overfits easily. Probably a v2 after B.

**D. Scaling-exponent regression (diagnostic).** Per compass sector, regress log(τ) on log(d) for many OD pairs. Slope ≠ 1 indicates time–distance non-linearity (a violation of any fixed-norm model). Per-sector gives anisotropy without committing to an L^p form.
- *Pros:* model-free sanity check on whether *any* norm-based fit is honest.
- *Cons:* doesn't yield a p; complement, not primary.

**E. Non-parametric ball-matching.** For each origin, pick p ∈ [0.3, 3] maximizing IoU (or minimizing symm-difference area) between the isochrone polygon and the best-fit L^p ball (with free v(x), optionally rotation).
- *Pros:* doesn't assume the ray-function form is smooth.
- *Cons:* shape match only; no metric structure; aggregation is just a histogram of p(x).

**F. Detour-ratio histogram (framing check).** Pure scatter of R vs. θ across many OD pairs and origins — compare to the closed-form R(θ, p) curves for p ∈ {0.5, 1, 1.5, 2}. Really just the visualization that justifies A.
- *Pros:* makes the framing legible before any fitting.
- *Cons:* not a model.

## Recommended order

1. **F then A** — first pass, global p for Austin. Can bootstrap on hosted ORS or a tiny Valhalla smoke-test while Docker is still being set up. Answers "what's Austin's p?" in a single number and a plot. (Cheapest step; highest info-per-hour.)
2. **D alongside A** — sanity check that OD time scales linearly with distance; if it doesn't, any p-fit is shaky and we know why.
3. **B** — lift to a p(x) field once isochrone infrastructure is alive. This is where the urban-design story gets visual (map of p(x) overlaid on Austin; expect high-p dense core, low-p suburbs, gradient along the highways).
4. **C** — only if B shows systematic residual anisotropy that a single p + isotropy can't explain.
5. **E** — as a non-parametric cross-check on B's fits wherever they look suspicious.

## Open questions / gotchas

- **v̄ identifiability.** In A, v̄ and p trade off. Pin v̄ first (e.g., free-flow on arterials from a small calibration set) or report a joint confidence region.
- **p < 1 is not a norm.** The fit is still well-defined and interpretable as a shape parameter, but we should stop calling the output "a metric" when p < 1. "Effective Minkowski functional" or just "accessibility field" is more honest.
- **Asymmetry.** τ(x,y) ≠ τ(y,x) (one-ways, turn penalties). A, D, F can symmetrize by averaging both directions. B fits a shape inherently tied to outgoing isochrones (arrivals would need the reverse isochrone — see Valhalla's `reverse_flow` option).
- **Reference frame rotation.** If we don't allow α(x), a highway at 45° drags fitted p downward (looks like L^1). Either rotate per-origin or report p only after whitening by a coarse anisotropy estimate.
- **Sampling bias.** Random OD pairs over-weight long trips and under-weight local structure. For A, stratify pair lengths.
- **Relation to math.md.** If framework B becomes primary, the math doc's central object (Riemannian g) should be rewritten as the p=2 specialization of a Minkowski fit. Do this in the same PR as the code change.
- **Ground truth for "desirable p."** Adam's hypothesis (p ≈ 2 is better) is an empirical claim, not a definition. Needs external validation — VMT, access-to-jobs, 15-minute-city scores. Out of scope for v1 but flag for eventual comparison.
