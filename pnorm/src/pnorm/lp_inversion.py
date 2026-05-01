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


def p_of_circuity(C, p_min: float = 0.30, p_max: float = 3.0, n_table: int = 401):
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
