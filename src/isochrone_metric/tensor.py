"""Fit a local effective-time tensor g(x) from one isochrone polygon.

See docs/math.md. For each boundary point at angle θ and projected distance r
from the origin, we have

    r² (cos²θ · g11 + 2 cosθ sinθ · g12 + sin²θ · g22) = t²

with t the contour time (seconds). Stack the rows, solve in least squares.
The recovered g is symmetric 2×2 with units (s/m)².
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon

# UTM Zone 14N covers central Texas (Austin). Swap for other regions.
DEFAULT_PROJECTED_CRS = "EPSG:32614"
WGS84 = "EPSG:4326"


@dataclass(frozen=True)
class LocalTensor:
    """Fitted local quadratic form. Units of g entries: (s/m)²."""

    g: np.ndarray  # (2, 2) symmetric
    origin_xy: tuple[float, float]  # in projected coords (meters)
    t_seconds: float
    residual_rms: float  # rms of (predicted t² − actual t²), normalized by t²

    @property
    def eigvals(self) -> np.ndarray:
        return np.linalg.eigvalsh(self.g)

    @property
    def anisotropy(self) -> float:
        """Ratio of slow-axis to fast-axis travel time. >= 1, equals 1 iff isotropic."""
        l = self.eigvals  # ascending
        if l[0] <= 0:
            return float("inf")
        return float(np.sqrt(l[1] / l[0]))

    @property
    def mean_speed(self) -> float:
        """Effective isotropic speed (m/s) implied by det(g)^(1/4)."""
        d = float(np.linalg.det(self.g))
        if d <= 0:
            return float("nan")
        return float(d ** (-0.25))


def _project_to_xy(
    lat: float, lon: float, polygon_lonlat: Polygon, crs: str
) -> tuple[tuple[float, float], np.ndarray]:
    """Project origin + polygon ring to a local meter CRS.

    Returns (origin_xy, ring_xy) where ring_xy is (N, 2).
    """
    tr = Transformer.from_crs(WGS84, crs, always_xy=True)
    ox, oy = tr.transform(lon, lat)
    coords = np.asarray(polygon_lonlat.exterior.coords)  # (N, 2) lon,lat
    xs, ys = tr.transform(coords[:, 0], coords[:, 1])
    return (ox, oy), np.column_stack([xs, ys])


def fit_local_tensor(
    polygon_lonlat: Polygon,
    origin_lat: float,
    origin_lon: float,
    t_seconds: float,
    *,
    projected_crs: str = DEFAULT_PROJECTED_CRS,
) -> LocalTensor:
    """Fit g(x) from one isochrone polygon at travel-time t.

    The polygon is the level set {y : τ(x, y) ≤ t}, in WGS84 lon/lat.
    """
    if t_seconds <= 0:
        raise ValueError("t_seconds must be positive")

    (ox, oy), ring = _project_to_xy(origin_lat, origin_lon, polygon_lonlat, projected_crs)
    dx = ring[:, 0] - ox
    dy = ring[:, 1] - oy
    r2 = dx * dx + dy * dy
    nz = r2 > 0
    dx, dy, r2 = dx[nz], dy[nz], r2[nz]

    # cos θ = dx/r, sin θ = dy/r → r² cos²θ = dx², r² sin²θ = dy², 2 r² cosθ sinθ = 2 dx dy
    A = np.column_stack([dx * dx, 2.0 * dx * dy, dy * dy])
    b = np.full(A.shape[0], t_seconds * t_seconds)

    # Solve A · [g11, g12, g22] = b in least squares.
    # Light regularization toward isotropic mean prevents pathological fits when
    # the polygon is a near-degenerate sliver. The prior is weak (lambda ≈ 1e-6).
    lam = 1e-6
    AtA = A.T @ A + lam * np.eye(3)
    Atb = A.T @ b
    g11, g12, g22 = np.linalg.solve(AtA, Atb)
    g = np.array([[g11, g12], [g12, g22]], dtype=float)

    # Project to PSD cone if a bad polygon pulled us slightly negative.
    w, V = np.linalg.eigh(g)
    if (w <= 0).any():
        w = np.clip(w, 1e-12, None)
        g = V @ np.diag(w) @ V.T

    pred = A @ np.array([g[0, 0], g[0, 1], g[1, 1]])
    rms = float(np.sqrt(np.mean(((pred - b) / (t_seconds * t_seconds)) ** 2)))

    return LocalTensor(g=g, origin_xy=(ox, oy), t_seconds=t_seconds, residual_rms=rms)


def euclidean_reference_g(reference_speed_mps: float) -> np.ndarray:
    """The Euclidean metric g_E = (1/v̄²) I."""
    inv = 1.0 / (reference_speed_mps * reference_speed_mps)
    return np.array([[inv, 0.0], [0.0, inv]])


def deviation(g: np.ndarray, g_ref: np.ndarray) -> dict[str, float]:
    """Decompose Δ = g − g_ref into trace + deviatoric parts."""
    delta = g - g_ref
    tr = float(np.trace(delta))
    iso = 0.5 * tr * np.eye(2)
    dev = delta - iso
    return {
        "trace_half": 0.5 * tr,
        "deviatoric_frobenius": float(np.linalg.norm(dev, ord="fro")),
        "frobenius": float(np.linalg.norm(delta, ord="fro")),
    }
