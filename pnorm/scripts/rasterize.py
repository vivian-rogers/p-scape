"""Rasterize one circuity-grid npz into the asset set the explorer consumes.

For each loaded layer we emit:
  - Four visual PNGs (palette-colored): p_mean, p_median, circuity_mean,
    circuity_median. The explorer composites them with L.imageOverlay.
  - One data PNG (RGBA-packed raw values) for client-side hover lookup:
        R = p_mean   ∈ [0, 2] → uint8
        G = c_mean   ∈ [1, 3] → uint8
        B = p_median ∈ [0, 2] → uint8
        A = 0 (no cell) | 255 (valid)
    c_median is recoverable client-side via the closed-form
    medianCircuityOfP(p_median), so we don't waste a fourth channel on it.
  - A lat/lng bounding box from the UTM-axis-aligned raster corners, which
    Leaflet stretches the image to. UTM→lat/lng distortion at city scale is
    sub-pixel.

The palette and normalize() definitions mirror the JS ones in
explorer_template.html exactly so the visual maps match before/after the
raster cut-over.
"""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

from pnorm.geo import set_utm_epsg, to_lonlat


JS_PALETTE = [
    (0.00, (120, 30, 20)),
    (0.15, (200, 60, 40)),
    (0.30, (255, 100, 70)),
    (0.40, (255, 170, 140)),
    (0.50, (254, 249, 238)),
    (0.60, (170, 180, 240)),
    (0.70, (90, 110, 230)),
    (0.85, (40, 60, 200)),
    (1.00, (25, 35, 110)),
]
GRID_C = 4.0 / np.pi

# Data-PNG quantization ranges. Out-of-range values clamp on encode.
P_MIN, P_MAX = 0.0, 2.0
C_MIN, C_MAX = 1.0, 3.0
# λ_social = C(x) / (2·√n(x)), units = meters. Range [1, 1000] m on a
# log10 scale: dense Manhattan ≈ 5 m, suburban ≈ 50 m, exurban > 500 m.
LAMBDA_MIN_M, LAMBDA_MAX_M = 1.0, 1000.0


def _build_palette_lut(n: int = 256) -> np.ndarray:
    """Precompute a 256-entry RGB lookup table from JS_PALETTE."""
    lut = np.zeros((n, 3), dtype=np.uint8)
    for i in range(n):
        t = i / (n - 1)
        rgb = JS_PALETTE[-1][1]
        for k in range(1, len(JS_PALETTE)):
            t1, c1 = JS_PALETTE[k]
            if t <= t1:
                t0, c0 = JS_PALETTE[k - 1]
                f = (t - t0) / (t1 - t0)
                rgb = tuple(int(c0[j] + f * (c1[j] - c0[j])) for j in range(3))
                break
        lut[i] = rgb
    return lut


PALETTE_LUT = _build_palette_lut()


def _normalize_p(values: np.ndarray) -> np.ndarray:
    """For p fields: linear in [0, 2] → t ∈ [0, 1]."""
    return np.clip(values / 2.0, 0.0, 1.0)


def _normalize_c(values: np.ndarray) -> np.ndarray:
    """For circuity fields: piecewise palette anchored at 4/π."""
    t = np.where(
        values <= 1.0, 1.0,
        np.where(
            values >= 2.5, 0.0,
            np.where(
                values <= GRID_C,
                1.0 - (values - 1.0) / (GRID_C - 1.0) * 0.5,
                0.5 - (values - GRID_C) / (2.5 - GRID_C) * 0.5,
            ),
        ),
    )
    return np.clip(t, 0.0, 1.0)


def _quantize_p(values: np.ndarray) -> np.ndarray:
    return np.clip((values - P_MIN) / (P_MAX - P_MIN), 0.0, 1.0).__mul__(255).astype(np.uint8)


def _quantize_c(values: np.ndarray) -> np.ndarray:
    return np.clip((values - C_MIN) / (C_MAX - C_MIN), 0.0, 1.0).__mul__(255).astype(np.uint8)


def _normalize_lambda(values: np.ndarray) -> np.ndarray:
    """λ_social on a log10 [1, 1000] m scale; small λ → 1 (warm), large → 0 (cool).

    Matches the diverging-palette convention used for p_eff: low λ_social
    (dense, lots of contact) lands on the cool/blue end (analog to high p,
    grid-like), high λ_social (isolated) lands on the warm/red end. So we
    map *high* values to the LOW end of the palette index so the palette
    interpretation stays 'red = bad, blue = good'.
    """
    lo = np.log10(LAMBDA_MIN_M)
    hi = np.log10(LAMBDA_MAX_M)
    safe = np.clip(values, LAMBDA_MIN_M, LAMBDA_MAX_M)
    # 1 - log_ratio so dense → 1.0 (cool/grid end), isolated → 0.0 (warm/sprawl end)
    t = 1.0 - (np.log10(safe) - lo) / (hi - lo)
    return np.clip(t, 0.0, 1.0)


def _quantize_lambda(values: np.ndarray) -> np.ndarray:
    """log10 [1, 1000] m → uint8. Recover via 10**(lo + (b/255) * (hi-lo))."""
    lo = np.log10(LAMBDA_MIN_M)
    hi = np.log10(LAMBDA_MAX_M)
    safe = np.clip(values, LAMBDA_MIN_M, LAMBDA_MAX_M)
    t = (np.log10(safe) - lo) / (hi - lo)
    return np.clip(t, 0.0, 1.0).__mul__(255).astype(np.uint8)


def _png_bytes(arr_rgba: np.ndarray) -> bytes:
    """Encode an (H, W, 4) uint8 array as PNG bytes."""
    img = Image.fromarray(arr_rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def png_to_data_uri(png_bytes: bytes) -> str:
    """Wrap PNG bytes as a `data:image/png;base64,…` URI (for inlined preload)."""
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def _bounds_from_utm(xy: np.ndarray, spacing_m: float, utm_epsg: int) -> list[list[float]]:
    """Axis-aligned lat/lng bbox of the UTM-grid raster, padded by half a cell."""
    set_utm_epsg(utm_epsg)
    x_min, x_max = float(xy[:, 0].min()), float(xy[:, 0].max())
    y_min, y_max = float(xy[:, 1].min()), float(xy[:, 1].max())
    pad = spacing_m / 2.0
    corners = [
        (x_min - pad, y_min - pad),
        (x_max + pad, y_min - pad),
        (x_min - pad, y_max + pad),
        (x_max + pad, y_max + pad),
    ]
    lats, lons = [], []
    for x, y in corners:
        lon, lat = to_lonlat(x, y)
        lats.append(float(lat))
        lons.append(float(lon))
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def rasterize(d) -> dict:
    """Turn a loaded npz into visual PNGs + data PNG + bounds + per-field stats."""
    xy = d["xy_utm"]
    spacing_m = float(d["spacing_m"])
    utm_epsg = int(d["utm_epsg"])

    x_min, x_max = float(xy[:, 0].min()), float(xy[:, 0].max())
    y_max = float(xy[:, 1].max())
    n_cols = int(round((x_max - x_min) / spacing_m)) + 1
    cols = np.round((xy[:, 0] - x_min) / spacing_m).astype(np.int32)
    rows = np.round((y_max - xy[:, 1]) / spacing_m).astype(np.int32)  # PNG Y origin top-left
    n_rows = int(rows.max()) + 1
    in_bounds = (rows >= 0) & (rows < n_rows) & (cols >= 0) & (cols < n_cols)

    p_mean   = np.asarray(d["effective_p_mean"], dtype=np.float64)
    p_median = np.asarray(d["effective_p_median"], dtype=np.float64)
    c_mean   = np.asarray(d["mean_circuity"], dtype=np.float64)
    c_median = np.asarray(d["median_circuity"], dtype=np.float64)

    fields = [
        ("p_mean",          p_mean,   _normalize_p,      "p"),
        ("p_median",        p_median, _normalize_p,      "p"),
        ("circuity_mean",   c_mean,   _normalize_c,      "c"),
        ("circuity_median", c_median, _normalize_c,      "c"),
    ]

    # λ_social = C(x) / (2·√n(x)) — population MFP. Optional: only present
    # in npz files that were post-processed against a population raster
    # (currently Austin foot grids via Kontur). When absent, no lambda
    # layer is emitted and the field doesn't appear in the explorer
    # dropdown for that city.
    has_lambda = False
    lam_vals = None
    if hasattr(d, 'files') and "lambda_social_m" in d.files:
        has_lambda = True
    elif isinstance(d, dict) and "lambda_social_m" in d:
        has_lambda = True
    if has_lambda:
        lam_vals = np.asarray(d["lambda_social_m"], dtype=np.float64)
        fields.append(("lambda_social", lam_vals, _normalize_lambda, "lambda"))

    rasters: dict[str, bytes] = {}
    stats: dict[str, dict] = {}
    for name, values, normalize_fn, kind in fields:
        finite = np.isfinite(values)
        place = in_bounds & finite

        img = np.zeros((n_rows, n_cols, 4), dtype=np.uint8)
        if place.any():
            t = normalize_fn(values[place])
            idx = np.clip((t * 255).astype(np.int32), 0, 255)
            img[rows[place], cols[place], :3] = PALETTE_LUT[idx]
            img[rows[place], cols[place], 3] = 255
        rasters[name] = _png_bytes(img)

        # Precomputed stats — what the explorer used to compute by iterating
        # the cells array on every layer change.
        vals = values[finite]
        if vals.size:
            qs = np.quantile(vals, np.linspace(0, 1, 101))
            stats[name] = {
                "median": float(np.median(vals)),
                "p10":    float(np.quantile(vals, 0.10)),
                "p90":    float(np.quantile(vals, 0.90)),
                "cdf":    [round(float(q), 4) for q in qs],
            }
        else:
            stats[name] = {"median": float("nan"), "p10": float("nan"),
                           "p90": float("nan"), "cdf": []}

    # Data PNG: RGB = (p_mean, c_mean, p_median); A = validity.
    valid = in_bounds & np.isfinite(p_mean) & np.isfinite(c_mean) & np.isfinite(p_median)
    data = np.zeros((n_rows, n_cols, 4), dtype=np.uint8)
    if valid.any():
        data[rows[valid], cols[valid], 0] = _quantize_p(p_mean[valid])
        data[rows[valid], cols[valid], 1] = _quantize_c(c_mean[valid])
        data[rows[valid], cols[valid], 2] = _quantize_p(p_median[valid])
        data[rows[valid], cols[valid], 3] = 255
    data_raster = _png_bytes(data)

    # Lambda data PNG (optional, separate from the main data PNG because
    # all 4 RGBA channels are already in use). R = log10(λ_m) on [0, 3]
    # quantized to uint8, A = validity.
    lambda_data_raster = None
    if has_lambda:
        lvalid = in_bounds & np.isfinite(lam_vals)
        lam_img = np.zeros((n_rows, n_cols, 4), dtype=np.uint8)
        if lvalid.any():
            lam_img[rows[lvalid], cols[lvalid], 0] = _quantize_lambda(lam_vals[lvalid])
            lam_img[rows[lvalid], cols[lvalid], 3] = 255
        lambda_data_raster = _png_bytes(lam_img)

    bounds = _bounds_from_utm(xy, spacing_m, utm_epsg)

    out = {
        "rasters": rasters,           # {field: PNG bytes}
        "data_raster": data_raster,   # PNG bytes
        "bounds": bounds,
        "raster_shape": [n_rows, n_cols],
        "ranges": {"p": [P_MIN, P_MAX], "c": [C_MIN, C_MAX],
                   "lambda": [LAMBDA_MIN_M, LAMBDA_MAX_M]},
        "stats": stats,
    }
    if lambda_data_raster is not None:
        out["lambda_data_raster"] = lambda_data_raster
    return out
