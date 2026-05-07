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
        # urban core, ~14x22 km; previous wider metro bbox (1260 km²) was too large
        # for the unified walking grid at 75 m spacing.
        bbox=(-97.80, 30.20, -97.65, 30.40),
        utm_epsg=32614,  # UTM 14N
        geofabrik_region="north-america/us/texas",
        center=(30.27, -97.73),
        default_zoom=11,
    ),
    "nyc": City(
        key="nyc",
        name="New York City",
        # Manhattan + Park Slope + LIC + Astoria + South Bronx; ~15x21 km
        bbox=(-74.03, 40.66, -73.85, 40.85),
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
    "barcelona": City(
        key="barcelona",
        name="Barcelona, Spain",
        # Wider Barcelona: W to Les Corts/Pedralbes (~2.08), E to Sant Adrià
        # (~2.24, captures 22@/Diagonal Mar/Forum + a sliver of Badalona),
        # N to Horta-Guinardó ridge. Gives the Cerdà grid lots of room while
        # still including older industrial fringe and car-oriented W
        # neighborhoods for contrast. ~16 × 11 km ≈ 178 km².
        bbox=(2.08, 41.36, 2.24, 41.46),
        utm_epsg=32631,  # UTM 31N
        geofabrik_region="europe/spain",
        center=(41.3874, 2.1686),  # Plaça de Catalunya
        default_zoom=12,
    ),
    "paris": City(
        key="paris",
        name="Paris, France",
        # Intra-périphérique plus inner banlieue (Boulogne-Billancourt,
        # Levallois, Saint-Ouen, Pantin, Vincennes, Issy). ~16 × 12 km ≈
        # 192 km².
        bbox=(2.23, 48.81, 2.45, 48.92),
        utm_epsg=32631,  # UTM 31N
        geofabrik_region="europe/france/ile-de-france",
        center=(48.857, 2.347),  # Notre-Dame
        default_zoom=12,
    ),
    "dc": City(
        key="dc",
        name="Washington, DC",
        # L'Enfant diamond + Adams Morgan + Capitol Hill + Anacostia +
        # Arlington edge + inner Bethesda. Captures the radial diagonals.
        bbox=(-77.13, 38.81, -76.94, 39.00),
        utm_epsg=32618,  # UTM 18N (same as NYC; DC is at -77° W)
        geofabrik_region="north-america/us/district-of-columbia",
        center=(38.8951, -77.0364),  # White House-ish
        default_zoom=12,
    ),
    "venice": City(
        key="venice",
        name="Venice, Italy",
        # Historic islands only — cars can't reach island origins, so we
        # only run foot for Venice.
        bbox=(12.30, 45.42, 12.38, 45.46),
        utm_epsg=32633,  # UTM 33N
        geofabrik_region="europe/italy/nord-est",
        center=(45.4408, 12.3155),  # Piazzale Roma — main island entry
        default_zoom=14,
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
