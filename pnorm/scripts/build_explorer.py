"""Build a single self-contained HTML 'explorer' that lets the user pick city,
mode (walking / driving), and ring radius.

Loads every available `<city>_<mode>_r<R>.npz` (and the `_foot_core_` legacy
naming for cities that predate the unified-bbox convention), resolves p(C)
per cell, and injects the data into `scripts/explorer_template.html` (the
"Isochrome" design from Claude Design). Outputs `data/explorer.html`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from pnorm.cities import CITIES
from pnorm.lp_inversion import p_of_circuity

import sys
sys.path.insert(0, str(Path(__file__).parent))
from rasterize import rasterize

OUT_DEFAULT = Path("data/explorer.html")
TEMPLATE = Path("scripts/explorer_template.html")
SENTINEL = "/*__PAYLOAD_JSON__*/null"

# Per-city filename pattern. Some early runs used "_foot_core_" instead of
# "_foot_" because they predate the unified-bbox convention. The new square
# pipeline writes `<city>_<mode>_sq_r<R>.npz` uniformly across all cities;
# build_explorer.py prefers those, falling back to the legacy hex files.
#
# CAR_RADII is the union of the legacy set {1000, 2000, 3000} and the new
# square-pipeline set {1000, 4000, 16000} so cities can be migrated one at a
# time without dropping car layers from the not-yet-migrated ones.
FOOT_RADII = [200, 400, 800, 1600]
CAR_RADII = [1000, 2000, 3000, 4000, 16000]

CITY_FOOT_PREFIX = {
    "austin":    "austin_foot",
    "nyc":       "nyc_foot",
    "dc":        "dc_foot",
    "houston":   "houston_foot",
    "la":        "la_foot",
    "sf":        "sf_foot_core",
    "chicago":   "chicago_foot",
    "seattle":   "seattle_foot",
    "lansing":   "lansing_foot",
    "barcelona": "barcelona_foot",
    "paris":     "paris_foot",
    "villages":  "villages_foot",
    "karlsruhe": "karlsruhe_foot",
    "rome":      "rome_foot",
    "tokyo":     "tokyo_foot",
    "mexico_city": "mexico_city_foot",
    "brasilia":  "brasilia_foot",
    "london_on": "london_on_foot",
    "bruges":    "bruges_foot",
    "east_bay":  "east_bay_foot",
    "champaign": "champaign_foot",
    "vienna":    "vienna_foot",
}
CITY_CAR_PREFIX = {
    "austin":    "austin_car",
    "nyc":       "nyc_car",
    "dc":        "dc_car",
    "houston":   "houston_car",
    "la":        "la_car",
    "sf":        "sf_car",
    "chicago":   "chicago_car",
    "seattle":   "seattle_car",
    "lansing":   "lansing_car",
    "barcelona": "barcelona_car",
    "paris":     "paris_car",
    "villages":  "villages_car",
    "karlsruhe": "karlsruhe_car",
    "rome":      "rome_car",
    "tokyo":     "tokyo_car",
    "mexico_city": "mexico_city_car",
    "brasilia":  "brasilia_car",
    "london_on": "london_on_car",
    "bruges":    "bruges_car",
    "east_bay":  "east_bay_car",
    "champaign": "champaign_car",
    "vienna":    "vienna_car",
}

PRETTY = {
    "austin": "Austin, TX",
    "nyc": "New York City",
    "dc": "Washington, DC",
    "houston": "Houston, TX",
    "la": "Los Angeles",
    "sf": "San Francisco",
    "chicago": "Chicago, IL",
    "seattle": "Seattle, WA",
    "lansing": "Lansing, MI",
    "barcelona": "Barcelona",
    "paris": "Paris",
    "villages": "The Villages, FL",
    "karlsruhe": "Karlsruhe",
    "rome": "Rome",
    "tokyo": "Tokyo (Shitamachi)",
    "mexico_city": "Mexico City",
    "brasilia": "Brasília",
    "london_on": "London, ON",
    "bruges": "Bruges",
    "east_bay": "East Bay (Berkeley + Oakland)",
    "champaign": "Champaign–Urbana, IL",
    "vienna": "Vienna, Austria",
}


def load_layer(npz_path: Path) -> dict:
    """Load a npz and rasterize it into the payload format the explorer consumes.

    Layer shape (no per-cell array — visuals come from PNGs, hover values come
    from a packed data PNG, derived stats are precomputed):
        {
          "spacing_m", "radius_m", "grid_type",
          "rasters":  {p_mean, p_median, circuity_mean, circuity_median},  # data: URIs
          "data_raster": "data:image/png;base64,…",                        # RGBA pack
          "bounds": [[sw_lat, sw_lng], [ne_lat, ne_lng]],
          "raster_shape": [n_rows, n_cols],
          "ranges": {"p": [0, 2], "c": [1, 3]},
          "stats":  {<field>: {median, p10, p90, cdf[101]}}
        }
    """
    d = np.load(npz_path)
    spacing = float(d["spacing_m"])
    radius = float(d["radius_m"])
    grid_type = str(d["grid_type"]) if "grid_type" in d.files else "hex"

    # Legacy npz files predate effective_p_mean / effective_p_median /
    # median_circuity. Synthesize them so rasterize() always sees the same
    # schema regardless of which generation produced the file.
    if "effective_p_mean" not in d.files or "effective_p_median" not in d.files \
            or "median_circuity" not in d.files:
        from pnorm.lp_inversion import p_of_median_circuity
        c = np.asarray(d["mean_circuity"], dtype=np.float64)
        if "median_circuity" in d.files:
            cm = np.asarray(d["median_circuity"], dtype=np.float64)
        elif "circuities" in d.files:
            cm = np.nanmedian(np.asarray(d["circuities"], dtype=np.float64), axis=1)
        else:
            cm = c
        eff_p_mean = np.full_like(c, np.nan)
        eff_p_median = np.full_like(c, np.nan)
        finite_c = np.isfinite(c)
        finite_cm = np.isfinite(cm)
        if finite_c.any():
            eff_p_mean[finite_c] = p_of_circuity(c[finite_c])
        if finite_cm.any():
            eff_p_median[finite_cm] = p_of_median_circuity(cm[finite_cm])
        synthetic = {k: d[k] for k in d.files}
        synthetic["effective_p_mean"] = eff_p_mean
        synthetic["effective_p_median"] = eff_p_median
        synthetic["median_circuity"] = cm
        d = synthetic

    raster = rasterize(d)
    raster["spacing_m"] = spacing
    raster["radius_m"] = radius
    raster["grid_type"] = grid_type
    return raster


def resolve_layer_path(city: str, mode: str, radius: int,
                       legacy_prefix_map: dict[str, str]) -> Path | None:
    """Prefer the new square-pipeline filename, fall back to the legacy hex one."""
    sq = Path("data") / f"{city}_{mode}_sq_r{radius}.npz"
    if sq.exists():
        return sq
    legacy_prefix = legacy_prefix_map.get(city)
    if legacy_prefix:
        legacy = Path("data") / f"{legacy_prefix}_r{radius}.npz"
        if legacy.exists():
            return legacy
    return None


def _parse_skip(spec: str) -> set[tuple[str, int]]:
    """Parse ``--skip foot:200,car:2000`` → ``{('foot', 200), ('car', 2000)}``."""
    out: set[tuple[str, int]] = set()
    for tok in (spec or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        mode, _, r = tok.partition(":")
        if mode not in {"foot", "car"} or not r.isdigit():
            raise ValueError(f"--skip token must be foot:N or car:N, got {tok!r}")
        out.add((mode, int(r)))
    return out


def _parse_keep(spec: str) -> set[tuple[str, str, int]]:
    """Parse ``--keep paris:foot:200,nyc:car:1000`` → ``{('paris', 'foot', 200), ...}``.

    These (city, mode, radius) triples bypass any ``--skip`` rule. Useful when
    you want to skip a layer for most cities (to fit the Vercel cap) but
    selectively include it for one or two.
    """
    out: set[tuple[str, str, int]] = set()
    for tok in (spec or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        parts = tok.split(":")
        if len(parts) != 3 or parts[1] not in {"foot", "car"} or not parts[2].isdigit():
            raise ValueError(f"--keep token must be city:mode:N, got {tok!r}")
        out.add((parts[0], parts[1], int(parts[2])))
    return out


def _parse_skip_extra(spec: str) -> set[tuple[str, str, int]]:
    """Inverse of ``--keep``: per-city extra skips on top of ``--skip``.

    Parse ``--skip-extra houston:foot:1600,la:foot:1600`` → triples to drop
    specifically. Use when a global ``--skip`` would over-trim but you want
    surgical drops of single layers from specific cities.
    """
    return _parse_keep(spec)  # same syntax, same parser


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT,
                    help=f"output HTML path (default: {OUT_DEFAULT})")
    ap.add_argument("--skip", default="",
                    help="comma-separated mode:radius layers to omit, "
                         "e.g. --skip foot:200,car:2000 — useful for fitting under "
                         "the Vercel 100 MB per-file deploy cap.")
    ap.add_argument("--keep", default="",
                    help="comma-separated city:mode:radius triples to include even "
                         "if --skip would drop them, e.g. --keep paris:foot:200")
    ap.add_argument("--skip-extra", default="",
                    help="comma-separated city:mode:radius triples to drop in addition "
                         "to --skip, e.g. --skip-extra houston:foot:1600")
    a = ap.parse_args()
    out_path: Path = a.out
    skip = _parse_skip(a.skip)
    keep = _parse_keep(a.keep)
    skip_extra = _parse_skip_extra(a.skip_extra)
    if skip:
        print(f"  skipping: {sorted(skip)}")
    if keep:
        print(f"  keeping exceptions: {sorted(keep)}")
    if skip_extra:
        print(f"  skipping (per-city): {sorted(skip_extra)}")

    layers: dict[str, dict] = {}
    cities_present = []

    for city, prefix in CITY_FOOT_PREFIX.items():
        any_layer = False
        for r in FOOT_RADII:
            if (city, "foot", r) in skip_extra:
                continue
            if ("foot", r) in skip and (city, "foot", r) not in keep:
                continue
            path = resolve_layer_path(city, "foot", r, CITY_FOOT_PREFIX)
            if path is not None:
                key = f"{city}__foot__{r}"
                layers[key] = load_layer(path)
                any_layer = True
        if any_layer:
            cities_present.append(city)
        for r in CAR_RADII:
            if (city, "car", r) in skip_extra:
                continue
            if ("car", r) in skip and (city, "car", r) not in keep:
                continue
            path = resolve_layer_path(city, "car", r, CITY_CAR_PREFIX)
            if path is not None:
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
        med = float(l["stats"]["p_mean"]["median"]) if l.get("stats") else float("nan")
        n_rows, n_cols = l.get("raster_shape", [0, 0])
        print(f"  {k:<28}  raster={n_rows}x{n_cols}  spacing={l['spacing_m']:.0f}m  median_p={med:.3f}")

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

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    size_mb = out_path.stat().st_size / 1024 / 1024
    n_rasters = sum(len(l.get("rasters", {})) + (1 if l.get("data_raster") else 0)
                    for l in layers.values())
    print(f"\nwrote {out_path}  ({size_mb:.1f} MB, {len(layers)} layers, {n_rasters} PNGs embedded)")




if __name__ == "__main__":
    main()
