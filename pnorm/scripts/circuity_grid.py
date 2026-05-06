"""Grid of circuity probes over Austin.

Hex grid of origins; each probes a ring of destinations at fixed radius.
Saves per-origin {mean circuity, mean excess, n_valid} to npz and renders
a hex-tile heatmap in UTM coordinates.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.patches import RegularPolygon
from tqdm import tqdm

from pnorm.circuity import ring_destinations
from pnorm.cities import use_city
from pnorm.geo import AUSTIN_BBOX, to_utm
from pnorm.grid import hex_grid_utm
from pnorm.osrm import OSRM


def run_grid(spacing_m, radius_m, n_dests, url, out_npz, bbox=AUSTIN_BBOX, inset_buffer_m=500.0):
    xy, lonlat = hex_grid_utm(bbox_lonlat=bbox, spacing_m=spacing_m, inset_m=radius_m + inset_buffer_m)
    n = len(xy)
    print(f"grid: {n} origins at {spacing_m:.0f} m spacing, ring r={radius_m:.0f} m × {n_dests}")

    osrm = OSRM(url)
    mean_circ = np.full(n, np.nan)
    mean_exc = np.full(n, np.nan)
    n_valid = np.zeros(n, dtype=int)
    origin_snap_m = np.full(n, np.nan)
    bad_origin = np.zeros(n, dtype=bool)

    # If the requested origin is in a road-free area (forest, water, deep
    # private parcel) OSRM happily snaps to the nearest road, which can be
    # very far away. Past `max_origin_snap_m` we consider the cell to have
    # no honest origin and mark `bad_origin = True` (renderers paint these
    # as p = 0). Default threshold = grid spacing — the snap moved us
    # farther than to a neighboring cell.
    max_origin_snap_m = float(spacing_m)

    max_snap_frac = 0.25
    for i in tqdm(range(n), desc="origins"):
        origin_ll = tuple(lonlat[i])
        dests_ll, _ = ring_destinations(origin_ll, radius_m, n_dests, seed=0)
        try:
            t, d_route, src_snap, dst_snap = osrm.table(
                [origin_ll],
                [tuple(p) for p in dests_ll],
                annotations="duration,distance",
                return_snapped=True,
            )
        except Exception:
            continue
        d_route = d_route[0]
        osnap_x, osnap_y = to_utm(src_snap[0, 0], src_snap[0, 1])
        o_snap_offset = float(np.hypot(float(osnap_x) - xy[i, 0],
                                       float(osnap_y) - xy[i, 1]))
        origin_snap_m[i] = o_snap_offset
        if o_snap_offset > max_origin_snap_m:
            bad_origin[i] = True
            continue  # don't even compute circuity — the origin isn't honest
        dsnap_x, dsnap_y = to_utm(dst_snap[:, 0], dst_snap[:, 1])
        dx, dy = to_utm(dests_ll[:, 0], dests_ll[:, 1])
        d_euc = np.hypot(np.asarray(dsnap_x) - float(osnap_x),
                         np.asarray(dsnap_y) - float(osnap_y))
        snap_off = np.hypot(np.asarray(dsnap_x) - np.asarray(dx),
                            np.asarray(dsnap_y) - np.asarray(dy))
        bad = snap_off > max_snap_frac * radius_m
        ok = np.isfinite(d_route) & (d_euc > 0) & ~bad
        if ok.sum() < 3:
            continue
        circ = d_route[ok] / d_euc[ok]
        mean_circ[i] = float(circ.mean())
        mean_exc[i] = float((d_route[ok] - d_euc[ok]).mean())
        n_valid[i] = int(ok.sum())

    n_bad = int(bad_origin.sum())
    n_meas = int(np.isfinite(mean_circ).sum())
    print(f"  cells: {n_meas} measured, {n_bad} bad-origin (>{max_origin_snap_m:.0f} m snap), "
          f"{n - n_meas - n_bad} dropped (no valid rays)")

    out = Path(out_npz)
    out.parent.mkdir(parents=True, exist_ok=True)
    from pnorm.geo import current_utm_epsg
    np.savez(
        out,
        xy_utm=xy,
        lonlat=lonlat,
        mean_circuity=mean_circ,
        mean_excess_m=mean_exc,
        n_valid=n_valid,
        spacing_m=spacing_m,
        radius_m=radius_m,
        n_dests=n_dests,
        utm_epsg=current_utm_epsg(),
        origin_snap_m=origin_snap_m,
        bad_origin=bad_origin,
        max_origin_snap_m=max_origin_snap_m,
    )
    print(f"saved {out}")
    return out


def render(npz_path, out_png, vmin=None, vmax=None):
    data = np.load(npz_path)
    xy = data["xy_utm"]
    circ = data["mean_circuity"]
    exc = data["mean_excess_m"]
    spacing = float(data["spacing_m"])
    radius = float(data["radius_m"])

    ok = np.isfinite(circ)
    if vmin is None:
        vmin = float(np.nanpercentile(circ, 5))
    if vmax is None:
        vmax = float(np.nanpercentile(circ, 95))

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    hex_r = spacing / np.sqrt(3)
    cmap = plt.get_cmap("plasma")

    for ax, values, title, label, vlo, vhi in [
        (axes[0], circ, f"Mean circuity  (ring r={radius/1000:.1f} km)", "circuity", vmin, vmax),
        (axes[1], exc / 1000.0,
         f"Mean excess distance (km)  (ring r={radius/1000:.1f} km)",
         "excess (km)",
         float(np.nanpercentile(exc[ok], 5) / 1000.0),
         float(np.nanpercentile(exc[ok], 95) / 1000.0)),
    ]:
        patches = []
        colors = []
        for i in range(len(xy)):
            if not np.isfinite(values[i]):
                continue
            patches.append(RegularPolygon(
                (xy[i, 0] / 1000.0, xy[i, 1] / 1000.0),
                numVertices=6,
                radius=hex_r / 1000.0,
                orientation=np.pi / 6,
            ))
            colors.append(values[i])
        pc = PatchCollection(patches, cmap=cmap, edgecolor="none")
        pc.set_array(np.asarray(colors))
        pc.set_clim(vlo, vhi)
        ax.add_collection(pc)
        plt.colorbar(pc, ax=ax, label=label, shrink=0.8)
        ax.set_aspect("equal")
        ax.set_xlim(xy[:, 0].min() / 1000.0 - 1, xy[:, 0].max() / 1000.0 + 1)
        ax.set_ylim(xy[:, 1].min() / 1000.0 - 1, xy[:, 1].max() / 1000.0 + 1)
        ax.set_xlabel("UTM 14N easting (km)")
        ax.set_ylabel("UTM 14N northing (km)")
        ax.set_title(title)
        ax.grid(alpha=0.2)

    s = (
        f"Austin circuity grid — {int(ok.sum())} origins, "
        f"mean {np.nanmean(circ):.3f}, median {np.nanmedian(circ):.3f}, "
        f"p95 {np.nanpercentile(circ, 95):.3f}"
    )
    fig.suptitle(s, y=1.00)
    fig.tight_layout()
    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"saved {out}")

    print(
        "stats (valid origins): "
        f"mean circuity={np.nanmean(circ):.3f}, "
        f"min={np.nanmin(circ):.3f}, "
        f"max={np.nanmax(circ):.3f}, "
        f"mean excess={np.nanmean(exc):.0f} m"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spacing", type=float, default=1500.0, help="hex grid spacing (m)")
    ap.add_argument("--radius", type=float, default=3000.0, help="ring radius (m)")
    ap.add_argument("--n", type=int, default=48, help="destinations per ring")
    ap.add_argument("--url", default="http://localhost:5001")
    ap.add_argument("--npz", default="data/circuity_grid.npz")
    ap.add_argument("--out", default="data/circuity_grid.png")
    ap.add_argument("--bbox", default=None,
                    help="min_lon,min_lat,max_lon,max_lat (overrides --city)")
    ap.add_argument("--city", default=None,
                    help="city key from pnorm/cities.py (sets bbox + UTM)")
    ap.add_argument("--render-only", action="store_true")
    a = ap.parse_args()

    if a.city:
        city = use_city(a.city)
        bbox = city.bbox
    else:
        bbox = AUSTIN_BBOX
    if a.bbox:
        bbox = tuple(float(x) for x in a.bbox.split(","))

    if not a.render_only:
        run_grid(a.spacing, a.radius, a.n, a.url, a.npz, bbox=bbox)
    render(a.npz, a.out)
