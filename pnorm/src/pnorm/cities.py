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
        name="San Francisco + Peninsula",
        # Extended south down the Peninsula to include Daly City, South SF,
        # San Bruno, Millbrae, Burlingame, Hillsborough, San Mateo. Adds
        # 19 km of car/transit-dominated suburban grid that contrasts SF
        # proper's hill-and-grid mix.
        bbox=(-122.52, 37.53, -122.25, 37.83),
        utm_epsg=32610,  # UTM 10N
        geofabrik_region="north-america/us/california",
        center=(37.7749, -122.4194),
        default_zoom=11,
    ),
    "la": City(
        key="la",
        name="Los Angeles, CA",
        # Santa Monica → East LA, Inglewood → Glendale/Burbank. Excludes the
        # SF Valley, Long Beach, and the San Gabriel Valley.
        bbox=(-118.55, 33.92, -118.18, 34.20),
        utm_epsg=32611,  # UTM 11N
        geofabrik_region="north-america/us/california",
        center=(34.0522, -118.2437),
        default_zoom=11,
    ),
    "chicago": City(
        key="chicago",
        name="Chicago, IL",
        bbox=(-87.80, 41.78, -87.55, 42.10),  # extended north to include Evanston + Wilmette
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
    "lansing": City(
        key="lansing",
        name="Lansing, MI",
        # Lansing core + East Lansing / MSU campus. ~16 × 14 km.
        bbox=(-84.65, 42.65, -84.45, 42.78),
        utm_epsg=32616,  # UTM 16N
        geofabrik_region="north-america/us/michigan",
        center=(42.7325, -84.5555),
        default_zoom=12,
    ),
    "seattle": City(
        key="seattle",
        name="Seattle, WA",
        # Downtown + Capitol Hill + Ballard + U District + West Seattle +
        # Beacon Hill + Rainier Valley. ~15 × 24 km. Excludes Bellevue
        # (different street logic across the lake).
        bbox=(-122.45, 47.50, -122.25, 47.72),
        utm_epsg=32610,  # UTM 10N
        geofabrik_region="north-america/us/washington",
        center=(47.6062, -122.3321),
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
    "villages": City(
        key="villages",
        name="The Villages, FL",
        # Golf-cart retirement-community sprawl: cul-de-sac dominant, low p.
        bbox=(-82.10, 28.85, -81.92, 29.00),
        utm_epsg=32617,  # UTM 17N
        geofabrik_region="north-america/us/florida",
        center=(28.9341, -82.0089),
        default_zoom=12,
    ),
    "karlsruhe": City(
        key="karlsruhe",
        name="Karlsruhe, Germany",
        # The textbook radial fan: 32 streets radiating from the Schloss.
        bbox=(8.32, 48.95, 8.50, 49.06),
        utm_epsg=32632,  # UTM 32N
        geofabrik_region="europe/germany/baden-wuerttemberg",
        center=(49.0094, 8.4044),  # Marktplatz
        default_zoom=12,
    ),
    "rome": City(
        key="rome",
        name="Rome, Italy",
        # Centro Storico + Trastevere + Vatican + early ring suburbs.
        bbox=(12.40, 41.85, 12.55, 41.95),
        utm_epsg=32633,  # UTM 33N
        geofabrik_region="europe/italy/centro",
        center=(41.9028, 12.4964),  # Roman Forum-ish
        default_zoom=12,
    ),
    "tokyo": City(
        key="tokyo",
        name="Tokyo (Shitamachi)",
        # Asakusa + Ueno + Yanaka + Nezu + Sendagi — the historic "low city"
        # of pre-modern street layouts; not a grid, very pedestrian.
        bbox=(139.73, 35.68, 139.84, 35.76),
        utm_epsg=32654,  # UTM 54N
        geofabrik_region="asia/japan/kanto",
        center=(35.7148, 139.7967),  # Asakusa-ish
        default_zoom=13,
    ),
    "mexico_city": City(
        key="mexico_city",
        name="Mexico City",
        # Centro Histórico (Tenochtitlán grid heritage) + Reforma diagonal +
        # Roma/Condesa Haussmann + Polanco + Coyoacán north.
        bbox=(-99.22, 19.35, -99.05, 19.48),
        utm_epsg=32614,  # UTM 14N
        geofabrik_region="north-america/mexico",
        center=(19.4326, -99.1332),  # Zócalo
        default_zoom=12,
    ),
    "brasilia": City(
        key="brasilia",
        name="Brasília",
        # Niemeyer's Plano Piloto — modernist "airplane" plan, designed
        # explicitly for cars; expect low p_mean from the superblock fabric.
        bbox=(-47.95, -15.85, -47.80, -15.74),
        utm_epsg=32723,  # UTM 23S
        geofabrik_region="south-america/brazil/centro-oeste",
        center=(-15.7975, -47.8919),  # Praça dos Três Poderes
        default_zoom=12,
    ),
    "london_on": City(
        key="london_on",
        name="London, ON",
        # Western Ontario mid-sized city: 19c orthogonal core + diagonal
        # Dundas/Oxford/Wonderland + post-WWII subdivision sprawl.
        bbox=(-81.34, 42.93, -81.16, 43.04),
        utm_epsg=32617,  # UTM 17N
        geofabrik_region="north-america/canada/ontario",
        center=(42.9849, -81.2453),
        default_zoom=12,
    ),
    "bruges": City(
        key="bruges",
        name="Bruges",
        # Medieval walled city + immediate suburbs. Famous canal network +
        # winding pre-modern street layout. Expect strong mean−median gap
        # from the irregular medieval fabric.
        bbox=(3.18, 51.18, 3.28, 51.24),
        utm_epsg=32631,  # UTM 31N
        geofabrik_region="europe/belgium",
        center=(51.2093, 3.2247),  # Markt
        default_zoom=14,
    ),
    "east_bay": City(
        key="east_bay",
        name="East Bay (Berkeley + Oakland)",
        # Oakland (south + downtown + Lake Merritt) and Berkeley (UC campus +
        # downtown). Includes the East Bay hills which break the grid pattern.
        # Mix of orthogonal grid (Berkeley flats, Oakland flatlands), hill
        # neighborhoods (Berkeley Hills, Oakland Hills), and freeway-divided
        # West Oakland.
        bbox=(-122.34, 37.69, -122.10, 37.91),
        utm_epsg=32610,  # UTM 10N, same as SF
        geofabrik_region="north-america/us/california",
        center=(37.8200, -122.2700),  # between downtown Oakland & Berkeley
        default_zoom=11,
    ),
    "champaign": City(
        key="champaign",
        name="Champaign–Urbana, IL",
        # Twin cities + UIUC campus + residential rings. Champaign sits on a
        # true N/S grid; Urbana is rotated ~3° to follow section-line
        # alignment. UIUC's Main Quad is a structurally different sub-region
        # (pedestrian-dominated, internal axes). ~13 × 11 km.
        bbox=(-88.30, 40.06, -88.15, 40.16),
        utm_epsg=32616,  # UTM 16N
        geofabrik_region="north-america/us/illinois",
        center=(40.113, -88.225),  # between Champaign downtown + UIUC Quad
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
