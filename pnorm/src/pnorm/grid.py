from __future__ import annotations

import numpy as np

from .geo import AUSTIN_BBOX, to_lonlat, to_utm


def hex_grid_utm(bbox_lonlat=AUSTIN_BBOX, spacing_m=1500.0, inset_m=0.0):
    """Generate hex-grid points in UTM covering the bbox, optionally inset.

    Returns (xy_utm (N,2), lonlat (N,2)).
    """
    min_lon, min_lat, max_lon, max_lat = bbox_lonlat
    xs = [to_utm(min_lon, min_lat), to_utm(max_lon, min_lat),
          to_utm(min_lon, max_lat), to_utm(max_lon, max_lat)]
    x_min = min(p[0] for p in xs) + inset_m
    x_max = max(p[0] for p in xs) - inset_m
    y_min = min(p[1] for p in xs) + inset_m
    y_max = max(p[1] for p in xs) - inset_m

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
