from __future__ import annotations

import numpy as np

from .geo import AUSTIN_BBOX, to_lonlat, to_utm


def stratified_od_pairs(n, d_min=500.0, d_max=20000.0, bbox=AUSTIN_BBOX, seed=0):
    """Sample n (origin, destination) lon/lat pairs.

    Origin uniform in bbox. Destination at uniform-random heading θ and
    uniform-random distance d ∈ [d_min, d_max] meters in UTM space.
    Destinations outside bbox are rejected and resampled — avoids the
    long-diagonal bias of picking two uniform bbox points.
    """
    rng = np.random.default_rng(seed)
    min_lon, min_lat, max_lon, max_lat = bbox
    origins, dests = [], []
    while len(origins) < n:
        need = n - len(origins)
        batch = max(need * 2, 64)
        o_lon = rng.uniform(min_lon, max_lon, batch)
        o_lat = rng.uniform(min_lat, max_lat, batch)
        o_x, o_y = to_utm(o_lon, o_lat)
        theta = rng.uniform(0, 2 * np.pi, batch)
        d = rng.uniform(d_min, d_max, batch)
        d_x = np.asarray(o_x) + d * np.cos(theta)
        d_y = np.asarray(o_y) + d * np.sin(theta)
        d_lon, d_lat = to_lonlat(d_x, d_y)
        d_lon = np.asarray(d_lon)
        d_lat = np.asarray(d_lat)
        keep = (d_lon >= min_lon) & (d_lon <= max_lon) & (d_lat >= min_lat) & (d_lat <= max_lat)
        idx = np.where(keep)[0][:need]
        for i in idx:
            origins.append((float(o_lon[i]), float(o_lat[i])))
            dests.append((float(d_lon[i]), float(d_lat[i])))
    return np.array(origins), np.array(dests)
