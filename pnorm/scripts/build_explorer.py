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
from rasterize import rasterize, png_to_data_uri

OUT_DEFAULT = Path("data/explorer.html")
LAYERS_DIR = Path("data/layers")          # per-layer PNG files served at /layers/*.png
TEMPLATE = Path("scripts/explorer_template.html")
SENTINEL = "/*__PAYLOAD_JSON__*/null"

# Default layer to preload (inline as base64 in the HTML for instant first
# paint). Tuple of (city, mode, radius). The picked city should be one that
# pretty much always has data and matches the dropdown defaults (foot r=800).
PRELOAD_CITY = "nyc"
PRELOAD_MODE = "foot"
PRELOAD_RADIUS = 800

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
    "amsterdam": "amsterdam_foot",
    "copenhagen":"copenhagen_foot",
    "kyoto":     "kyoto_foot",
    "phoenix":   "phoenix_foot",
    "edinburgh": "edinburgh_foot",
    "buenos_aires": "buenos_aires_foot",
    "detroit":   "detroit_foot",
    "slc":       "slc_foot",
    "london":    "london_foot",
    "charlotte": "charlotte_foot",
    "charlottesville": "charlottesville_foot",
    "madison":   "madison_foot",
    "boulder":   "boulder_foot",
    "katy":      "katy_foot",
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
    "amsterdam": "amsterdam_car",
    "copenhagen":"copenhagen_car",
    "kyoto":     "kyoto_car",
    "phoenix":   "phoenix_car",
    "edinburgh": "edinburgh_car",
    "buenos_aires": "buenos_aires_car",
    "detroit":   "detroit_car",
    "slc":       "slc_car",
    "london":    "london_car",
    "charlotte": "charlotte_car",
    "charlottesville": "charlottesville_car",
    "madison":   "madison_car",
    "boulder":   "boulder_car",
    "katy":      "katy_car",
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
    "amsterdam": "Amsterdam",
    "copenhagen": "Copenhagen",
    "kyoto": "Kyoto, Japan",
    "phoenix": "Phoenix, AZ",
    "edinburgh": "Edinburgh",
    "buenos_aires": "Buenos Aires",
    "detroit": "Detroit, MI",
    "slc": "Salt Lake City, UT",
    "london": "London, UK",
    "charlotte": "Charlotte, NC",
    "charlottesville": "Charlottesville, VA",
    "madison": "Madison, WI",
    "boulder": "Boulder, CO",
    "katy":    "Katy + Fulshear, TX",
}


def load_layer(npz_path: Path, layer_key: str) -> tuple[dict, dict]:
    """Load a npz, rasterize it, and write 5 PNG files to data/layers/.

    Returns (manifest_entry, raster_bytes) where:
      - manifest_entry — JSON-serializable dict for the explorer payload:
          {
            spacing_m, radius_m, grid_type,
            raster_urls: {field: "layers/<key>__<field>.png"},
            data_raster_url: "layers/<key>__data.png",
            bounds: [[sw_lat, sw_lng], [ne_lat, ne_lng]],
            raster_shape: [n_rows, n_cols],
            ranges: {"p": [0, 2], "c": [1, 3]},
            stats: {<field>: {median, p10, p90, cdf[101]}}
          }
      - raster_bytes — {"<field>": png_bytes, "data": png_bytes} for any
        downstream caller that wants to inline a specific layer (e.g. preload).
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

    # Write the 5 PNGs to disk under data/layers/. Filenames are stable per
    # (city, mode, radius, field) so a long-cache + ETag setup on the CDN
    # keeps re-requests cheap.
    raster_urls: dict[str, str] = {}
    raster_bytes: dict[str, bytes] = {}
    for field, png in raster["rasters"].items():
        fname = f"{layer_key}__{field}.png"
        (LAYERS_DIR / fname).write_bytes(png)
        raster_urls[field] = f"layers/{fname}"
        raster_bytes[field] = png
    data_fname = f"{layer_key}__data.png"
    (LAYERS_DIR / data_fname).write_bytes(raster["data_raster"])
    data_raster_url = f"layers/{data_fname}"
    raster_bytes["data"] = raster["data_raster"]

    manifest_entry = {
        "spacing_m": spacing,
        "radius_m": radius,
        "grid_type": grid_type,
        "raster_urls": raster_urls,
        "data_raster_url": data_raster_url,
        "bounds": raster["bounds"],
        "raster_shape": raster["raster_shape"],
        "ranges": raster["ranges"],
        "stats": raster["stats"],
    }
    return manifest_entry, raster_bytes


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

    # Fresh layers/ dir each build — stale files would accumulate forever
    # otherwise, and a rebuild after dropping a city should remove the
    # orphan PNGs from the deploy.
    if LAYERS_DIR.exists():
        import shutil
        shutil.rmtree(LAYERS_DIR)
    LAYERS_DIR.mkdir(parents=True, exist_ok=True)

    layers: dict[str, dict] = {}
    raster_bytes_cache: dict[str, dict[str, bytes]] = {}   # for inlining preload
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
                manifest_entry, bytes_dict = load_layer(path, key)
                layers[key] = manifest_entry
                raster_bytes_cache[key] = bytes_dict
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
                manifest_entry, bytes_dict = load_layer(path, key)
                layers[key] = manifest_entry
                raster_bytes_cache[key] = bytes_dict
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

    # Preload: replace the default layer's raster URLs with inline base64
    # data URIs so first paint is instant — no network round trips for the
    # default city × mode × radius. RasterField transparently accepts data
    # URIs in the same field where it'd otherwise expect a URL.
    preload_key = f"{PRELOAD_CITY}__{PRELOAD_MODE}__{PRELOAD_RADIUS}"
    if preload_key in layers and preload_key in raster_bytes_cache:
        b = raster_bytes_cache[preload_key]
        layers[preload_key]["raster_urls"] = {
            field: png_to_data_uri(b[field])
            for field in ("p_mean", "p_median", "circuity_mean", "circuity_median")
        }
        layers[preload_key]["data_raster_url"] = png_to_data_uri(b["data"])
        preload_bytes = sum(len(v) for v in b.values())
        print(f"  preloading {preload_key} ({preload_bytes // 1024} KB inline)")
    else:
        print(f"  WARNING: preload target {preload_key} not present; "
              f"deploy will need a network fetch for first paint")

    payload = {
        "layers": layers,
        "centers": centers,
        "pretty": {c: PRETTY[c] for c in cities_present},
        "cities": cities_present,
        "radii": radii_for,
        "preload_key": preload_key,
    }
    payload_json = json.dumps(payload, separators=(",", ":"))

    template = TEMPLATE.read_text()
    if SENTINEL not in template:
        raise RuntimeError(f"template {TEMPLATE} missing sentinel {SENTINEL!r}")
    html = template.replace(SENTINEL, payload_json)

    # Sanity guardrail: the built HTML must reference the payload's snake_case
    # field names that the JS reads at runtime. If the template was edited to
    # rename a field but the JS-side reader wasn't updated (or vice versa),
    # the deploy would render an empty map. Cheap to grep, expensive to debug.
    required_in_html = [
        '"raster_urls"',     # Each layer's URL map
        '"data_raster_url"', # Each layer's data PNG URL
        '"stats"',           # Per-field precomputed CDF / quantiles
        '"bounds"',          # Per-layer L.imageOverlay bbox
        'rasterUrls',        # RasterField opts param name (camelCase, JS-side)
        'dataRasterUrl',     # RasterField opts param name (camelCase, JS-side)
        'layerLoading',      # The "Loading…" pill DOM id used by show/hideLoading
    ]
    missing = [s for s in required_in_html if s not in html]
    if missing:
        raise RuntimeError(
            "Built HTML is missing expected identifiers " + repr(missing) +
            " — template and payload field names have drifted apart. "
            "Check explorer_template.html + load_layer()'s manifest schema."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    html_mb = out_path.stat().st_size / 1024 / 1024
    layer_files = sorted(LAYERS_DIR.glob("*.png"))
    layers_mb = sum(p.stat().st_size for p in layer_files) / 1024 / 1024
    print(f"\nwrote {out_path}  ({html_mb:.1f} MB HTML, {len(layers)} layers)")
    print(f"wrote {LAYERS_DIR}/  ({layers_mb:.1f} MB across {len(layer_files)} PNG files)")
    print(f"  first-paint payload (HTML + preload inline): {html_mb:.1f} MB")
    print(f"  lazy-loaded thereafter: per-layer ~{(layers_mb / max(len(layers), 1)):.2f} MB")




if __name__ == "__main__":
    main()
