from __future__ import annotations

import numpy as np

from .geo import AUSTIN_BBOX, to_lonlat, to_utm


def _utm_bbox(bbox_lonlat, inset_m):
    """Project lon/lat bbox corners to UTM, return inset (x_min, x_max, y_min, y_max)."""
    min_lon, min_lat, max_lon, max_lat = bbox_lonlat
    xs = [to_utm(min_lon, min_lat), to_utm(max_lon, min_lat),
          to_utm(min_lon, max_lat), to_utm(max_lon, max_lat)]
    x_min = min(p[0] for p in xs) + inset_m
    x_max = max(p[0] for p in xs) - inset_m
    y_min = min(p[1] for p in xs) + inset_m
    y_max = max(p[1] for p in xs) - inset_m
    return x_min, x_max, y_min, y_max


def hex_grid_utm(bbox_lonlat=AUSTIN_BBOX, spacing_m=1500.0, inset_m=0.0):
    """Generate hex-grid points in UTM covering the bbox, optionally inset.

    Returns (xy_utm (N,2), lonlat (N,2)).
    """
    x_min, x_max, y_min, y_max = _utm_bbox(bbox_lonlat, inset_m)

    dx = spacing_m
    dy = spacing_m * (np.sqrt(3) / 2)

    pts = []
    row = 0
    y = y_min
    while y <= y_max:
        offset = (dx / 2) if (row % 2) else 0.0
        x = x_min + offset
        while x <= x_max:
            pts.append((x, y))
            x += dx
        y += dy
        row += 1

    xy = np.asarray(pts, dtype=float)
    lon, lat = to_lonlat(xy[:, 0], xy[:, 1])
    return xy, np.column_stack([np.asarray(lon), np.asarray(lat)])


def square_grid_utm(bbox_lonlat=AUSTIN_BBOX, spacing_m=75.0, inset_m=0.0):
    """Generate square-lattice points in UTM covering the bbox, optionally inset.

    Tile centers on a regular square grid at ``spacing_m`` pitch. Deterministic,
    no jitter — per-tile randomization is reserved for a future multi-origin
    Monte Carlo mode.

    Returns (xy_utm (N,2), lonlat (N,2)) — same shape as ``hex_grid_utm()``.
    """
    x_min, x_max, y_min, y_max = _utm_bbox(bbox_lonlat, inset_m)
    xs = np.arange(x_min, x_max + 1e-6, spacing_m)
    ys = np.arange(y_min, y_max + 1e-6, spacing_m)
    xx, yy = np.meshgrid(xs, ys)
    xy = np.column_stack([xx.ravel(), yy.ravel()])
    lon, lat = to_lonlat(xy[:, 0], xy[:, 1])
    return xy, np.column_stack([np.asarray(lon), np.asarray(lat)])
