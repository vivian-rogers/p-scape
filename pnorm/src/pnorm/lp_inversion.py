"""
Effective L^p norm: from mean circuity to a single shape parameter p.

We treat the empirical mean circuity of a region as the average L^p magnitude of a
uniformly-random direction on the *Euclidean* unit circle, and invert to find p.

Setup
-----
Let v(θ) = (cos θ, sin θ) be a point on the Euclidean unit circle, parametrized by
θ ∈ [0, 2π).  Its L^p norm is

    ‖v(θ)‖_p = (|cos θ|^p + |sin θ|^p)^{1/p}.

The mean over directions is

    M(p) = (1/(2π)) ∫_0^{2π} (|cos θ|^p + |sin θ|^p)^{1/p} dθ
         = (2/π)   ∫_0^{π/2} (cos^p θ + sin^p θ)^{1/p} dθ        (π/2-symmetry)

Interpretation: if the routing network behaves locally like a centered, axis-aligned
isotropic L^p Minkowski functional with the same scale as Euclidean, then a unit-radius
Euclidean ring of destinations has average network-distance equal to M(p).  Equating
M(p) to the empirically observed mean circuity defines the *effective p* of the network.

Closed-form values
------------------
    p = 1   :  M(1) = 4/π             ≈ 1.27324
    p = 2   :  M(2) = 1               (Euclidean, by definition)
    p → ∞   :  M(∞) = 2√2/π           ≈ 0.90032
    p → 0⁺  :  M(p) → ∞                (cul-de-sac limit)

Why no closed form for general p
--------------------------------
Substitute u = tan θ to get

    M(p) = (2/π) ∫_0^∞ (1 + u^p)^{1/p} / (1 + u²)^{3/2} du.

The integrand is elementary only at p ∈ {1, 2, ∞}; for general real p the
(1 + u^p)^{1/p} factor obstructs elementary antidifferentiation.

Monotonicity
------------
For each fixed nonzero vector, p ↦ ‖x‖_p is strictly decreasing on (0, ∞)
(Hölder).  Integrating preserves this: M is strictly decreasing.  So M : (0, ∞) →
(2√2/π, ∞) is a bijection and the inverse p(C) is well-defined for any C in that range.

First-order expansion around p = 2
----------------------------------
    M(p) ≈ 1 + (p − 2)·α,   α = (1/π) ∫_0^{π/2} (cos²θ ln cos θ + sin²θ ln sin θ) dθ
                              ≈ −0.2310

So  M(p) ≈ 1 − 0.231 (p − 2).  At p = 1 this gives ≈ 1.231 vs. exact 1.273 — about 3.3%
low.  Acceptable for a back-of-envelope sanity check; not for the inverse map.

Numerical inverse
-----------------
Composite Simpson over [0, π/2] at 4097 nodes is accurate to <1e-10 across p ∈ [0.3, 3].
Below p = 0.1 the inverse table gets very steep (small ΔC ↔ large Δp) so fitted p's
near the floor should be read as "extreme low-p, exact value untrustworthy" rather
than as a precise estimate. We allow p_min as low as 0.01 because it covers the
cul-de-sac / dead-end tail without floor-piling, even though the table is noisy there.
We build a table {(p_i, M(p_i))} on a geometric grid and invert with a monotone-cubic
(PCHIP) spline.  Per-cell inversion is then O(log N) lookups, microseconds each.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.integrate import simpson
from scipy.interpolate import PchipInterpolator


def mean_circuity_of_p(p: float, n_quad: int = 4097) -> float:
    """Compute M(p) = (2/π) ∫_0^{π/2} (cos^p θ + sin^p θ)^{1/p} dθ via Simpson."""
    p = float(p)
    if p <= 0:
        raise ValueError("p must be positive")
    theta = np.linspace(0.0, np.pi / 2.0, n_quad)
    c = np.cos(theta)
    s = np.sin(theta)
    integrand = (c**p + s**p) ** (1.0 / p)
    return float((2.0 / np.pi) * simpson(integrand, x=theta))


def mean_circuity_p_inf() -> float:
    return 2.0 * np.sqrt(2.0) / np.pi


@lru_cache(maxsize=8)
def _build_inverse(p_min: float, p_max: float, n: int):
    p_grid = np.geomspace(p_min, p_max, n)
    C_grid = np.array([mean_circuity_of_p(p) for p in p_grid])
    order = np.argsort(C_grid)
    inv = PchipInterpolator(C_grid[order], p_grid[order], extrapolate=False)
    return p_grid, C_grid, inv


def p_of_circuity(C, p_min: float = 0.01, p_max: float = 3.0, n_table: int = 401):
    """Inverse of M: given mean circuity C, return effective p.

    Out-of-range inputs are clamped to [p_min, p_max].  NaN passes through.
    """
    _, _, inv = _build_inverse(p_min, p_max, n_table)
    arr = np.asarray(C, dtype=float)
    out = inv(arr)
    C_lo = mean_circuity_of_p(p_max)
    C_hi = mean_circuity_of_p(p_min)
    nan_mask = ~np.isfinite(arr)
    out = np.where(arr <= C_lo, p_max, out)
    out = np.where(arr >= C_hi, p_min, out)
    out = np.where(nan_mask, np.nan, out)
    return float(out) if np.ndim(C) == 0 else out


# ─────────────────────────────────────────────────────────────────────────────
# Median variant: same setup as M(p), but reading off the median directional
# circuity over the unit circle instead of the mean.
#
# By the 8-fold symmetry of the L^p ball (X↔−X, Y↔−Y, X↔Y), the distribution
# of (cos^p θ + sin^p θ)^{1/p} for θ ∈ [0, 2π) is the same as its distribution
# over a single octant [0, π/4].  Within that octant the function is monotonic
# in θ for every p > 0, so its median value is its value at the octant midpoint
# θ = π/8.  The integral therefore collapses to a closed form:
#
#     Med(p) = (cos^p(π/8) + sin^p(π/8))^{1/p}
#            = (1/2) · ((2 + √2)^{p/2} + (2 − √2)^{p/2})^{1/p}.
#
# Strictly monotone-decreasing in p, like M.  Boundary values:
#
#     p = 1   :  Med(1)  = cos(π/8) + sin(π/8)         ≈ 1.30656
#     p = 2   :  Med(2)  = 1                            (Euclidean)
#     p → ∞   :  Med(∞) = cos(π/8)                     ≈ 0.92388
# ─────────────────────────────────────────────────────────────────────────────

_COS_PI_8 = float(np.cos(np.pi / 8.0))   # ≈ 0.9238795325112867
_SIN_PI_8 = float(np.sin(np.pi / 8.0))   # ≈ 0.3826834323650898


def quantile_circuity_of_p(p: float, q: float) -> float:
    """Closed-form q-th quantile of L^p directional circuity over the unit ring.

    By the 8-fold symmetry of the L^p ball plus monotonicity of
    f(θ) = (cos^p θ + sin^p θ)^(1/p) on each octant [0, π/4], the distribution
    of f over θ ∈ [0, 2π) is identical to f evaluated uniformly on the octant.
    Therefore the q-th quantile is:

        Q_q(p) = (cos^p(q · π/4) + sin^p(q · π/4))^(1/p)

    Special cases:
        q = 0.5   →  Q_0.5 = (cos^p(π/8) + sin^p(π/8))^(1/p)   (== median)
        q = 0.25  →  axis-leaning quartile
        q = 0.75  →  diagonal-leaning quartile

    Strictly monotone-decreasing in p for any fixed q ∈ (0, 1).
    """
    if not (0.0 < q < 1.0):
        raise ValueError(f"q must be in (0, 1), got {q}")
    p = float(p)
    if not np.isfinite(p):
        if p > 0:
            return float(np.cos(q * np.pi / 4.0))
        raise ValueError("p must be positive")
    if p <= 0:
        raise ValueError("p must be positive")
    alpha = q * np.pi / 4.0
    c, s = np.cos(alpha), np.sin(alpha)
    return float((c**p + s**p) ** (1.0 / p))


@lru_cache(maxsize=16)
def _build_quantile_inverse(q: float, p_min: float, p_max: float, n: int):
    p_grid = np.geomspace(p_min, p_max, n)
    C_grid = np.array([quantile_circuity_of_p(float(p), q) for p in p_grid])
    order = np.argsort(C_grid)
    inv = PchipInterpolator(C_grid[order], p_grid[order], extrapolate=False)
    return p_grid, C_grid, inv


def p_of_quantile_circuity(C, q: float,
                           p_min: float = 0.01, p_max: float = 3.0,
                           n_table: int = 401):
    """Inverse of Q_q: given the q-th quantile of cell circuities, return p.

    Same clamping behavior as ``p_of_circuity`` / ``p_of_median_circuity``.
    """
    if not (0.0 < q < 1.0):
        raise ValueError(f"q must be in (0, 1), got {q}")
    _, _, inv = _build_quantile_inverse(q, p_min, p_max, n_table)
    arr = np.asarray(C, dtype=float)
    out = inv(arr)
    C_lo = quantile_circuity_of_p(p_max, q)
    C_hi = quantile_circuity_of_p(p_min, q)
    nan_mask = ~np.isfinite(arr)
    out = np.where(arr <= C_lo, p_max, out)
    out = np.where(arr >= C_hi, p_min, out)
    out = np.where(nan_mask, np.nan, out)
    return float(out) if np.ndim(C) == 0 else out


def median_circuity_of_p(p: float) -> float:
    """Closed-form median directional circuity for a pure L^p norm.

    No numerical quadrature: the symmetry argument collapses the integral
    to a single function evaluation at θ = π/8.
    """
    p = float(p)
    if not np.isfinite(p):
        if p > 0:
            return _COS_PI_8
        raise ValueError("p must be positive")
    if p <= 0:
        raise ValueError("p must be positive")
    return (_COS_PI_8**p + _SIN_PI_8**p) ** (1.0 / p)


def median_circuity_p_inf() -> float:
    return _COS_PI_8


@lru_cache(maxsize=8)
def _build_median_inverse(p_min: float, p_max: float, n: int):
    p_grid = np.geomspace(p_min, p_max, n)
    C_grid = np.array([median_circuity_of_p(p) for p in p_grid])
    order = np.argsort(C_grid)
    inv = PchipInterpolator(C_grid[order], p_grid[order], extrapolate=False)
    return p_grid, C_grid, inv


def p_of_median_circuity(C, p_min: float = 0.01, p_max: float = 3.0, n_table: int = 401):
    """Inverse of Med: given median circuity C, return effective p.

    Out-of-range inputs are clamped to [p_min, p_max].  NaN passes through.
    """
    _, _, inv = _build_median_inverse(p_min, p_max, n_table)
    arr = np.asarray(C, dtype=float)
    out = inv(arr)
    C_lo = median_circuity_of_p(p_max)
    C_hi = median_circuity_of_p(p_min)
    nan_mask = ~np.isfinite(arr)
    out = np.where(arr <= C_lo, p_max, out)
    out = np.where(arr >= C_hi, p_min, out)
    out = np.where(nan_mask, np.nan, out)
    return float(out) if np.ndim(C) == 0 else out


# ─────────────────────────────────────────────────────────────────────────────
# MLE-based per-cell p estimator.
#
# Uses the FULL distribution of 48 directional circuities per cell, not just
# a moment (mean / median). Model: log c_k = log c_Lp(theta_k; p) + N(0, sigma^2),
# i.e. multiplicative log-Gaussian noise on the L^p prediction. Profiling out
# sigma reduces to least-squares of log-circuity against the L^p curve.
#
# For each cell, minimize over p in [p_min, p_max]:
#     SSR(p) = sum_k ( log c_k − log c_Lp(theta_k; p) )^2
#
# Vectorized across cells via a p-grid + parabolic refinement. ~1 sec for a
# 100k-cell layer at 48 rays.
# ─────────────────────────────────────────────────────────────────────────────


def _c_lp_directional(theta, p):
    """L^p ring circuity at angle(s) ``theta`` for shape exponent ``p``.

    Supports broadcasting: theta shape (n_dirs,), p shape (n_p,) →
    output shape (n_p, n_dirs).
    """
    theta = np.atleast_1d(np.asarray(theta, dtype=float))
    p = np.atleast_1d(np.asarray(p, dtype=float))
    c = np.abs(np.cos(theta))[np.newaxis, :]
    s = np.abs(np.sin(theta))[np.newaxis, :]
    p_col = p[:, np.newaxis]
    return (c**p_col + s**p_col) ** (1.0 / p_col)


def mle_p_from_directional_circuities(
    circuities: np.ndarray,
    theta_dir: np.ndarray,
    p_min: float = 0.30,
    p_max: float = 3.0,
    n_grid: int = 121,
    min_valid_rays: int = 8,
):
    """MLE estimate of effective p per cell from the full 48-ray distribution.

    Parameters
    ----------
    circuities : (n_cells, n_dirs) array
        Per-cell directional circuities. NaN entries are excluded ray-by-ray.
    theta_dir : (n_dirs,) array
        Ray angles in radians.
    p_min, p_max : float
        Bounds of the search range; result is clamped to this interval.
    n_grid : int
        Number of candidate p values on the coarse grid; refined by a
        single parabolic step around the minimum.
    min_valid_rays : int
        Cells with fewer than this many finite circuities return NaN.

    Returns
    -------
    p_mle : (n_cells,) array
        MLE estimate. NaN for cells with insufficient data.
    sigma : (n_cells,) array
        Residual std on log-circuity at the optimum (useful goodness-of-fit
        diagnostic: small = clean L^p, large = the L^p model misfits this cell).
    """
    C = np.asarray(circuities, dtype=float)
    theta = np.asarray(theta_dir, dtype=float)
    n_cells, n_dirs = C.shape
    assert theta.shape == (n_dirs,)

    # Build a p-grid and precompute the predicted log-circuity at each (p, θ).
    p_grid = np.linspace(p_min, p_max, n_grid)  # (n_p,)
    log_C_pred = np.log(_c_lp_directional(theta, p_grid))   # (n_p, n_dirs)

    # Log-circuity of the measurements (NaN where ray failed).
    with np.errstate(invalid="ignore", divide="ignore"):
        log_C = np.log(C)                                   # (n_cells, n_dirs)
    valid = np.isfinite(log_C)                              # (n_cells, n_dirs)
    n_valid = valid.sum(axis=1)                             # (n_cells,)

    # SSR(p) per cell: sum over rays of (log_C - log_C_pred(p))^2, NaNs ignored.
    # Broadcast: log_C[None, :, :]    shape (1, n_cells, n_dirs)
    #            log_C_pred[:, None, :] shape (n_p, 1, n_dirs)
    # Result:    diff shape (n_p, n_cells, n_dirs) — too big at full size, so
    # we loop over p and accumulate the (n_p, n_cells) matrix.
    ssr = np.empty((n_grid, n_cells), dtype=np.float64)
    log_C_filled = np.where(valid, log_C, 0.0)  # NaN-safe
    for ip in range(n_grid):
        diff = log_C_filled - log_C_pred[ip][np.newaxis, :]
        sq = (diff * diff) * valid                          # zero out invalid rays
        ssr[ip] = sq.sum(axis=1)

    # Coarse grid minimum per cell.
    ip_best = np.argmin(ssr, axis=0)                        # (n_cells,)

    # Parabolic refinement around ip_best (3-point fit).
    ip_lo = np.clip(ip_best - 1, 0, n_grid - 1)
    ip_hi = np.clip(ip_best + 1, 0, n_grid - 1)
    y0 = ssr[ip_lo, np.arange(n_cells)]
    y1 = ssr[ip_best, np.arange(n_cells)]
    y2 = ssr[ip_hi, np.arange(n_cells)]
    denom = y0 - 2 * y1 + y2
    delta = np.where(np.abs(denom) > 1e-12, 0.5 * (y0 - y2) / denom, 0.0)
    delta = np.clip(delta, -1.0, 1.0)
    p_best = p_grid[ip_best] + delta * (p_grid[1] - p_grid[0])
    p_best = np.clip(p_best, p_min, p_max)

    # Residual std at the optimum (using coarse value, close enough).
    sigma = np.sqrt(ssr[ip_best, np.arange(n_cells)] / np.maximum(n_valid - 1, 1))

    # Cells with too few rays → NaN.
    bad = n_valid < min_valid_rays
    p_best = np.where(bad, np.nan, p_best)
    sigma = np.where(bad, np.nan, sigma)
    return p_best, sigma
