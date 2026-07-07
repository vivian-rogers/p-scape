"""Isolated-dropout infill in rasterize(): specks get patched, real absences
(parks, water, 2×2+ blobs) stay transparent, stats never move."""

import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from rasterize import _quantize_p, rasterize  # noqa: E402

H = W = 20
SPACING = 100.0
X0, Y0 = 620_000.0, 3_350_000.0  # plausible UTM 14N (Texas)

SINGLE = (5, 5)
PAIR = [(7, 14), (7, 15)]
BLOCK2 = [(10, 10), (10, 11), (11, 10), (11, 11)]
PARK4 = [(r, c) for r in range(14, 18) for c in range(2, 6)]
WATER = (2, 15)


def make_layer(neighbor_bump=False):
    """20×20 synthetic city with known holes. Cell (r, c) → pixel (r, c)."""
    rr, cc = np.meshgrid(np.arange(H), np.arange(W), indexing="ij")
    xy = np.column_stack([
        (X0 + cc.ravel() * SPACING),
        (Y0 + (H - 1 - rr.ravel()) * SPACING),  # row 0 = top = max northing
    ])
    n = H * W
    idx = lambda r, c: r * W + c

    p_mean = np.full(n, 1.0)
    if neighbor_bump:
        # give the single hole's 8 neighbors a known, asymmetric value set
        vals = [0.5, 0.6, 0.7, 0.8, 1.2, 1.3, 1.4, 1.5]  # median 1.0
        r0, c0 = SINGLE
        k = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr or dc:
                    p_mean[idx(r0 + dr, c0 + dc)] = vals[k]
                    k += 1
    p_median = p_mean * 0.8
    c_mean = np.full(n, 1.2)
    c_median = np.full(n, 1.15)

    in_water = np.zeros(n, dtype=bool)
    in_water[idx(*WATER)] = True
    holes = [SINGLE, *PAIR, *BLOCK2, *PARK4, WATER]
    for arr in (p_mean, p_median, c_mean, c_median):
        for r, c in holes:
            arr[idx(r, c)] = np.nan

    return {
        "xy_utm": xy,
        "spacing_m": SPACING,
        "utm_epsg": 32614,
        "effective_p_mean": p_mean,
        "effective_p_median": p_median,
        "mean_circuity": c_mean,
        "median_circuity": c_median,
        "in_water": in_water,
    }


def decode(png_bytes):
    return np.asarray(Image.open(io.BytesIO(png_bytes)))


def alpha_at(png, rc):
    return int(png[rc[0], rc[1], 3])


def test_speck_and_pair_filled_blobs_and_water_kept():
    out = rasterize(make_layer())
    for name in ("p_mean", "p_median", "circuity_mean", "circuity_median"):
        png = decode(out["rasters"][name])
        assert alpha_at(png, SINGLE) == 255, name
        for rc in PAIR:
            assert alpha_at(png, rc) == 255, name
        for rc in BLOCK2 + PARK4:
            assert alpha_at(png, rc) == 0, name
        assert alpha_at(png, WATER) == 0, name


def test_filled_value_is_neighbor_median():
    out = rasterize(make_layer(neighbor_bump=True))
    data = decode(out["data_raster"])
    assert alpha_at(data, SINGLE) == 255
    got = data[SINGLE[0], SINGLE[1], 0]
    expect = _quantize_p(np.array([1.0]))[0]  # median of the 8 bumped values
    assert abs(int(got) - int(expect)) <= 1


def test_data_png_matches_visual_validity():
    out = rasterize(make_layer())
    data = decode(out["data_raster"])
    visual = decode(out["rasters"]["p_median"])
    np.testing.assert_array_equal(data[:, :, 3] > 0, visual[:, :, 3] > 0)


def test_stats_unaffected_by_infill():
    on = rasterize(make_layer())
    off = rasterize(make_layer(), infill_min_neighbors=None)
    assert on["stats"] == off["stats"]


def test_disable_keeps_speck_transparent():
    out = rasterize(make_layer(), infill_min_neighbors=None)
    png = decode(out["rasters"]["p_median"])
    assert alpha_at(png, SINGLE) == 0
