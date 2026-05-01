"""Framework F smoke test: τ·v̄/d vs heading θ, overlaid with L^p curves.

Runs stratified OD pairs through a local OSRM and plots the detour-ratio
scatter. Expects OSRM at --url (default http://localhost:5000).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from pnorm.geo import to_utm
from pnorm.osrm import OSRM
from pnorm.sampling import stratified_od_pairs


def main(n: int, url: str, out: str, use_table: bool, seed: int) -> None:
    origins, dests = stratified_od_pairs(n, seed=seed)
    osrm = OSRM(url)

    if use_table:
        batch = 100
        taus = np.empty(n)
        for i in tqdm(range(0, n, batch), desc="table"):
            end = min(i + batch, n)
            m = osrm.table(origins[i:end], dests[i:end])
            taus[i:end] = np.diag(m)
    else:
        taus = np.empty(n)
        for i in tqdm(range(n), desc="route"):
            taus[i] = osrm.route(tuple(origins[i]), tuple(dests[i]))

    ox, oy = to_utm(origins[:, 0], origins[:, 1])
    dx, dy = to_utm(dests[:, 0], dests[:, 1])
    vx = np.asarray(dx) - np.asarray(ox)
    vy = np.asarray(dy) - np.asarray(oy)
    d = np.hypot(vx, vy)
    theta = np.arctan2(vy, vx)

    ok = (taus > 0) & np.isfinite(taus) & (d > 0)
    taus, d, theta = taus[ok], d[ok], theta[ok]

    speed = d / taus
    v_bar = float(np.percentile(speed, 95))
    R = taus * v_bar / d

    theta_deg = np.degrees(np.mod(theta, 2 * np.pi))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    ax1.scatter(theta_deg, R, s=5, alpha=0.35, color="k")
    tt = np.linspace(0, 2 * np.pi, 361)
    for p, col in [(0.5, "red"), (1.0, "orange"), (1.5, "blue"), (2.0, "green")]:
        curve = (np.abs(np.cos(tt)) ** p + np.abs(np.sin(tt)) ** p) ** (1 / p)
        ax1.plot(np.degrees(tt), curve, color=col, label=f"p={p}", lw=1.5)
    ax1.set_xlabel("heading θ (deg, 0 = east)")
    ax1.set_ylabel("R = τ · v̄ / d")
    ax1.set_title(f"Detour ratio vs heading ({len(R)} pairs, v̄={v_bar * 2.237:.1f} mph)")
    ax1.axhline(1.0, color="gray", lw=0.5, ls="--")
    ax1.set_ylim(0.6, 2.6)
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(alpha=0.3)

    theta_fold = np.mod(theta, np.pi / 2)
    ax2.scatter(np.degrees(theta_fold), R, s=5, alpha=0.35, color="k")
    tt2 = np.linspace(0, np.pi / 2, 181)
    for p, col in [(0.5, "red"), (1.0, "orange"), (1.5, "blue"), (2.0, "green")]:
        curve = (np.abs(np.cos(tt2)) ** p + np.abs(np.sin(tt2)) ** p) ** (1 / p)
        ax2.plot(np.degrees(tt2), curve, color=col, label=f"p={p}", lw=1.5)
    ax2.set_xlabel("|θ mod 90°| (deg)")
    ax2.set_ylabel("R")
    ax2.set_title("Folded to [0°, 90°] (assumes axis-aligned)")
    ax2.axhline(1.0, color="gray", lw=0.5, ls="--")
    ax2.set_ylim(0.6, 2.6)
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(alpha=0.3)

    out_p = Path(out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_p, dpi=120)
    print(f"v̄ (95th-pct d/τ) = {v_bar:.2f} m/s = {v_bar * 2.237:.1f} mph")
    print(f"R: median={np.median(R):.3f}  mean={np.mean(R):.3f}  p95={np.percentile(R, 95):.3f}")
    print(f"saved {out_p}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--url", default="http://localhost:5000")
    ap.add_argument("--out", default="data/smoke.png")
    ap.add_argument("--route", action="store_true", help="use /route instead of /table")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    main(a.n, a.url, a.out, use_table=not a.route, seed=a.seed)
