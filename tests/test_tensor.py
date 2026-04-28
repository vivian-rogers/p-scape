"""Synthetic-ellipse sanity checks for the tensor fit.

We generate a polygon that IS the geodesic ball of a known g, in projected meters,
then check that fit_local_tensor recovers g.
"""
from __future__ import annotations

import numpy as np
import pytest
from pyproj import Transformer
from shapely.geometry import Polygon

from isochrone_metric.tensor import (
    DEFAULT_PROJECTED_CRS,
    WGS84,
    deviation,
    euclidean_reference_g,
    fit_local_tensor,
)


def _ellipse_polygon_lonlat(
    origin_lat: float,
    origin_lon: float,
    g: np.ndarray,
    t_seconds: float,
    n: int = 360,
) -> Polygon:
    """Build the ellipse {v : vᵀ g v = t²} around the origin and inverse-project to WGS84."""
    tr_fwd = Transformer.from_crs(WGS84, DEFAULT_PROJECTED_CRS, always_xy=True)
    tr_inv = Transformer.from_crs(DEFAULT_PROJECTED_CRS, WGS84, always_xy=True)
    ox, oy = tr_fwd.transform(origin_lon, origin_lat)

    thetas = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pts = []
    for th in thetas:
        u = np.array([np.cos(th), np.sin(th)])
        # r such that r² uᵀ g u = t² → r = t / sqrt(uᵀ g u)
        r = t_seconds / np.sqrt(u @ g @ u)
        pts.append((ox + r * u[0], oy + r * u[1]))
    xs, ys = zip(*pts)
    lons, lats = tr_inv.transform(xs, ys)
    return Polygon(zip(lons, lats))


@pytest.mark.parametrize(
    "v_along, v_cross, theta_deg",
    [
        (15.0, 15.0, 0.0),    # isotropic, 15 m/s
        (25.0, 8.0, 0.0),     # E-W highway anisotropy
        (25.0, 8.0, 45.0),    # rotated 45°
        (30.0, 5.0, -30.0),   # strong anisotropy
    ],
)
def test_recovers_known_metric(v_along: float, v_cross: float, theta_deg: float) -> None:
    """Build an ellipse from a known g, fit, recover g."""
    th = np.deg2rad(theta_deg)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    # Diagonal in principal axes: g_ii = 1/v_i²
    g_diag = np.diag([1.0 / v_along**2, 1.0 / v_cross**2])
    g_true = R @ g_diag @ R.T

    origin = (30.2672, -97.7431)  # downtown Austin
    t = 600.0  # 10 minutes
    poly = _ellipse_polygon_lonlat(origin[0], origin[1], g_true, t, n=360)

    fit = fit_local_tensor(poly, origin[0], origin[1], t)
    rel_err = np.linalg.norm(fit.g - g_true, ord="fro") / np.linalg.norm(g_true, ord="fro")
    assert rel_err < 1e-3, f"Frobenius rel error {rel_err:.2e}, residual {fit.residual_rms:.2e}"
    assert fit.residual_rms < 1e-3


def test_anisotropy_and_mean_speed() -> None:
    g_true = np.diag([1.0 / 25.0**2, 1.0 / 5.0**2])
    poly = _ellipse_polygon_lonlat(30.2672, -97.7431, g_true, 600.0, n=360)
    fit = fit_local_tensor(poly, 30.2672, -97.7431, 600.0)
    assert abs(fit.anisotropy - 5.0) < 0.01  # 25/5
    # mean_speed = (det g)^(-1/4) = (1/(25²·5²))^(-1/4) = sqrt(25·5) ≈ 11.18
    assert abs(fit.mean_speed - np.sqrt(25 * 5)) < 0.05


def test_euclidean_reference_and_deviation_zero() -> None:
    v_bar = 15.0
    g_E = euclidean_reference_g(v_bar)
    poly = _ellipse_polygon_lonlat(30.2672, -97.7431, g_E, 600.0, n=360)
    fit = fit_local_tensor(poly, 30.2672, -97.7431, 600.0)
    d = deviation(fit.g, g_E)
    assert d["frobenius"] < 1e-4
    assert d["deviatoric_frobenius"] < 1e-4
