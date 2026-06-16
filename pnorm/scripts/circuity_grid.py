"""Grid of K-jittered Monte Carlo circuity probes over a city.

Origins are tiled on a square (or hex, legacy) lattice. For each tile we
sample K = ``n_samples`` origins uniformly inside the tile and shoot one
ray per origin at the fixed angle θ_k = 2πk/K. The K rays form a
clean Monte Carlo estimate of the tile-averaged angular circuity profile;
the empirical Fourier coefficients of that profile are an unbiased
estimate of the spatially-windowed Fourier descriptor.

OSRM can't batch K different (origin, destination) pairs into one /table
call, so we fire K /route calls in parallel with a bounded asyncio
concurrency semaphore.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.patches import RegularPolygon
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from pnorm.cities import use_city
from pnorm.geo import AUSTIN_BBOX, to_lonlat, to_utm
from pnorm.grid import hex_grid_utm, square_grid_utm
from pnorm.lp_inversion import p_of_circuity, p_of_median_circuity
from pnorm.osrm import AsyncOSRM


async def run_grid(spacing_m, radius_m, n_samples, url, out_npz,
                   bbox=AUSTIN_BBOX, inset_buffer_m=500.0,
                   city_key=None, use_water_mask=True,
                   grid_type="square", tile_buffer_m=0.0,
                   concurrency=16, seed=None, save_full_matrix=True):
    # The origin grid is inset from the city bbox so the destination ring
    # stays inside the routable graph. The K jittered origins live inside
    # the tile box, so add half a spacing of extra cushion. When the OSRM
    # tile build itself was cropped with a `tile_buffer_m` margin around
    # the city bbox we can shrink the inset by the same amount.
    inset_m = max(radius_m + inset_buffer_m + spacing_m / 2 - tile_buffer_m,
                  inset_buffer_m)
    if grid_type == "square":
        xy, lonlat = square_grid_utm(bbox_lonlat=bbox, spacing_m=spacing_m,
                                     inset_m=inset_m)
    elif grid_type == "hex":
        xy, lonlat = hex_grid_utm(bbox_lonlat=bbox, spacing_m=spacing_m,
                                  inset_m=inset_m)
    else:
        raise ValueError(f"grid_type must be 'square' or 'hex', got {grid_type!r}")
    n = len(xy)
    print(f"grid: {n} tiles ({grid_type}) at {spacing_m:.0f} m spacing, "
          f"K={n_samples} jittered origins per tile, ring r={radius_m:.0f} m "
          f"(inset {inset_m:.0f} m, tile buffer {tile_buffer_m:.0f} m, "
          f"concurrency {concurrency})")

    mean_circ = np.full(n, np.nan)
    mean_exc = np.full(n, np.nan)
    n_valid = np.zeros(n, dtype=int)
    origin_snap_m = np.full(n, np.nan)
    bad_origin = np.zeros(n, dtype=bool)
    in_water = np.zeros(n, dtype=bool)

    if use_water_mask and city_key:
        try:
            from pnorm.water_mask import load_water_mask, origins_in_water
            water_paths, hole_paths = load_water_mask(city_key, bbox)
            in_water = origins_in_water(lonlat, water_paths, hole_paths)
            bad_origin |= in_water
            print(f"  water mask: {int(in_water.sum())} tiles flagged as in-water "
                  f"({len(water_paths)} water polys, {len(hole_paths)} holes)")
        except Exception as e:
            print(f"  water mask: skipped ({type(e).__name__}: {e})")

    # Diagonal-only per-ray data (the "K=48 jittered MC" samples) consumed
    # by rasterize.py and downstream analysis. With K-jittered sampling,
    # circuities[i, k] is the circuity of the k-th (jittered origin, ring
    # destination at angle θ_k) pair — angular axis is now spatially
    # averaged across the tile.
    circuities = np.full((n, n_samples), np.nan, dtype=np.float32)
    d_route_m = np.full((n, n_samples), np.nan, dtype=np.float32)
    theta_dir = np.linspace(0.0, 2 * np.pi, n_samples, endpoint=False)
    cos_t = np.cos(theta_dir)
    sin_t = np.sin(theta_dir)

    # The OFF-DIAGONAL pairs of the /table call are free data: each is a
    # route from a random tile origin to a random-tile-offset + radial
    # destination. Displacement is r·u_θ + (origin_j − origin_i), so they
    # sample displacements within ±spacing of the canonical ring radius.
    # Saved in a sidecar npz (compressed) so the main npz stays small.
    if save_full_matrix:
        d_route_matrix_m = np.full((n, n_samples, n_samples), np.nan, dtype=np.float32)
        src_snap_lonlat  = np.full((n, n_samples, 2), np.nan, dtype=np.float32)
        dst_snap_lonlat  = np.full((n, n_samples, 2), np.nan, dtype=np.float32)
    else:
        d_route_matrix_m = src_snap_lonlat = dst_snap_lonlat = None

    max_origin_snap_m = float(min(spacing_m, 100.0))
    min_valid_rays = max(3, int(round(n_samples * 0.5)))
    max_snap_frac = 0.25

    if seed is None:
        seed = abs(hash((url, int(spacing_m), int(radius_m), n_samples,
                         "k_jittered_v1"))) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    print(f"  rng seed: {seed}")

    # Pre-generate all jittered offsets up front. With deterministic rng,
    # we can do this in O(n·K) at startup rather than inside the hot loop.
    all_offsets = rng.uniform(-spacing_m / 2.0, spacing_m / 2.0,
                              (n, n_samples, 2)).astype(np.float64)

    async def process_tile(i):
        """Process one tile: K-jittered Monte Carlo via a single /table call.

        Issues ONE OSRM /table query of K sources × K destinations per tile.
        The diagonal (origin_k → destination_k) is the principal sample;
        the off-diagonal pairs are saved to the sidecar matrix.
        """
        if bad_origin[i]:
            return
        offsets = all_offsets[i]
        origins_utm = xy[i] + offsets
        dests_utm = origins_utm + np.column_stack([radius_m * cos_t, radius_m * sin_t])

        ol_lon, ol_lat = to_lonlat(origins_utm[:, 0], origins_utm[:, 1])
        dl_lon, dl_lat = to_lonlat(dests_utm[:, 0], dests_utm[:, 1])
        sources = list(zip(np.asarray(ol_lon, dtype=float).tolist(),
                           np.asarray(ol_lat, dtype=float).tolist()))
        dests   = list(zip(np.asarray(dl_lon, dtype=float).tolist(),
                           np.asarray(dl_lat, dtype=float).tolist()))

        result = await osrm.table(sources, dests)
        if result is None:
            return
        distances, src_snap_ll, dst_snap_ll = result   # (K,K), (K,2), (K,2) — lonlat snaps

        # Convert snapped lon/lat to UTM for distance math.
        osnap_x, osnap_y = to_utm(src_snap_ll[:, 0], src_snap_ll[:, 1])
        dsnap_x, dsnap_y = to_utm(dst_snap_ll[:, 0], dst_snap_ll[:, 1])
        osnap_x = np.asarray(osnap_x, dtype=float)
        osnap_y = np.asarray(osnap_y, dtype=float)
        dsnap_x = np.asarray(dsnap_x, dtype=float)
        dsnap_y = np.asarray(dsnap_y, dtype=float)

        o_snap_off = np.hypot(osnap_x - origins_utm[:, 0], osnap_y - origins_utm[:, 1])
        d_snap_off = np.hypot(dsnap_x - dests_utm[:, 0],   dsnap_y - dests_utm[:, 1])

        # Diagonal: route_k = origin_k → dest_k. Read distances[k, k].
        d_route_diag = distances[np.arange(n_samples), np.arange(n_samples)]
        d_euclid = np.hypot(dsnap_x - osnap_x, dsnap_y - osnap_y)

        ok = (np.isfinite(d_route_diag)
              & (d_euclid > 0)
              & (o_snap_off <= max_origin_snap_m)
              & (d_snap_off <= max_snap_frac * radius_m))
        n_valid_i = int(ok.sum())
        n_valid[i] = n_valid_i
        if n_valid_i < min_valid_rays:
            bad_origin[i] = True
            return
        origin_snap_m[i] = float(np.nanmean(o_snap_off))
        circ_ok = d_route_diag[ok] / d_euclid[ok]
        mean_circ[i] = float(circ_ok.mean())
        mean_exc[i] = float((d_route_diag[ok] - d_euclid[ok]).mean())
        circuities[i, ok] = circ_ok.astype(np.float32)
        d_route_m[i, ok] = d_route_diag[ok].astype(np.float32)

        if save_full_matrix:
            d_route_matrix_m[i] = distances.astype(np.float32)
            src_snap_lonlat[i] = src_snap_ll.astype(np.float32)
            dst_snap_lonlat[i] = dst_snap_ll.astype(np.float32)

    async with AsyncOSRM(url, concurrency=concurrency) as osrm:
        await tqdm_asyncio.gather(
            *[process_tile(i) for i in range(n)],
            total=n, desc="tiles", mininterval=2.0,
        )

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
    np.savez_compressed(
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
        n_dests=n_samples,          # kept name for backward-compat; now = K samples
        n_samples=n_samples,        # explicit
        rng_seed=seed,              # reconstructs jittered origins
        utm_epsg=current_utm_epsg(),
        origin_snap_m=origin_snap_m,
        bad_origin=bad_origin,
        in_water=in_water,
        max_origin_snap_m=max_origin_snap_m,
        grid_type=np.array(grid_type),
        # Per-ray (K=n_samples) circuity ratios. Float32, NaN for rays that
        # failed snap/route. With K-jittered sampling, column k holds the
        # circuity at angle θ_k=2πk/K from a DIFFERENT jittered origin
        # inside the tile — angular axis is spatially averaged across the tile.
        circuities=circuities,
        # Raw per-ray route distances in meters, companion to circuities.
        d_route_m=d_route_m,
        theta_dir=theta_dir,
    )
    print(f"saved {out}")

    # Sidecar: full K×K route-distance matrix per tile + per-ray snap
    # positions. The diagonal coincides with `d_route_m`; the off-diagonal
    # is free data from the /table batch — routes between random tile
    # points with displacement ≈ R·u_θ ± in-tile-jitter. Worth caching
    # against future analyses (anisotropic kernels, distance histograms,
    # graph-spectral work) even though the main pipeline ignores it.
    if save_full_matrix and d_route_matrix_m is not None:
        full_out = out.with_name(out.stem + "_full.npz")
        np.savez_compressed(
            full_out,
            d_route_matrix_m=d_route_matrix_m,
            src_snap_lonlat=src_snap_lonlat,
            dst_snap_lonlat=dst_snap_lonlat,
            theta_dir=theta_dir,
            spacing_m=spacing_m,
            radius_m=radius_m,
            n_samples=n_samples,
            rng_seed=seed,
            utm_epsg=current_utm_epsg(),
        )
        size_mb = full_out.stat().st_size / 1024 / 1024
        print(f"saved {full_out} ({size_mb:.1f} MB compressed full matrix)")
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
    ap.add_argument("--n", type=int, default=48,
                    help="K — number of jittered Monte Carlo (origin, angle) samples per tile")
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
    ap.add_argument("--concurrency", type=int, default=16,
                    help="max in-flight OSRM /table requests (default 16, "
                         "matches the docker-compose --threads 8 setting × 2 queue depth)")
    ap.add_argument("--seed", type=int, default=None,
                    help="rng seed for jittered origins (default: hash of (url, "
                         "spacing, radius, K))")
    ap.add_argument("--no-full-matrix", action="store_true",
                    help="skip the sidecar K×K full-distance-matrix npz "
                         "(big — ~150-300 MB per layer compressed)")
    a = ap.parse_args()

    if a.city:
        city = use_city(a.city)
        bbox = city.bbox
    else:
        bbox = AUSTIN_BBOX
    if a.bbox:
        bbox = tuple(float(x) for x in a.bbox.split(","))

    if not a.render_only:
        asyncio.run(
            run_grid(a.spacing, a.radius, a.n, a.url, a.npz, bbox=bbox,
                     city_key=a.city, use_water_mask=not a.no_water_mask,
                     grid_type=a.grid_type, tile_buffer_m=a.tile_buffer_m,
                     concurrency=a.concurrency, seed=a.seed,
                     save_full_matrix=not a.no_full_matrix)
        )
    render(a.npz, a.out)
