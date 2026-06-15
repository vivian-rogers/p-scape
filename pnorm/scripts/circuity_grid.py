"""Grid of circuity probes over a city.

Origins on a square or hex lattice; each probes a ring of destinations at
fixed radius. Saves per-origin {mean & median circuity, both effective_p
variants, n_valid, raw per-ray route distances, per-ray circuities} to npz
and renders a heatmap in UTM coordinates.
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
from pnorm.grid import hex_grid_utm, square_grid_utm
from pnorm.lp_inversion import p_of_circuity, p_of_median_circuity
from pnorm.osrm import OSRM


def run_grid(spacing_m, radius_m, n_dests, url, out_npz,
             bbox=AUSTIN_BBOX, inset_buffer_m=500.0,
             city_key=None, use_water_mask=True,
             grid_type="square", tile_buffer_m=0.0):
    # The origin grid is inset from the city bbox so the destination ring
    # stays inside the routable graph. When the OSRM tile build itself was
    # cropped with a `tile_buffer_m` margin around the city bbox, the graph
    # already extends that far, so we can shrink the origin inset by the
    # same amount and still have valid destinations. Always keep at least
    # `inset_buffer_m` of cushion for OSRM-side edge effects.
    inset_m = max(radius_m + inset_buffer_m - tile_buffer_m, inset_buffer_m)
    if grid_type == "square":
        xy, lonlat = square_grid_utm(bbox_lonlat=bbox, spacing_m=spacing_m,
                                     inset_m=inset_m)
    elif grid_type == "hex":
        xy, lonlat = hex_grid_utm(bbox_lonlat=bbox, spacing_m=spacing_m,
                                  inset_m=inset_m)
    else:
        raise ValueError(f"grid_type must be 'square' or 'hex', got {grid_type!r}")
    n = len(xy)
    print(f"grid: {n} origins ({grid_type}) at {spacing_m:.0f} m spacing, "
          f"ring r={radius_m:.0f} m × {n_dests} "
          f"(inset {inset_m:.0f} m, tile buffer {tile_buffer_m:.0f} m)")

    osrm = OSRM(url)
    mean_circ = np.full(n, np.nan)
    mean_exc = np.full(n, np.nan)
    n_valid = np.zeros(n, dtype=int)
    origin_snap_m = np.full(n, np.nan)
    bad_origin = np.zeros(n, dtype=bool)
    in_water = np.zeros(n, dtype=bool)

    # Pre-flag origins inside water polygons (rivers, lakes, harbors).
    # Without this, cells in e.g. the East River snap to nearby piers,
    # bridge decks, or riverwalks (snap < 75 m, under the foot threshold)
    # and produce meaningless circuity values. Skip them entirely.
    if use_water_mask and city_key:
        try:
            from pnorm.water_mask import load_water_mask, origins_in_water
            water_paths, hole_paths = load_water_mask(city_key, bbox)
            in_water = origins_in_water(lonlat, water_paths, hole_paths)
            bad_origin |= in_water
            print(f"  water mask: {int(in_water.sum())} cells flagged as in-water "
                  f"({len(water_paths)} water polys, {len(hole_paths)} holes)")
        except Exception as e:
            print(f"  water mask: skipped ({type(e).__name__}: {e})")
    # Per-direction circuity ratios kept around for downstream analysis
    # (median-based inversion, anisotropic fits, bimodality flags, future
    # Fourier-anisotropy spectrum). Float32 to halve the storage hit; NaN
    # for rays that failed the snap / route checks. The ring angles
    # `theta_dir` are shared across all origins (same seed=0, no jitter)
    # so we save just one length-n_dests vector.
    circuities = np.full((n, n_dests), np.nan, dtype=np.float32)
    # Raw per-ray route distances in meters, NaN where the ray failed.
    # Companion to `circuities`; lets future analyses compute arbitrary
    # distance-based quantiles (IQR, q90, etc.) without rerunning OSRM.
    d_route_m = np.full((n, n_dests), np.nan, dtype=np.float32)
    theta_dir = np.linspace(0.0, 2 * np.pi, n_dests, endpoint=False)

    # If the requested origin is in a road-free area (forest, water, deep
    # private parcel) OSRM happily snaps to the nearest road, which can be
    # very far away. We reject the cell if either:
    #   (1) the origin snap moves more than min(spacing_m, 100 m) — in
    #       sparse-network regions a 250 m car snap is a city block away;
    #       cap the absolute distance regardless of spacing, or
    #   (2) fewer than 50 % of the destinations route successfully — the
    #       origin may have snapped to a small disconnected component.
    # Either trip flips `bad_origin = True` and the cell renders at p = 0.
    max_origin_snap_m = float(min(spacing_m, 100.0))
    min_valid_rays = max(3, int(round(n_dests * 0.5)))

    max_snap_frac = 0.25
    for i in tqdm(range(n), desc="origins"):
        if bad_origin[i]:
            # Pre-flagged (water mask hit). Don't waste an OSRM call.
            continue
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
            continue  # origin isn't on a road within tolerance
        dsnap_x, dsnap_y = to_utm(dst_snap[:, 0], dst_snap[:, 1])
        dx, dy = to_utm(dests_ll[:, 0], dests_ll[:, 1])
        d_euc = np.hypot(np.asarray(dsnap_x) - float(osnap_x),
                         np.asarray(dsnap_y) - float(osnap_y))
        snap_off = np.hypot(np.asarray(dsnap_x) - np.asarray(dx),
                            np.asarray(dsnap_y) - np.asarray(dy))
        bad = snap_off > max_snap_frac * radius_m
        ok = np.isfinite(d_route) & (d_euc > 0) & ~bad
        n_valid[i] = int(ok.sum())
        if ok.sum() < min_valid_rays:
            # Too few destinations route successfully — origin is on an
            # island in the routing graph. Same flag as bad-snap origins.
            bad_origin[i] = True
            continue
        circ = d_route[ok] / d_euc[ok]
        mean_circ[i] = float(circ.mean())
        mean_exc[i] = float((d_route[ok] - d_euc[ok]).mean())
        # Cache the per-direction ratios + raw routed distances for this cell
        # (NaN in slots that failed snap/route checks). theta_dir is uniform
        # across cells.
        circuities[i, ok] = circ.astype(np.float32)
        d_route_m[i, ok] = d_route[ok].astype(np.float32)

    n_bad = int(bad_origin.sum())
    n_water = int(in_water.sum())
    n_meas = int(np.isfinite(mean_circ).sum())
    print(f"  cells: {n_meas} measured, {n_bad} bad-origin "
          f"({n_water} water + {n_bad - n_water} snap/connectivity), "
          f"{n - n_meas - n_bad} dropped (no valid rays)")

    # Native median circuity (was add_median_overlay.py postproc) +
    # effective_p_{mean,median} inversions. nanmedian over the per-ray axis
    # collapses (n, n_dests) → (n,); cells with no valid rays stay NaN.
    with np.errstate(all="ignore"):
        median_circ = np.nanmedian(circuities.astype(np.float64), axis=1)
    eff_p_mean = np.full(n, np.nan)
    eff_p_median = np.full(n, np.nan)
    mfin = np.isfinite(mean_circ)
    if mfin.any():
        eff_p_mean[mfin] = p_of_circuity(mean_circ[mfin])
    medfin = np.isfinite(median_circ)
    if medfin.any():
        eff_p_median[medfin] = p_of_median_circuity(median_circ[medfin])

    out = Path(out_npz)
    out.parent.mkdir(parents=True, exist_ok=True)
    from pnorm.geo import current_utm_epsg
    np.savez(
        out,
        xy_utm=xy,
        lonlat=lonlat,
        mean_circuity=mean_circ,
        median_circuity=median_circ,
        effective_p_mean=eff_p_mean,
        effective_p_median=eff_p_median,
        mean_excess_m=mean_exc,
        n_valid=n_valid,
        spacing_m=spacing_m,
        radius_m=radius_m,
        n_dests=n_dests,
        utm_epsg=current_utm_epsg(),
        origin_snap_m=origin_snap_m,
        bad_origin=bad_origin,
        in_water=in_water,
        max_origin_snap_m=max_origin_snap_m,
        grid_type=np.array(grid_type),
        # Per-direction circuities: shape (n_cells, n_dests), float32, NaN
        # for failed rays. theta_dir gives the angle of each column (radians,
        # 0 = east, CCW). Same angles for every cell in the grid.
        circuities=circuities,
        # Raw per-ray route distances in meters, companion to circuities.
        d_route_m=d_route_m,
        theta_dir=theta_dir,
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
    ap.add_argument("--no-water-mask", action="store_true",
                    help="skip the OSM water-polygon mask (only relevant with --city)")
    ap.add_argument("--grid-type", choices=("square", "hex"), default="square",
                    help="origin lattice: 'square' (default) or 'hex' (legacy)")
    ap.add_argument("--tile-buffer-m", type=float, default=0.0,
                    help="meters of OSRM-graph buffer beyond the city bbox. "
                         "Shrinks the origin inset by this amount — set when "
                         "BUFFER_M was used during tile build (e.g. 17000 for "
                         "16 km car rings).")
    a = ap.parse_args()

    if a.city:
        city = use_city(a.city)
        bbox = city.bbox
    else:
        bbox = AUSTIN_BBOX
    if a.bbox:
        bbox = tuple(float(x) for x in a.bbox.split(","))

    if not a.render_only:
        run_grid(a.spacing, a.radius, a.n, a.url, a.npz, bbox=bbox,
                 city_key=a.city, use_water_mask=not a.no_water_mask,
                 grid_type=a.grid_type, tile_buffer_m=a.tile_buffer_m)
    render(a.npz, a.out)
