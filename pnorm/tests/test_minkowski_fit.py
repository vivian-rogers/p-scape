"""Synthetic validation of the rotated anisotropic Minkowski fit.

Also pins down the estimator-bias story that motivates it:
- moment estimators (mean/median circuity → p) are rotation-IMMUNE,
- the axis-aligned ray-pattern MLE is rotation-BIASED (reads a rotated
  grid as spuriously high p),
- all axis-aligned estimators read anisotropy as spuriously low p.
"""

import numpy as np
import pytest

from pnorm.lp_inversion import (
    mean_circuity_of_p,
    median_circuity_of_p,
    mle_p_from_directional_circuities,
    p_of_circuity,
)
from pnorm.minkowski_fit import c_minkowski, fit_minkowski

K = 48
THETA = np.linspace(0.0, 2.0 * np.pi, K, endpoint=False)


def angdist_pi(x, y):
    """Angular distance between orientations (mod π)."""
    return np.abs(np.mod(x - y + np.pi / 2.0, np.pi) - np.pi / 2.0)


def test_forward_model_special_cases():
    theta = np.linspace(0, 2 * np.pi, 999)
    assert np.allclose(c_minkowski(theta, p=2.0), 1.0)
    c1 = c_minkowski(theta, p=1.0)
    assert np.isclose(c1.max(), np.sqrt(2.0))
    assert np.isclose(c1.min(), 1.0)
    alpha = 0.7
    assert np.allclose(
        c_minkowski(theta, 1.3, alpha=alpha, a=0.9, b=0.6),
        c_minkowski(theta - alpha, 1.3, a=0.9, b=0.6),
    )


def test_moment_estimators_are_rotation_immune():
    theta = np.linspace(0, 2 * np.pi, 200_001)
    for alpha in (0.0, np.pi / 4, 1.1):
        c = c_minkowski(theta, p=1.0, alpha=alpha)
        assert np.isclose(c.mean(), mean_circuity_of_p(1.0), atol=1e-4)
        assert np.isclose(np.median(c), median_circuity_of_p(1.0), atol=1e-4)


def test_mle_is_rotation_biased_and_rotated_fit_is_not():
    c = c_minkowski(THETA, p=1.0, alpha=np.pi / 4)[np.newaxis, :]
    p_mle, sigma_mle = mle_p_from_directional_circuities(c, THETA)
    # rotation de-phases the modulation: p drifts toward 2, misfit explodes
    assert p_mle[0] > 1.08
    assert sigma_mle[0] > 0.15

    fit = fit_minkowski(c, THETA)
    assert np.isclose(fit.p_rot[0], 1.0, atol=0.02)
    assert angdist_pi(fit.alpha_rot[0], np.pi / 4) < np.deg2rad(1.0)
    assert np.isclose(fit.p[0], 1.0, atol=0.05)
    assert np.isclose(fit.kappa[0], 1.0, atol=0.02)


def test_anisotropy_biases_axis_aligned_p_downward():
    a, b = 1.0, 0.7
    c = c_minkowski(THETA, p=1.0, a=a, b=b)
    p_moment = p_of_circuity(float(c.mean()))
    assert p_moment < 0.9  # slow axis read as cul-de-sac-ness

    fit = fit_minkowski(c[np.newaxis, :], THETA)
    assert np.isclose(fit.p[0], 1.0, atol=0.05)
    assert np.isclose(fit.kappa[0], b / a, atol=0.03)
    assert angdist_pi(fit.alpha[0], 0.0) < np.deg2rad(3.0)


def test_recovery_under_noise_and_missing_rays():
    rng = np.random.default_rng(42)
    n = 300
    p = rng.uniform(0.6, 2.5, n)
    alpha = rng.uniform(0.0, np.pi, n)
    a = rng.uniform(0.7, 1.0, n)
    b = a * rng.uniform(0.55, 1.0, n)
    sigma = 0.05

    C = np.empty((n, K))
    for i in range(n):
        C[i] = c_minkowski(THETA, p[i], alpha[i], a[i], b[i])
    C *= np.exp(sigma * rng.standard_normal(C.shape))
    C[rng.random(C.shape) < 0.10] = np.nan

    fit = fit_minkowski(C, THETA)
    ok = np.isfinite(fit.p)
    assert ok.mean() > 0.95
    assert np.median(np.abs(fit.p[ok] - p[ok])) < 0.08
    assert np.median(np.abs(fit.kappa[ok] - b[ok] / a[ok])) < 0.05

    # α is only identifiable away from the isotropic degeneracy
    ident = ok & (b / a < 0.9)
    ang_err = angdist_pi(fit.alpha[ident], alpha[ident])
    assert np.median(ang_err) < np.deg2rad(4.0)

    # the full model should explain anisotropic cells better than M0
    p_mle, sigma_mle = mle_p_from_directional_circuities(C, THETA)
    aniso = ident & np.isfinite(sigma_mle)
    assert np.median(sigma_mle[aniso] - fit.sigma[aniso]) > 0.0


def test_min_valid_rays_gate():
    c = c_minkowski(THETA, p=1.0)[np.newaxis, :].copy()
    c[0, 5:] = np.nan  # 5 valid rays < default gate of 8
    fit = fit_minkowski(c, THETA)
    for field in (fit.p, fit.alpha, fit.kappa, fit.sigma, fit.p_rot):
        assert np.isnan(field[0])
    assert fit.n_valid[0] == 5


def test_chunking_is_transparent():
    rng = np.random.default_rng(7)
    C = c_minkowski(THETA, p=1.2, alpha=0.5, a=0.9, b=0.8)[np.newaxis, :]
    C = np.repeat(C, 10, axis=0) * np.exp(0.03 * rng.standard_normal((10, K)))
    whole = fit_minkowski(C, THETA)
    parts = fit_minkowski(C, THETA, chunk=3)
    np.testing.assert_allclose(whole.p, parts.p)
    np.testing.assert_allclose(whole.alpha, parts.alpha)
    np.testing.assert_allclose(whole.sigma, parts.sigma)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
