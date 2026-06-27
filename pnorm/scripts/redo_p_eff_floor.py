"""Re-derive effective_p_mean and effective_p_median from the cached
mean_circuity / median_circuity fields with a new p_min floor (default 0.01).

Use after changing the default in pnorm/src/pnorm/lp_inversion.py. Writes
each npz in place with the updated p fields; everything else is preserved.

No OSRM, no resampling — pure post-processing of cached circuity values.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

from pnorm.lp_inversion import p_of_circuity, p_of_median_circuity


PAT = re.compile(r"(.+)_(car|foot)_sq_r(\d+)$")


def process(npz_path: Path, p_min: float, p_max: float = 3.0, dry_run: bool = False):
    d = dict(np.load(npz_path, allow_pickle=True))
    if "mean_circuity" not in d or "median_circuity" not in d:
        print(f"  ! {npz_path.name}: missing circuity fields — skipping")
        return

    c_mean   = np.asarray(d["mean_circuity"],   dtype=np.float64)
    c_median = np.asarray(d["median_circuity"], dtype=np.float64)

    new_p_mean   = np.full_like(c_mean,   np.nan)
    new_p_median = np.full_like(c_median, np.nan)
    fm = np.isfinite(c_mean)
    fM = np.isfinite(c_median)
    if fm.any():
        new_p_mean[fm]   = p_of_circuity(c_mean[fm],   p_min=p_min, p_max=p_max)
    if fM.any():
        new_p_median[fM] = p_of_median_circuity(c_median[fM], p_min=p_min, p_max=p_max)

    # Report changes
    if "effective_p_mean" in d:
        old = np.asarray(d["effective_p_mean"], dtype=np.float64)
        n_floor_was = int((np.isfinite(old) & (old < 0.301)).sum())
        n_unfloored = int((np.isfinite(old) & (old < 0.301) &
                            np.isfinite(new_p_mean) & (new_p_mean < 0.295)).sum())
    else:
        n_floor_was = n_unfloored = 0

    d["effective_p_mean"]   = new_p_mean.astype(np.float32)
    d["effective_p_median"] = new_p_median.astype(np.float32)

    if not dry_run:
        np.savez_compressed(npz_path, **d)
    print(f"  {npz_path.name}: n_unfloored = {n_unfloored}, new p10 = {np.nanpercentile(new_p_mean, 10):.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p-min", type=float, default=0.01)
    ap.add_argument("--p-max", type=float, default=3.0)
    ap.add_argument("--only", default="", help="comma-separated city keys to limit to")
    ap.add_argument("--mode", default="", help="car|foot, blank = both")
    ap.add_argument("--dry", action="store_true", help="don't write back")
    args = ap.parse_args()

    only = set(s.strip() for s in args.only.split(",") if s.strip())
    paths = sorted(Path("data").glob("*_sq_r*.npz"))
    if args.mode:
        paths = [p for p in paths if f"_{args.mode}_sq_" in p.name]
    if only:
        paths = [p for p in paths if PAT.match(p.stem) and PAT.match(p.stem).group(1) in only]

    print(f"processing {len(paths)} npz files, p_min={args.p_min}, p_max={args.p_max}, dry={args.dry}")
    for path in paths:
        process(path, args.p_min, args.p_max, args.dry)


if __name__ == "__main__":
    main()
