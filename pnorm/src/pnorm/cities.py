"""City catalog for cross-region p-norm analysis.

Each entry pins the bbox we'll crop OSM to, the right UTM zone for distance work,
the Geofabrik region path that contains it, and a sensible default folium map view.

Usage:
    from pnorm.cities import use_city
    city = use_city("nyc")     # also flips the geo module's UTM zone
    print(city.bbox)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    key: str
    name: str
    # (min_lon, min_lat, max_lon, max_lat) — the OSM bbox we crop to.
    bbox: tuple[float, float, float, float]
    # EPSG code for the UTM zone covering the bbox. Used for local-meters distance work.
    utm_epsg: int
    # Path under download.geofabrik.de — e.g. "north-america/us/texas" → fetches the .osm.pbf
    geofabrik_region: str
    # (lat, lon) — folium map default center.
    center: tuple[float, float]
    default_zoom: int


CITIES: dict[str, City] = {
    "austin": City(
        key="austin",
        name="Austin, TX",
        bbox=(-97.88, 30.12, -97.58, 30.50),
        utm_epsg=32614,  # UTM 14N
        geofabrik_region="north-america/us/texas",
        center=(30.27, -97.73),
        default_zoom=11,
    ),
    "nyc": City(
        key="nyc",
        name="New York City",
        bbox=(-74.04, 40.68, -73.86, 40.83),  # Manhattan + adjacent boroughs
        utm_epsg=32618,  # UTM 18N
        geofabrik_region="north-america/us/new-york",
        center=(40.7589, -73.9857),  # Times Square
        default_zoom=12,
    ),
    "houston": City(
        key="houston",
        name="Houston, TX",
        bbox=(-95.60, 29.55, -95.20, 29.95),  # downtown + inner loop
        utm_epsg=32615,  # UTM 15N
        geofabrik_region="north-america/us/texas",
        center=(29.7604, -95.3698),
        default_zoom=11,
    ),
    "sf": City(
        key="sf",
        name="San Francisco, CA",
        bbox=(-122.52, 37.70, -122.35, 37.83),
        utm_epsg=32610,  # UTM 10N
        geofabrik_region="north-america/us/california",
        center=(37.7749, -122.4194),
        default_zoom=12,
    ),
    "chicago": City(
        key="chicago",
        name="Chicago, IL",
        bbox=(-87.80, 41.78, -87.55, 42.00),
        utm_epsg=32616,  # UTM 16N
        geofabrik_region="north-america/us/illinois",
        center=(41.8781, -87.6298),
        default_zoom=11,
    ),
    "boston": City(
        key="boston",
        name="Boston, MA",
        bbox=(-71.18, 42.30, -71.00, 42.40),
        utm_epsg=32619,  # UTM 19N
        geofabrik_region="north-america/us/massachusetts",
        center=(42.3601, -71.0589),
        default_zoom=12,
    ),
}


def get_city(key: str) -> City:
    if key not in CITIES:
        raise KeyError(f"unknown city {key!r}; known: {sorted(CITIES)}")
    return CITIES[key]


def use_city(key: str) -> City:
    """Look up a city *and* set the geo module's UTM projection to match it."""
    from . import geo

    c = get_city(key)
    geo.set_utm_epsg(c.utm_epsg)
    return c
