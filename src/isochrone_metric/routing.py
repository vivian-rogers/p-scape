"""Thin client for the local Valhalla `/isochrone` endpoint."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence

import requests
from shapely.geometry import Polygon, shape

DEFAULT_URL = os.environ.get("ROUTING_URL", "http://localhost:8002")


@dataclass(frozen=True)
class Isochrone:
    """A single isochrone polygon at a given travel-time contour."""

    minutes: float
    polygon: Polygon  # in WGS84 (lon, lat)


def fetch_isochrones(
    lat: float,
    lon: float,
    minutes: Sequence[float],
    *,
    costing: str = "auto",
    url: str = DEFAULT_URL,
    timeout: float = 30.0,
) -> list[Isochrone]:
    """POST /isochrone for a single origin and one or more time contours.

    Returns isochrones sorted ascending by minutes. Polygons are in WGS84.
    """
    body = {
        "locations": [{"lat": lat, "lon": lon}],
        "costing": costing,
        "contours": [{"time": float(m)} for m in minutes],
        "polygons": True,
    }
    r = requests.post(f"{url}/isochrone", json=body, timeout=timeout)
    r.raise_for_status()
    feats = r.json().get("features", [])

    out: list[Isochrone] = []
    for f in feats:
        props = f.get("properties", {})
        # Valhalla returns either `contour` (numeric minutes) or `metric=time, contour=N`.
        contour = props.get("contour")
        geom = shape(f["geometry"])
        # Valhalla can return MultiPolygon for disconnected components — keep largest.
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda g: g.area)
        out.append(Isochrone(minutes=float(contour), polygon=geom))
    out.sort(key=lambda i: i.minutes)
    return out
