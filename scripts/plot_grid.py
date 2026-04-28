"""Plots from a grid result JSONL: ellipse field + scalar heatmap-scatters."""
from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import EllipseCollection
from matplotlib.colors import LogNorm

from isochrone_metric.grid import GridResult


def load(path: Path) -> list[GridResult]:
    field_names = {f.name for f in fields(GridResult)}
    out: list[GridResult] = []
    with Path(path).open() as fh:
        for line in fh:
            d = json.loads(line)
            out.append(GridResult(**{k: v for k, v in d.items() if k in field_names}))
    return [r for r in out if r.error is None]


def plot_ellipse_field(results: list[GridResult], out_path: Path) -> None:
    """Show one ellipse per origin: orientation = principal axes, color = mean speed.

    Ellipse size is fixed (purely indicative of orientation/aspect), so the field
    is readable even where the grid is dense.
    """
    lons = np.array([r.lon for r in results])
    lats = np.array([r.lat for r in results])
    aspect = np.array([r.slow_speed_mps / r.fast_speed_mps for r in results])
    # Aspect inverted: ellipse minor axis is along the SLOW direction (less reach in t).
    # Visual size: width along fast axis, height along slow axis.
    inv_aspect = np.array([r.fast_speed_mps / r.slow_speed_mps for r in results])  # ≤ 1
    angles_deg = np.array([r.fast_axis_deg for r in results])
    speeds = np.array([r.mean_speed_mps for r in results])

    # Pick an ellipse half-width that fits the grid spacing visually.
    dx = (lons.max() - lons.min()) / max(1, int(np.sqrt(len(lons))) - 1)
    dy = (lats.max() - lats.min()) / max(1, int(np.sqrt(len(lats))) - 1)
    base = 0.6 * min(dx, dy)
    widths = np.full_like(speeds, base)
    heights = base * inv_aspect

    fig, ax = plt.subplots(figsize=(9, 9))
    coll = EllipseCollection(
        widths=widths,
        heights=heights,
        angles=angles_deg,
        units="xy",
        offsets=np.column_stack([lons, lats]),
        transOffset=ax.transData,
        cmap="viridis",
        edgecolor="black",
        linewidth=0.6,
    )
    coll.set_array(speeds * 2.237)  # mph for readability
    ax.add_collection(coll)
    ax.autoscale_view()
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    ax.set_title("Local effective-speed ellipses (Austin, 10-min isochrones)\nmajor axis = fast direction; aspect = anisotropy; color = mean effective speed (mph)")
    cb = fig.colorbar(coll, ax=ax, fraction=0.04)
    cb.set_label("mean effective speed (mph)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_scalar_field(
    results: list[GridResult],
    value_fn,
    label: str,
    out_path: Path,
    *,
    cmap: str = "magma",
    log: bool = False,
) -> None:
    lons = np.array([r.lon for r in results])
    lats = np.array([r.lat for r in results])
    vals = np.array([value_fn(r) for r in results])

    fig, ax = plt.subplots(figsize=(9, 9))
    norm = LogNorm(vmin=max(vals.min(), 1e-6), vmax=vals.max()) if log else None
    sc = ax.scatter(lons, lats, c=vals, cmap=cmap, s=240, edgecolor="black", linewidth=0.4, norm=norm)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("lon")
    ax.set_ylabel("lat")
    ax.set_title(label)
    cb = fig.colorbar(sc, ax=ax, fraction=0.04)
    cb.set_label(label)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="path to a grid JSONL")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args()

    results = load(args.input)
    if not results:
        raise SystemExit("no successful fits in input")

    outdir = args.outdir or args.input.parent / "plots"
    outdir.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem

    plot_ellipse_field(results, outdir / f"{stem}_ellipses.png")
    plot_scalar_field(
        results,
        lambda r: r.mean_speed_mps * 2.237,
        "Mean effective speed (mph)",
        outdir / f"{stem}_speed.png",
    )
    plot_scalar_field(
        results,
        lambda r: r.anisotropy,
        "Anisotropy ratio (slow / fast)",
        outdir / f"{stem}_anisotropy.png",
        log=True,
    )
    print(f"Wrote {outdir}")


if __name__ == "__main__":
    main()
