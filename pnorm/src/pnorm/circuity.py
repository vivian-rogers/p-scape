from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geo import to_lonlat, to_utm
from .osrm import OSRM


@dataclass
class CircuityResult:
    origin_lonlat: tuple[float, float]
    origin_xy: tuple[float, float]
    dest_xy: np.ndarray          # (n, 2) UTM
    d_route: np.ndarray          # (n,) meters
    d_euclid: np.ndarray         # (n,) meters
    t_route: np.ndarray          # (n,) seconds
    theta: np.ndarray            # (n,) radians, 0 = east

    @property
    def excess_m(self) -> np.ndarray:
        return self.d_route - self.d_euclid

    @property
    def circuity(self) -> np.ndarray:
        return self.d_route / self.d_euclid

    def summary(self) -> dict:
        ok = np.isfinite(self.d_route) & (self.d_euclid > 0)
        return {
            "n": int(ok.sum()),
            "mean_excess_m": float(self.excess_m[ok].mean()),
            "median_excess_m": float(np.median(self.excess_m[ok])),
            "mean_circuity": float(self.circuity[ok].mean()),
            "median_circuity": float(np.median(self.circuity[ok])),
            "p95_circuity": float(np.percentile(self.circuity[ok], 95)),
        }


def ring_destinations(origin_lonlat, radius_m, n, jitter=0.0, seed=0):
    """Place n destinations on a circle of radius `radius_m` around origin (lonlat).

    Returns dest lonlat array (n,2) and angles θ (radians, 0 = east, CCW).
    """
    rng = np.random.default_rng(seed)
    o_x, o_y = to_utm(origin_lonlat[0], origin_lonlat[1])
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if jitter > 0:
        theta = theta + rng.uniform(-jitter, jitter, n)
    r = np.full(n, float(radius_m))
    dx = np.asarray(o_x) + r * np.cos(theta)
    dy = np.asarray(o_y) + r * np.sin(theta)
    d_lon, d_lat = to_lonlat(dx, dy)
    return np.column_stack([np.asarray(d_lon), np.asarray(d_lat)]), theta


def circuity_from_origin(
    origin_lonlat, radius_m, n_dests, osrm: OSRM, seed=0, max_snap_frac=0.25
) -> CircuityResult:
    """For a single origin, probe n_dests at radius_m; return route distance, time, euclid, θ.

    Uses OSRM's snapped endpoints to compute d_euclid (so ratio is truly network-vs-straight on
    the graph). Destinations whose snap offset exceeds max_snap_frac * radius_m are dropped — they
    indicate a node too far from the target point for the result to be meaningful.
    """
    dests_lonlat, theta = ring_destinations(origin_lonlat, radius_m, n_dests, seed=seed)
    t, d, src_snap, dst_snap = osrm.table(
        [tuple(origin_lonlat)],
        [tuple(p) for p in dests_lonlat],
        annotations="duration,distance",
        return_snapped=True,
    )
    t = t[0]
    d_route = d[0]

    o_x, o_y = to_utm(origin_lonlat[0], origin_lonlat[1])
    osnap_x, osnap_y = to_utm(src_snap[0, 0], src_snap[0, 1])
    dsnap_x, dsnap_y = to_utm(dst_snap[:, 0], dst_snap[:, 1])
    dx, dy = to_utm(dests_lonlat[:, 0], dests_lonlat[:, 1])

    d_euclid = np.hypot(
        np.asarray(dsnap_x) - float(osnap_x), np.asarray(dsnap_y) - float(osnap_y)
    )
    snap_offset = np.hypot(np.asarray(dsnap_x) - np.asarray(dx), np.asarray(dsnap_y) - np.asarray(dy))
    bad = snap_offset > max_snap_frac * radius_m
    d_route = d_route.copy()
    d_route[bad] = np.nan

    return CircuityResult(
        origin_lonlat=tuple(origin_lonlat),
        origin_xy=(float(osnap_x), float(osnap_y)),
        dest_xy=np.column_stack([np.asarray(dsnap_x), np.asarray(dsnap_y)]),
        d_route=d_route,
        d_euclid=d_euclid,
        t_route=t,
        theta=theta,
    )
