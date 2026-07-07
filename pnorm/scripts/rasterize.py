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
from numpy.lib.stride_tricks import sliding_window_view
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
# Legacy: λ_social in meters (directed-MFP version, kept only so old npz
# files don't break the build). New field is diffusive_rate_per_km below.
LAMBDA_MIN_M, LAMBDA_MAX_M = 1.0, 300.0

# Diffusive encounter rate per km walked = 1000·2π·n / (C²·ln(L²/σ²)).
# Linear range [0, 25] /km. 0 = dark (no incidental contact), 25 = light
# yellow (saturated dense). Linear means most of Austin/Brooklyn/Queens
# read as fairly dark because typical values sit at ~1/km, with Manhattan
# the only thing using the upper half of the palette.
RATE_MIN_PER_KM, RATE_MAX_PER_KM = 0.0, 15.0


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


def _build_inferno_lut(n: int = 256) -> np.ndarray:
    """Inferno colormap (perceptually uniform). t=0 → near-black; t=1 → pale yellow.

    For λ_social the palette maps 'small λ (dense, lots of contact)' to the
    LIGHT end and 'large λ (isolated)' to the DARK end, matching the user
    intuition that bright = good signal, dark = absence/desert.
    """
    try:
        import matplotlib
        cm = matplotlib.colormaps["inferno"]
        return (cm(np.linspace(0, 1, n))[:, :3] * 255).astype(np.uint8)
    except Exception:
        # Hard-coded 9-stop fallback (inferno key colors, linearly interpolated).
        stops = [
            (0.000, (0, 0, 4)),
            (0.125, (40, 11, 84)),
            (0.250, (101, 21, 110)),
            (0.375, (159, 42, 99)),
            (0.500, (213, 67, 76)),
            (0.625, (244, 121, 33)),
            (0.750, (252, 187, 39)),
            (0.875, (252, 246, 113)),
            (1.000, (252, 255, 164)),
        ]
        lut = np.zeros((n, 3), dtype=np.uint8)
        for i in range(n):
            t = i / (n - 1)
            rgb = stops[-1][1]
            for k in range(1, len(stops)):
                t1, c1 = stops[k]
                if t <= t1:
                    t0, c0 = stops[k - 1]
                    f = (t - t0) / (t1 - t0)
                    rgb = tuple(int(c0[j] + f * (c1[j] - c0[j])) for j in range(3))
                    break
            lut[i] = rgb
        return lut


INFERNO_LUT = _build_inferno_lut()


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


def _normalize_rate(values: np.ndarray) -> np.ndarray:
    """Diffusive encounter rate (per km) → palette index t ∈ [0, 1].

    Linear scale on [RATE_MIN_PER_KM, RATE_MAX_PER_KM]. High rate (dense
    contact) → t=1 (light yellow); low rate → t=0 (dark purple).
    """
    safe = np.clip(values, RATE_MIN_PER_KM, RATE_MAX_PER_KM)
    t = (safe - RATE_MIN_PER_KM) / (RATE_MAX_PER_KM - RATE_MIN_PER_KM)
    return np.clip(t, 0.0, 1.0)


def _quantize_rate(values: np.ndarray) -> np.ndarray:
    """Linear [0, 25] /km → uint8."""
    safe = np.clip(values, RATE_MIN_PER_KM, RATE_MAX_PER_KM)
    t = (safe - RATE_MIN_PER_KM) / (RATE_MAX_PER_KM - RATE_MIN_PER_KM)
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


def _infill_isolated(grid: np.ndarray, protect: np.ndarray | None = None,
                     min_neighbors: int = 6) -> np.ndarray:
    """Median-of-neighbors fill for isolated NaN cells (QC dropouts).

    A cell goes NaN when its origin fails to snap or too many rays get
    dropped — on a map those read as "confused" transparent specks inside
    solid data. Fill a NaN cell with the median of its finite 8-neighbors
    when at least `min_neighbors` of them are finite. At the default 6,
    singletons, pairs, and thin strings get patched while any compact blob
    of 2×2 or larger (parks, water, plazas — genuinely un-probed places)
    keeps every cell: a 2×2 corner has only 5 finite neighbors. Cells in
    `protect` (e.g. the water mask) are never filled. Single pass, so the
    fill uses measured values only — never other filled cells.
    """
    fillable = np.isnan(grid)
    if protect is not None:
        fillable &= ~protect
    if not fillable.any():
        return grid
    padded = np.pad(grid, 1, constant_values=np.nan)
    neigh = sliding_window_view(padded, (3, 3)).reshape(*grid.shape, 9)
    neigh = neigh[..., [0, 1, 2, 3, 5, 6, 7, 8]]
    n_ok = np.isfinite(neigh).sum(axis=2)
    fill = fillable & (n_ok >= min_neighbors)
    if not fill.any():
        return grid
    out = grid.copy()
    out[fill] = np.nanmedian(neigh[fill], axis=1)
    return out


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


def rasterize(d, infill_min_neighbors: int | None = 6) -> dict:
    """Turn a loaded npz into visual PNGs + data PNG + bounds + per-field stats.

    `infill_min_neighbors` patches isolated QC-dropout cells (see
    _infill_isolated) in every rendered raster, including the hover data
    PNGs so displayed and inspected values agree. The stats block is always
    computed from raw, un-filled values. Pass None to disable infill.
    """
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

    shape = (n_rows, n_cols)
    protect = np.zeros(shape, dtype=bool)
    has_water = ((hasattr(d, "files") and "in_water" in d.files)
                 or (isinstance(d, dict) and "in_water" in d))
    if has_water:
        water = np.asarray(d["in_water"], dtype=bool)
        protect[rows[in_bounds], cols[in_bounds]] = water[in_bounds]

    def _field_grid(values: np.ndarray) -> np.ndarray:
        g = np.full(shape, np.nan)
        place = in_bounds & np.isfinite(values)
        g[rows[place], cols[place]] = values[place]
        if infill_min_neighbors is not None:
            g = _infill_isolated(g, protect, infill_min_neighbors)
        return g

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
    # in npz files that were post-processed against a population raster.
    # Kept for backwards-compatibility; the production-website field is
    # `diffusive_rate_per_km` below.
    has_lambda = False
    lam_vals = None
    if hasattr(d, 'files') and "lambda_social_m" in d.files:
        has_lambda = True
    elif isinstance(d, dict) and "lambda_social_m" in d:
        has_lambda = True
    if has_lambda:
        lam_vals = np.asarray(d["lambda_social_m"], dtype=np.float64)
        fields.append(("lambda_social", lam_vals, _normalize_lambda, "lambda"))

    # Diffusive encounter rate per km walked — the post-Smoluchowski
    # quantity 1000·2π·n(x) / (C_med(x)² · ln(L²/σ²)). Currently injected
    # for Austin & NYC foot grids via inject_diffusive_rate.py. Same
    # palette family as λ_social (inferno via "lambda" kind) but the
    # value→color direction is inverted: HIGH rate = light yellow.
    has_rate = False
    rate_vals = None
    if hasattr(d, 'files') and "diffusive_rate_per_km" in d.files:
        has_rate = True
    elif isinstance(d, dict) and "diffusive_rate_per_km" in d:
        has_rate = True
    if has_rate:
        rate_vals = np.asarray(d["diffusive_rate_per_km"], dtype=np.float64)
        fields.append(("diffusive_rate", rate_vals, _normalize_rate, "lambda"))

    rasters: dict[str, bytes] = {}
    stats: dict[str, dict] = {}
    grids: dict[str, np.ndarray] = {}
    for name, values, normalize_fn, kind in fields:
        finite = np.isfinite(values)

        # p / circuity use the diverging red-cream-blue palette anchored at
        # the grid value. λ_social uses inferno on a log scale: small λ
        # (dense contact) is rendered pale yellow, large λ (isolated) goes
        # to dark purple/black. The user-facing legend in the explorer
        # template must match this branch.
        lut = INFERNO_LUT if kind == "lambda" else PALETTE_LUT

        grid = _field_grid(values)
        grids[name] = grid
        gfin = np.isfinite(grid)
        img = np.zeros((n_rows, n_cols, 4), dtype=np.uint8)
        if gfin.any():
            t = normalize_fn(grid[gfin])
            idx = np.clip((t * 255).astype(np.int32), 0, 255)
            img[gfin, :3] = lut[idx]
            img[gfin, 3] = 255
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

    # Data PNG: RGB = (p_mean, c_mean, p_median); A = validity. Built from
    # the same (possibly infilled) grids as the visuals so hover values
    # always agree with the rendered pixels.
    g_pm, g_cm, g_pmed = grids["p_mean"], grids["circuity_mean"], grids["p_median"]
    dvalid = np.isfinite(g_pm) & np.isfinite(g_cm) & np.isfinite(g_pmed)
    data = np.zeros((n_rows, n_cols, 4), dtype=np.uint8)
    if dvalid.any():
        data[dvalid, 0] = _quantize_p(g_pm[dvalid])
        data[dvalid, 1] = _quantize_c(g_cm[dvalid])
        data[dvalid, 2] = _quantize_p(g_pmed[dvalid])
        data[dvalid, 3] = 255
    data_raster = _png_bytes(data)

    # Lambda data PNG (optional, separate from the main data PNG because
    # all 4 RGBA channels are already in use). R = log10(λ_m) on [0, 3]
    # quantized to uint8, A = validity.
    lambda_data_raster = None
    if has_lambda:
        g_lam = grids["lambda_social"]
        lvalid = np.isfinite(g_lam)
        lam_img = np.zeros((n_rows, n_cols, 4), dtype=np.uint8)
        if lvalid.any():
            lam_img[lvalid, 0] = _quantize_lambda(g_lam[lvalid])
            lam_img[lvalid, 3] = 255
        lambda_data_raster = _png_bytes(lam_img)

    # Diffusive rate data PNG (for hover-value lookup).
    rate_data_raster = None
    if has_rate:
        g_rate = grids["diffusive_rate"]
        rvalid = np.isfinite(g_rate)
        rate_img = np.zeros((n_rows, n_cols, 4), dtype=np.uint8)
        if rvalid.any():
            rate_img[rvalid, 0] = _quantize_rate(g_rate[rvalid])
            rate_img[rvalid, 3] = 255
        rate_data_raster = _png_bytes(rate_img)

    bounds = _bounds_from_utm(xy, spacing_m, utm_epsg)

    out = {
        "rasters": rasters,           # {field: PNG bytes}
        "data_raster": data_raster,   # PNG bytes
        "bounds": bounds,
        "raster_shape": [n_rows, n_cols],
        "ranges": {"p": [P_MIN, P_MAX], "c": [C_MIN, C_MAX],
                   "lambda": [LAMBDA_MIN_M, LAMBDA_MAX_M],
                   "rate":   [RATE_MIN_PER_KM, RATE_MAX_PER_KM]},
        "stats": stats,
    }
    if lambda_data_raster is not None:
        out["lambda_data_raster"] = lambda_data_raster
    if rate_data_raster is not None:
        out["rate_data_raster"] = rate_data_raster
    return out
