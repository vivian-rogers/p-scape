"""Circuity probe: for a given origin, probe N destinations on a ring of radius R.

Reports mean/median excess distance (route − euclid) and circuity ratio (route / euclid).
Plots d_route vs θ and the ring of destinations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pnorm.circuity import circuity_from_origin
from pnorm.osrm import OSRM

AUSTIN_LANDMARKS = {
    "downtown": (-97.7431, 30.2672),
    "ut_tower": (-97.7394, 30.2862),
    "mueller": (-97.7050, 30.3000),
    "domain": (-97.7250, 30.4020),
    "circle_c": (-97.8780, 30.2140),
}


def main(origin, radius_m, n_dests, url, out, tag, seed):
    osrm = OSRM(url)
    print(f"origin={origin}  radius={radius_m} m  n={n_dests}")
    res = circuity_from_origin(origin, radius_m, n_dests, osrm, seed=seed)

    s = res.summary()
    print(json.dumps(s, indent=2))

    ok = np.isfinite(res.d_route) & (res.d_euclid > 0)
    theta = res.theta[ok]
    d_route = res.d_route[ok]
    d_euc = res.d_euclid[ok]
    excess = d_route - d_euc
    circ = d_route / d_euc
    theta_deg = np.degrees(np.mod(theta, 2 * np.pi))

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    ax = axes[0]
    ax.scatter(theta_deg, circ, s=20, alpha=0.7, color="steelblue")
    ax.axhline(1.0, color="gray", ls="--", lw=0.8, label="straight-line")
    ax.axhline(s["mean_circuity"], color="crimson", ls="-", lw=1.2,
               label=f"mean={s['mean_circuity']:.3f}")
    ax.set_xlabel("heading θ (deg, 0 = east)")
    ax.set_ylabel("circuity  d_route / d_euclid")
    ax.set_title(f"Circuity vs heading  (radius {radius_m/1000:.1f} km)")
    ax.set_xlim(0, 360)
    ax.set_ylim(bottom=0.95)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(alpha=0.3)

    ax = axes[1]
    ax.scatter(theta_deg, excess / 1000.0, s=20, alpha=0.7, color="darkorange")
    ax.axhline(excess.mean() / 1000.0, color="crimson", ls="-", lw=1.2,
               label=f"mean={s['mean_excess_m']:.0f} m")
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.set_xlabel("heading θ (deg)")
    ax.set_ylabel("excess distance (km)")
    ax.set_title(f"Excess vs heading  (origin radius {radius_m/1000:.1f} km)")
    ax.set_xlim(0, 360)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(alpha=0.3)

    ax = axes[2]
    ox, oy = res.origin_xy
    dx = res.dest_xy[ok, 0]
    dy = res.dest_xy[ok, 1]
    sc = ax.scatter((dx - ox) / 1000.0, (dy - oy) / 1000.0, c=circ,
                    cmap="plasma", s=30, vmin=1.0, vmax=max(1.5, np.percentile(circ, 90)))
    ax.scatter([0], [0], color="black", s=80, marker="*", label="origin")
    ax.set_aspect("equal")
    ax.set_xlabel("east (km)")
    ax.set_ylabel("north (km)")
    ax.set_title("Destinations (color = circuity)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=9)
    plt.colorbar(sc, ax=ax, label="circuity")

    fig.suptitle(f"{tag}  —  mean circuity {s['mean_circuity']:.3f}, mean excess {s['mean_excess_m']/1000:.2f} km", y=1.02)

    out_p = Path(out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_p, dpi=120, bbox_inches="tight")
    print(f"saved {out_p}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default="downtown",
                    help=f"landmark name or 'lon,lat'. known: {list(AUSTIN_LANDMARKS)}")
    ap.add_argument("--radius", type=float, default=5000.0, help="radius in meters")
    ap.add_argument("--n", type=int, default=72, help="number of destinations on ring")
    ap.add_argument("--url", default="http://localhost:5001")
    ap.add_argument("--out", default=None)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    if a.origin in AUSTIN_LANDMARKS:
        origin = AUSTIN_LANDMARKS[a.origin]
        tag = a.origin
    else:
        lon, lat = (float(x) for x in a.origin.split(","))
        origin = (lon, lat)
        tag = f"{lon:.4f},{lat:.4f}"

    out = a.out or f"data/circuity_{tag}_{int(a.radius)}m.png"
    main(origin, a.radius, a.n, a.url, out, tag, a.seed)
