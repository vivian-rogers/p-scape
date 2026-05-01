"""Render a circuity-grid npz as an interactive folium map over OSM tiles."""

from __future__ import annotations

import argparse
from pathlib import Path

import branca.colormap as cm
import folium
import numpy as np

from pnorm.geo import to_lonlat


def hex_polygon_lonlat(cx_utm, cy_utm, spacing_m):
    """Return list of (lat, lon) vertices for a pointy-top hex at (cx, cy) UTM."""
    r = spacing_m / np.sqrt(3)
    verts = []
    for k in range(6):
        a = np.pi / 6 + k * np.pi / 3
        x = cx_utm + r * np.cos(a)
        y = cy_utm + r * np.sin(a)
        lon, lat = to_lonlat(x, y)
        verts.append((float(lat), float(lon)))
    return verts


def main(npz_path, out_html, field, vmin, vmax):
    data = np.load(npz_path)
    xy = data["xy_utm"]
    lonlat = data["lonlat"]
    spacing = float(data["spacing_m"])
    radius = float(data["radius_m"])
    vals = data[field]
    ok = np.isfinite(vals)

    if vmin is None:
        vmin = float(np.nanpercentile(vals, 5))
    if vmax is None:
        vmax = float(np.nanpercentile(vals, 95))

    center_lat = float(np.nanmean(lonlat[:, 1]))
    center_lon = float(np.nanmean(lonlat[:, 0]))

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="CartoDB positron",
        control_scale=True,
    )
    folium.TileLayer("OpenStreetMap", name="OSM").add_to(m)

    cmap = cm.linear.plasma.scale(vmin, vmax)
    label = {
        "mean_circuity": f"Mean circuity (ring r={radius/1000:.1f} km)",
        "mean_excess_m": f"Mean excess distance (m, ring r={radius/1000:.1f} km)",
    }.get(field, field)
    cmap.caption = label

    fg = folium.FeatureGroup(name=label).add_to(m)

    for i in range(len(xy)):
        if not ok[i]:
            continue
        v = float(vals[i])
        verts = hex_polygon_lonlat(xy[i, 0], xy[i, 1], spacing)
        v_clamped = max(vmin, min(vmax, v))
        tip = (
            f"<b>circuity</b> {data['mean_circuity'][i]:.3f}<br>"
            f"<b>excess</b> {data['mean_excess_m'][i]:.0f} m<br>"
            f"<b>n</b> {int(data['n_valid'][i])}<br>"
            f"lon,lat: {lonlat[i,0]:.4f}, {lonlat[i,1]:.4f}"
        )
        folium.Polygon(
            locations=verts,
            color=None,
            weight=0,
            fill=True,
            fill_color=cmap(v_clamped),
            fill_opacity=0.55,
            tooltip=tip,
        ).add_to(fg)

    cmap.add_to(m)
    folium.LayerControl().add_to(m)

    out = Path(out_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out))
    print(f"saved {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="data/circuity_grid.npz")
    ap.add_argument("--out", default="data/circuity_map.html")
    ap.add_argument("--field", default="mean_circuity",
                    choices=["mean_circuity", "mean_excess_m"])
    ap.add_argument("--vmin", type=float, default=None)
    ap.add_argument("--vmax", type=float, default=None)
    a = ap.parse_args()
    main(a.npz, a.out, a.field, a.vmin, a.vmax)
