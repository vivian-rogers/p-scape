"""
Rotated anisotropic Minkowski fit: p(x) jointly with grid orientation α(x)
and axis weights (a, b).

Why this exists
---------------
The axis-aligned estimators in `lp_inversion` assume the local network behaves
like an L^p ball whose axes are east/north with unit scale. Two failure modes:

1. **Rotation.** A perfect Manhattan grid rotated 45° has *exactly* the same
   distribution of directional circuity over a uniform ring as an unrotated
   one — the distribution of c(θ) over uniform θ is invariant under rotation.
   So the moment estimators (`p_of_circuity`, `p_of_median_circuity`) are
   provably rotation-immune. But the ray-pattern MLE
   (`mle_p_from_directional_circuities`) matches c against θ ray-by-ray;
   rotating the grid de-phases the directional modulation from the assumed
   axes, and the best axis-aligned fit responds by flattening — dragging p
   toward the featureless p = 2. Measured on noiseless synthetic data: true
   p = 1 rotated 45° reads p ≈ 1.14 with σ jumping to 0.19 (vs 0.001 aligned);
   true p = 0.7 rotated 45° reads ≈ 0.78. Grid orientation leaks into the
   p field.

2. **Anisotropy.** If one direction is structurally slower (river crossings,
   superblocks, one-way systems), every direction's circuity rises, the mean
   rises, and ALL axis-aligned estimators read it as lower p — conflating
   *shape* (how grid-like) with *throughput* (how much detour overall).

The fix: model the local metric as a rotated, axis-weighted L^p norm

    ‖v‖ = ( (|u₁|/a)^p + (|u₂|/b)^p )^{1/p},   u = R(−α) v,

whose directional circuity at Euclidean bearing θ is

    c(θ) = ( A·|cos(θ−α)|^p + B·|sin(θ−α)|^p )^{1/p},
    A = a^{−p},  B = b^{−p}.

Interpretation of the fitted fields:
    p      — grid exponent, now de-confounded from orientation and throughput.
    α      — orientation of the fast grid axis (mod π). A continuous
             street-grid compass field.
    a, b   — per-axis throughput scales in (0, 1]; c along the rotated axes
             is 1/a and 1/b.  a = b = 1 ⇔ ideal streets along both axes.
    κ=b/a  — anisotropy in (0, 1]; 1 = balanced axes.

Constraints. Physically c(θ) ≥ 1 (routes can't beat the straight line). For
p ≤ 2, min_θ c is attained on the grid axes, so A, B ≥ 1 (a, b ≤ 1) is exactly
the physical constraint. For p > 2 the directional minimum moves to the
diagonal and A, B ≥ 1 is necessary but not sufficient; we accept that softness
— empirical circuities are noisy near 1 anyway.

Symmetries and canonicalization. (α, A, B) ≡ (α + π/2, B, A) ≡ (α + π, A, B),
so the fit grids α over [0, π/2) only and afterwards swaps axes so a ≥ b and
reports α ∈ [0, π) as the orientation of the fast (a) axis. When κ ≈ 1 and
p ≈ 2 the ball is a circle and α is unidentifiable — judge α only where the
fit beats the axis-aligned σ and κ is clearly below 1.

Estimation
----------
Noise model as in the axis-aligned MLE: log c_k = log c(θ_k) + N(0, σ²).
The key structural fact: raising to the p-th power linearizes the model,

    c(θ_k)^p = A f₁ₖ + B f₂ₖ,   f₁ₖ = |cos(θ_k−α)|^p,  f₂ₖ = |sin(θ_k−α)|^p,

so for fixed (p, α) the inner problem is a 2-parameter linear least squares
with box constraint A, B ≥ 1 — closed form (interior / two edges / corner of
the constraint box; the quadratic is convex so these candidates cover the
minimum). Since d(log c) = d(c^p)/(p c^p), weighting the y = c^p residuals by
w_k = 1/y_k² makes the weighted SSR equal p²·SSR_log to first order; we
therefore select (p, α) by S/p², a faithful proxy for the log-scale objective.
Only (p, α) needs a grid: n_p × n_α closed-form solves, all vectorized across
cells as five moment matrices computed by (cells × rays) @ (rays × n_α)
matmuls per p. ~100k cells × 48 rays fits comfortably in a few seconds.

Both nested models are returned:
    M1 "pure rotated grid":  A = B = 1, parameters (p, α).  This answers the
       original question — a neighborhood organized around a 45° street grid
       should read p ≈ 1 with α ≈ 45°, not a distorted p.
    M2 "full":               parameters (p, α, A, B).
Compare their σ against `mle_p_from_directional_circuities`'s σ (the M0
special case α=0, A=B=1) to judge whether rotation/anisotropy is real signal
in a cell.

Grid resolution: p and α minima are refined by one parabolic step from the
stored SSR cube, so outputs are not quantized to the grid (no banding in
rendered fields).

Caveat for K-jittered grids: `circuities[i, k]` comes from a *different*
jittered origin inside tile i for each k (see circuity_grid.py), so the fit
reads the tile-averaged directional pattern, not a single origin's. That is
the right object for a per-tile orientation field, but σ then also absorbs
intra-tile heterogeneity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def c_minkowski(theta, p: float, alpha: float = 0.0, a: float = 1.0, b: float = 1.0):
    """Directional circuity of the rotated axis-weighted L^p model."""
    theta = np.asarray(theta, dtype=float)
    if p <= 0 or a <= 0 or b <= 0:
        raise ValueError("p, a, b must be positive")
    f1 = np.abs(np.cos(theta - alpha)) ** p
    f2 = np.abs(np.sin(theta - alpha)) ** p
    return (f1 / a**p + f2 / b**p) ** (1.0 / p)


@dataclass
class MinkowskiFit:
    # M2: full rotated anisotropic model
    p: np.ndarray
    alpha: np.ndarray        # orientation of the fast axis, [0, π)
    a: np.ndarray            # fast-axis scale, (0, 1]
    b: np.ndarray            # slow-axis scale, (0, 1], b ≤ a
    kappa: np.ndarray        # b/a anisotropy, (0, 1]
    sigma: np.ndarray        # residual std of log-circuity at the optimum
    # M1: pure rotated grid (a = b = 1)
    p_rot: np.ndarray
    alpha_rot: np.ndarray    # [0, π/2)
    sigma_rot: np.ndarray
    n_valid: np.ndarray


def _quad_S(A, B, m11, m12, m22, b1, b2, s0):
    """Weighted SSR  S(A,B) = Σ w (y − A f₁ − B f₂)²  from precomputed moments."""
    return s0 - 2.0 * A * b1 - 2.0 * B * b2 + A * A * m11 + 2.0 * A * B * m12 + B * B * m22


def _solve_box(m11, m12, m22, b1, b2, s0):
    """Minimize the convex quadratic S over A, B ≥ 1. Returns (A, B, S)."""
    tiny = 1e-12
    det = m11 * m22 - m12 * m12
    with np.errstate(divide="ignore", invalid="ignore"):
        A_int = (b1 * m22 - b2 * m12) / det
        B_int = (b2 * m11 - b1 * m12) / det
        B_e1 = (b2 - m12) / m22          # edge A = 1
        A_e2 = (b1 - m12) / m11          # edge B = 1
    ok_int = (det > tiny) & (A_int >= 1.0) & (B_int >= 1.0)
    B_e1 = np.where(m22 > tiny, np.maximum(B_e1, 1.0), 1.0)
    A_e2 = np.where(m11 > tiny, np.maximum(A_e2, 1.0), 1.0)

    one = np.ones_like(m11)
    cand_A = np.stack([np.where(ok_int, A_int, 1.0), one, A_e2, one])
    cand_B = np.stack([np.where(ok_int, B_int, 1.0), B_e1, one, one])
    S = _quad_S(cand_A, cand_B, m11, m12, m22, b1, b2, s0)
    S[0] = np.where(ok_int, S[0], np.inf)
    k = np.argmin(S, axis=0)
    take = lambda arr: np.take_along_axis(arr, k[np.newaxis], axis=0)[0]
    return take(cand_A), take(cand_B), take(S)


def _parabolic(y_lo, y_mid, y_hi, step):
    """Sub-grid offset of the minimum of a parabola through 3 equispaced points.

    Skipped where y_mid is negligible next to its neighbors: an (almost) exact
    fit makes the valley a kinked V with vertex at the grid point, and a
    parabola through it lands off-center.
    """
    denom = y_lo - 2.0 * y_mid + y_hi
    with np.errstate(divide="ignore", invalid="ignore"):
        delta = 0.5 * (y_lo - y_hi) / denom
    ok = (np.abs(denom) > 1e-12) & (y_mid > 1e-3 * np.minimum(y_lo, y_hi))
    delta = np.where(ok, delta, 0.0)
    return np.clip(delta, -1.0, 1.0) * step


def fit_minkowski(
    circuities: np.ndarray,
    theta_dir: np.ndarray,
    p_min: float = 0.30,
    p_max: float = 3.0,
    n_p: int = 55,
    n_alpha: int = 36,
    min_valid_rays: int = 8,
    chunk: int = 8192,
) -> MinkowskiFit:
    """Per-cell fit of the rotated anisotropic Minkowski model.

    Parameters
    ----------
    circuities : (n_cells, n_rays) array
        Per-cell directional circuities; NaN entries excluded ray-by-ray.
    theta_dir : (n_rays,) array
        Ray angles in radians (shared across cells).
    p_min, p_max, n_p : float, float, int
        p search grid (linear spacing, parabolic refinement).
    n_alpha : int
        Orientation grid over [0, π/2) (the model's fundamental domain).
    min_valid_rays : int
        Cells with fewer finite rays get NaN everywhere.
    chunk : int
        Cells per block; bounds peak memory (the per-block SSR cube is
        chunk × n_p × n_alpha float32).
    """
    C = np.asarray(circuities, dtype=np.float64)
    theta = np.asarray(theta_dir, dtype=np.float64)
    n_cells, n_rays = C.shape
    assert theta.shape == (n_rays,)

    p_grid = np.linspace(p_min, p_max, n_p)
    dp = p_grid[1] - p_grid[0]
    alpha_grid = np.linspace(0.0, np.pi / 2.0, n_alpha, endpoint=False)
    dalpha = alpha_grid[1] - alpha_grid[0]

    # |cos/sin(θ−α)| bases, shared by all cells and all p: (n_rays, n_alpha)
    dcos = np.abs(np.cos(theta[:, np.newaxis] - alpha_grid[np.newaxis, :]))
    dsin = np.abs(np.sin(theta[:, np.newaxis] - alpha_grid[np.newaxis, :]))

    out = {
        name: np.full(n_cells, np.nan)
        for name in ("p", "alpha", "a", "b", "kappa", "sigma",
                     "p_rot", "alpha_rot", "sigma_rot")
    }
    n_valid_all = np.zeros(n_cells, dtype=int)

    for lo in range(0, n_cells, chunk):
        hi = min(lo + chunk, n_cells)
        Cc = C[lo:hi]
        nc = hi - lo

        with np.errstate(invalid="ignore", divide="ignore"):
            logC = np.log(Cc)
        valid = np.isfinite(logC)
        n_valid = valid.sum(axis=1)
        n_valid_all[lo:hi] = n_valid
        logC = np.where(valid, logC, 0.0)
        s0 = n_valid.astype(np.float64)[:, np.newaxis]   # Σ w y² = n_valid

        ssr2 = np.empty((nc, n_p, n_alpha), dtype=np.float32)
        ssr1 = np.empty((nc, n_p, n_alpha), dtype=np.float32)
        A_cube = np.empty((nc, n_p, n_alpha), dtype=np.float32)
        B_cube = np.empty((nc, n_p, n_alpha), dtype=np.float32)

        for ip, p in enumerate(p_grid):
            Y = np.exp(p * logC)
            W = np.where(valid, 1.0 / (Y * Y), 0.0)
            U = np.where(valid, 1.0 / Y, 0.0)
            F1 = dcos**p
            F2 = dsin**p
            m11 = W @ (F1 * F1)
            m22 = W @ (F2 * F2)
            m12 = W @ (F1 * F2)
            b1 = U @ F1
            b2 = U @ F2

            A, B, S = _solve_box(m11, m12, m22, b1, b2, s0)
            inv_p2 = 1.0 / (p * p)
            ssr2[:, ip] = S * inv_p2
            A_cube[:, ip] = A
            B_cube[:, ip] = B
            ssr1[:, ip] = _quad_S(1.0, 1.0, m11, m12, m22, b1, b2, s0) * inv_p2

        for tag, cube in (("", ssr2), ("_rot", ssr1)):
            flat = cube.reshape(nc, -1)
            j = np.argmin(flat, axis=1)
            ip, ia = np.unravel_index(j, (n_p, n_alpha))
            rows = np.arange(nc)
            S_mid = flat[rows, j].astype(np.float64)

            # parabolic refinement; α is periodic on the grid, p is clipped
            S_a_lo = cube[rows, ip, (ia - 1) % n_alpha].astype(np.float64)
            S_a_hi = cube[rows, ip, (ia + 1) % n_alpha].astype(np.float64)
            alpha_hat = alpha_grid[ia] + _parabolic(S_a_lo, S_mid, S_a_hi, dalpha)

            ip_lo = np.clip(ip - 1, 0, n_p - 1)
            ip_hi = np.clip(ip + 1, 0, n_p - 1)
            S_p_lo = cube[rows, ip_lo, ia].astype(np.float64)
            S_p_hi = cube[rows, ip_hi, ia].astype(np.float64)
            interior = (ip > 0) & (ip < n_p - 1)
            p_hat = p_grid[ip] + np.where(
                interior, _parabolic(S_p_lo, S_mid, S_p_hi, dp), 0.0
            )
            p_hat = np.clip(p_hat, p_min, p_max)

            dof = 4 if tag == "" else 2
            # float32 cube roundoff can leave S_mid at -1e-7 on exact fits
            sigma = np.sqrt(np.maximum(S_mid, 0.0) / np.maximum(n_valid - dof, 1))
            bad = n_valid < min_valid_rays
            out["p" + tag][lo:hi] = np.where(bad, np.nan, p_hat)
            out["sigma" + tag][lo:hi] = np.where(bad, np.nan, sigma)

            if tag == "":
                A = A_cube[rows, ip, ia].astype(np.float64)
                B = B_cube[rows, ip, ia].astype(np.float64)
                a = A ** (-1.0 / p_grid[ip])
                b = B ** (-1.0 / p_grid[ip])
                # canonical: a = fast axis; α = its orientation, mod π
                swap = a < b
                a, b = np.where(swap, b, a), np.where(swap, a, b)
                alpha_hat = np.where(swap, alpha_hat + np.pi / 2.0, alpha_hat)
                alpha_hat = np.mod(alpha_hat, np.pi)
                out["alpha"][lo:hi] = np.where(bad, np.nan, alpha_hat)
                out["a"][lo:hi] = np.where(bad, np.nan, a)
                out["b"][lo:hi] = np.where(bad, np.nan, b)
                out["kappa"][lo:hi] = np.where(bad, np.nan, b / a)
            else:
                out["alpha_rot"][lo:hi] = np.where(
                    bad, np.nan, np.mod(alpha_hat, np.pi / 2.0)
                )

    return MinkowskiFit(n_valid=n_valid_all, **out)
