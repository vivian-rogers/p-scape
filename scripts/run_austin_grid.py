"""Smoke-run: 7×7 grid over central Austin, 10-minute drive isochrones, fit each.

Usage:
    uv run python scripts/run_austin_grid.py [--minutes 10] [--n 7]

Writes data/results/austin_<n>x<n>_<min>min.jsonl.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from isochrone_metric.grid import (
    GridResult,
    make_grid,
    run_grid,
    save_results_jsonl,
)

# Austin metro bbox — roughly Travis County core. (south, west, north, east)
AUSTIN_BBOX = (30.18, -97.92, 30.50, -97.60)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--n", type=int, default=7, help="grid is n × n")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--url", default="http://localhost:8002")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    origins = make_grid(AUSTIN_BBOX, args.n, args.n)
    print(f"Running {len(origins)} origins at {args.minutes} min …")
    results = run_grid(origins, minutes=args.minutes, url=args.url, max_workers=args.workers)

    n_ok = sum(1 for r in results if r.error is None)
    n_err = len(results) - n_ok
    print(f"Done: {n_ok} ok, {n_err} errors")

    out = args.out or Path(f"data/results/austin_{args.n}x{args.n}_{int(args.minutes)}min.jsonl")
    save_results_jsonl(results, out)
    print(f"Wrote {out}")

    if n_ok:
        ok = [r for r in results if r.error is None]
        anis = sorted(r.anisotropy for r in ok)
        spds = sorted(r.mean_speed_mps for r in ok)
        print()
        print("Anisotropy ratio (slow/fast):")
        print(f"  median {anis[len(anis)//2]:.2f}  min {anis[0]:.2f}  max {anis[-1]:.2f}")
        print("Effective mean speed (m/s, ~ mph in parens):")
        med = spds[len(spds) // 2]
        print(f"  median {med:.1f} m/s ({med * 2.237:.0f} mph)")
        print(f"  min    {spds[0]:.1f} m/s ({spds[0] * 2.237:.0f} mph)")
        print(f"  max    {spds[-1]:.1f} m/s ({spds[-1] * 2.237:.0f} mph)")

    if n_err:
        print()
        print("Errors:")
        for r in results:
            if r.error:
                print(f"  ({r.lat:.4f}, {r.lon:.4f}) -> {r.error}")


if __name__ == "__main__":
    main()
