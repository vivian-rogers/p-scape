"""Build a single self-contained HTML 'explorer' that lets the user pick city,
mode (walking / driving), and ring radius.

Loads every available `<city>_<mode>_r<R>.npz` (and the `_foot_core_` legacy
naming for cities that predate the unified-bbox convention), resolves p(C)
per cell, and injects the data into `scripts/explorer_template.html` (the
"Isochrome" design from Claude Design). Outputs `data/explorer.html`.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pnorm.cities import CITIES
from pnorm.lp_inversion import p_of_circuity

OUT = Path("data/explorer.html")
TEMPLATE = Path("scripts/explorer_template.html")
SENTINEL = "/*__PAYLOAD_JSON__*/null"

# Per-city filename pattern. Some early runs used "_foot_core_" instead of
# "_foot_" because they predate the unified-bbox convention.
FOOT_RADII = [200, 400, 800]
CAR_RADII = [1000, 2000, 3000]

CITY_FOOT_PREFIX = {
    "austin":    "austin_foot",
    "nyc":       "nyc_foot",
    "dc":        "dc_foot",
    "houston":   "houston_foot_core",
    "sf":        "sf_foot_core",
    "barcelona": "barcelona_foot_core",
}
CITY_CAR_PREFIX = {
    "austin":    "austin_car",
    "nyc":       "nyc_car",
    "dc":        "dc_car",
    "houston":   "houston_car",
    "sf":        "sf_car",
    "barcelona": "barcelona_car",
}

PRETTY = {
    "austin": "Austin, TX",
    "nyc": "New York City",
    "dc": "Washington, DC",
    "houston": "Houston, TX",
    "sf": "San Francisco",
    "barcelona": "Barcelona",
}


def load_layer(npz_path: Path) -> dict:
    d = np.load(npz_path)
    ll = d["lonlat"]
    c = d["mean_circuity"]
    spacing = float(d["spacing_m"])
    radius = float(d["radius_m"])
    bad_origin = (
        d["bad_origin"] if "bad_origin" in d.files else np.zeros(len(c), dtype=bool)
    )
    finite = np.isfinite(c)
    keep = finite | bad_origin
    p = np.full(len(c), np.nan)
    if finite.any():
        p[finite] = p_of_circuity(c[finite])
    p[bad_origin] = 0.0  # rural / unrouteable cells: render as p = 0 (deep red)

    cells = []
    for i in np.where(keep)[0]:
        if not np.isfinite(p[i]):
            continue
        cells.append([round(float(ll[i, 1]), 5),
                      round(float(ll[i, 0]), 5),
                      round(float(p[i]), 3)])
    return {
        "spacing_m": spacing,
        "radius_m": radius,
        "cells": cells,
    }


def main() -> None:
    layers: dict[str, dict] = {}
    cities_present = []

    for city, prefix in CITY_FOOT_PREFIX.items():
        any_layer = False
        for r in FOOT_RADII:
            path = Path("data") / f"{prefix}_r{r}.npz"
            if path.exists():
                key = f"{city}__foot__{r}"
                layers[key] = load_layer(path)
                any_layer = True
        if any_layer:
            cities_present.append(city)
        for r in CAR_RADII:
            prefix_car = CITY_CAR_PREFIX.get(city)
            if prefix_car:
                path = Path("data") / f"{prefix_car}_r{r}.npz"
                if path.exists():
                    key = f"{city}__car__{r}"
                    layers[key] = load_layer(path)
                    if not any_layer:
                        cities_present.append(city)
                        any_layer = True

    cities_present = sorted(set(cities_present), key=lambda c: list(CITY_FOOT_PREFIX).index(c))

    # Quick reporting + per-city radii lists
    radii_for = {}
    for city in cities_present:
        for mode in ("foot", "car"):
            rs = sorted(int(k.split("__")[2]) for k in layers if k.startswith(f"{city}__{mode}__"))
            if rs:
                radii_for[f"{city}__{mode}"] = rs

    for k, l in layers.items():
        ps = [c[2] for c in l["cells"]]
        med = float(np.median(ps)) if ps else float("nan")
        print(f"  {k:<28}  cells={len(l['cells']):>6}  spacing={l['spacing_m']:.0f}m  median_p={med:.3f}")

    centers = {
        city: {
            "lat": CITIES[city].center[0],
            "lng": CITIES[city].center[1],
            "zoom": CITIES[city].default_zoom,
        }
        for city in cities_present
    }

    payload = {
        "layers": layers,
        "centers": centers,
        "pretty": {c: PRETTY[c] for c in cities_present},
        "cities": cities_present,
        "radii": radii_for,
    }
    payload_json = json.dumps(payload, separators=(",", ":"))

    template = TEMPLATE.read_text()
    if SENTINEL not in template:
        raise RuntimeError(f"template {TEMPLATE} missing sentinel {SENTINEL!r}")
    html = template.replace(SENTINEL, payload_json)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    size_mb = OUT.stat().st_size / 1024 / 1024
    total_cells = sum(len(l["cells"]) for l in layers.values())
    print(f"\nwrote {OUT}  ({size_mb:.1f} MB, {len(layers)} layers, {total_cells:,} cells)")




if __name__ == "__main__":
    main()
