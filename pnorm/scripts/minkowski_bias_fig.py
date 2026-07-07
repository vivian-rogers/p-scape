"""Figure: why the rotated anisotropic Minkowski fit exists.

Renders docs/figures/minkowski_fit_bias.png, three panels:
  (a) directional circuity curves of the model family,
  (b) bias of axis-aligned estimators under pure rotation (true p = 1),
  (c) bias under pure anisotropy (true p = 1, b/a varies).

Run from pnorm/:  uv run python scripts/minkowski_bias_fig.py
"""

import matplotlib.pyplot as plt
import numpy as np

from pnorm.lp_inversion import (
    mle_p_from_directional_circuities,
    p_of_circuity,
    p_of_median_circuity,
)
from pnorm.minkowski_fit import c_minkowski, fit_minkowski

K = 48
THETA = np.linspace(0.0, 2.0 * np.pi, K, endpoint=False)
DENSE = np.linspace(0.0, 2.0 * np.pi, 4001)


def axis_aligned_estimates(c_rays):
    p_mle, _ = mle_p_from_directional_circuities(c_rays[np.newaxis, :], THETA)
    ok = np.isfinite(c_rays)
    return (
        float(p_of_circuity(float(c_rays[ok].mean()))),
        float(p_of_median_circuity(float(np.median(c_rays[ok])))),
        float(p_mle[0]),
    )


def main():
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.0))

    ax = axes[0]
    for p, alpha, a, b, label in [
        (1.0, 0.0, 1.0, 1.0, "p=1, aligned"),
        (1.0, np.pi / 4, 1.0, 1.0, "p=1, rotated 45°"),
        (1.0, 0.0, 1.0, 0.7, "p=1, b/a=0.7"),
        (2.0, 0.0, 1.0, 1.0, "p=2 (Euclidean)"),
    ]:
        ax.plot(np.rad2deg(DENSE), c_minkowski(DENSE, p, alpha, a, b), label=label)
    ax.set_xlabel("bearing θ (deg)")
    ax.set_ylabel("directional circuity c(θ)")
    ax.set_title("(a) model family")
    ax.legend(fontsize=8)

    ax = axes[1]
    angles = np.linspace(0.0, 45.0, 19)
    rows = {"mean": [], "median": [], "MLE": [], "rotated fit": []}
    for deg in angles:
        c = c_minkowski(THETA, 1.0, alpha=np.deg2rad(deg))
        pm, pmed, pmle = axis_aligned_estimates(c)
        rows["mean"].append(pm)
        rows["median"].append(pmed)
        rows["MLE"].append(pmle)
        rows["rotated fit"].append(float(fit_minkowski(c[np.newaxis, :], THETA).p[0]))
    for label, ys in rows.items():
        ax.plot(angles, ys, marker=".", label=label)
    ax.axhline(1.0, color="k", lw=0.6, ls=":")
    ax.set_xlabel("grid rotation α (deg)")
    ax.set_ylabel("estimated p (true p = 1)")
    ax.set_title("(b) pure rotation")
    ax.legend(fontsize=8)

    ax = axes[2]
    kappas = np.linspace(1.0, 0.55, 19)
    rows = {"mean": [], "median": [], "MLE": [], "rotated fit": []}
    for kappa in kappas:
        c = c_minkowski(THETA, 1.0, b=kappa)
        pm, pmed, pmle = axis_aligned_estimates(c)
        rows["mean"].append(pm)
        rows["median"].append(pmed)
        rows["MLE"].append(pmle)
        rows["rotated fit"].append(float(fit_minkowski(c[np.newaxis, :], THETA).p[0]))
    for label, ys in rows.items():
        ax.plot(kappas, ys, marker=".", label=label)
    ax.axhline(1.0, color="k", lw=0.6, ls=":")
    ax.invert_xaxis()
    ax.set_xlabel("anisotropy κ = b/a (true p = 1)")
    ax.set_ylabel("estimated p")
    ax.set_title("(c) pure anisotropy")
    ax.legend(fontsize=8)

    fig.tight_layout()
    out = "docs/figures/minkowski_fit_bias.png"
    fig.savefig(out, dpi=160)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
