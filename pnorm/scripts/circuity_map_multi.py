"""Multi-radius circuity map: one folium layer per ring radius, toggleable.

Fields:
    --field mean_circuity   raw d_route / d_euclid (default)
    --field mean_excess_m   raw extra distance, in meters
    --field effective_p     L^p shape parameter, derived from mean_circuity via
                            pnorm.lp_inversion.p_of_circuity (low p = sprawl-like).

Usage:
    uv run python scripts/circuity_map_multi.py \
        --npz data/grid_r1000.npz data/grid_r3000.npz data/grid_r5000.npz \
        --out data/effective_p_multi.html --field effective_p
"""

from __future__ import annotations

import argparse
from pathlib import Path

import branca.colormap as bcm
import folium
import numpy as np

from pnorm.cities import get_city
from pnorm.geo import set_utm_epsg, to_lonlat
from pnorm.lp_inversion import p_of_circuity


_INFERNO_STOPS = [
    "#000004", "#160b39", "#420a68", "#6a176e", "#932667",
    "#bc3754", "#dd513a", "#f37819", "#fca50a", "#f6d746", "#fcffa4",
]
_SPECTRAL_STOPS = [
    "#9e0142", "#d53e4f", "#f46d43", "#fdae61", "#fee08b", "#ffffbf",
    "#e6f598", "#abdda4", "#66c2a5", "#3288bd", "#5e4fa2",
]
# matplotlib `seismic` reversed: red at the low end, white in the middle, blue at the high end
_SEISMIC_R_STOPS = [
    "#4d0000", "#a30000", "#fa0000", "#ff5151", "#ffa8a8",
    "#ffffff",
    "#a8a8ff", "#5251ff", "#0000fa", "#0000a3", "#00004d",
]


def hex_polygon_latlon(cx_utm, cy_utm, spacing_m):
    r = spacing_m / np.sqrt(3)
    verts = []
    for k in range(6):
        a = np.pi / 6 + k * np.pi / 3
        x = cx_utm + r * np.cos(a)
        y = cy_utm + r * np.sin(a)
        lon, lat = to_lonlat(x, y)
        verts.append((float(lat), float(lon)))
    return verts


def make_cmap(field, vmin, vmax, name="inferno"):
    """Build a Branca colormap.

    Convention across palettes: cells where the network is "good" (high p,
    low circuity) should land on the cool/dark end. We flip per-palette to
    keep that invariant.
    """
    if name == "spectral":
        stops = _SPECTRAL_STOPS
        if field != "effective_p":
            stops = list(reversed(stops))
    elif name == "seismic_r":
        # red at vmin, blue at vmax — natural alignment with effective_p
        stops = _SEISMIC_R_STOPS
        if field != "effective_p":
            stops = list(reversed(stops))
    else:
        stops = _INFERNO_STOPS
        if field == "effective_p":
            stops = list(reversed(stops))
    return bcm.LinearColormap(stops, vmin=vmin, vmax=vmax)


def get_field_values(data, field):
    if field == "effective_p":
        return p_of_circuity(data["mean_circuity"])
    return data[field]


def field_caption(field, vmin, vmax):
    if field == "effective_p":
        return (
            f"Effective L^p exponent  (low = sprawl, ~1 = grid, ~2 = Euclidean)  "
            f"— range [{vmin:.2f}, {vmax:.2f}]"
        )
    if field == "mean_circuity":
        return f"Mean circuity  (d_route / d_euclid)  — range [{vmin:.2f}, {vmax:.2f}]"
    if field == "mean_excess_m":
        return f"Mean excess distance (m)  — range [{vmin:.0f}, {vmax:.0f}]"
    return field


def add_layer(m, npz_path, cmap, vmin, vmax, field, show=False):
    data = np.load(npz_path)
    xy = data["xy_utm"]
    lonlat = data["lonlat"]
    spacing = float(data["spacing_m"])
    radius = float(data["radius_m"])
    if "utm_epsg" in data.files:
        set_utm_epsg(int(data["utm_epsg"]))
    vals = get_field_values(data, field)
    p_vals = vals if field == "effective_p" else p_of_circuity(data["mean_circuity"])

    name = f"r = {radius / 1000:.1f} km"
    fg = folium.FeatureGroup(name=name, show=show)

    n_ok = 0
    for i in range(len(xy)):
        v = float(vals[i])
        if not np.isfinite(v):
            continue
        n_ok += 1
        verts = hex_polygon_latlon(xy[i, 0], xy[i, 1], spacing)
        v_c = max(vmin, min(vmax, v))
        p_i = float(p_vals[i]) if np.isfinite(p_vals[i]) else float("nan")
        tip = (
            f"<b>r={radius / 1000:.1f} km</b><br>"
            f"effective p {p_i:.2f}<br>"
            f"circuity {data['mean_circuity'][i]:.3f}<br>"
            f"excess {data['mean_excess_m'][i]:.0f} m<br>"
            f"n {int(data['n_valid'][i])}<br>"
            f"({lonlat[i, 0]:.4f}, {lonlat[i, 1]:.4f})"
        )
        folium.Polygon(
            locations=verts,
            color=None,
            weight=0,
            fill=True,
            fill_color=cmap(v_c),
            fill_opacity=0.6,
            tooltip=tip,
        ).add_to(fg)

    fg.add_to(m)
    return name, n_ok, radius


def main(npz_paths, out_html, field, vmin, vmax, zoom, center, cmap_name="inferno"):
    all_vals = []
    all_ll = []
    for p in npz_paths:
        d = np.load(p)
        v = get_field_values(d, field)
        all_vals.append(v[np.isfinite(v)])
        all_ll.append(d["lonlat"])
    flat = np.concatenate(all_vals)
    if vmin is None:
        vmin = float(np.nanpercentile(flat, 5))
    if vmax is None:
        vmax = float(np.nanpercentile(flat, 95))

    if center is None:
        ll = np.vstack(all_ll)
        center = (float(np.nanmean(ll[:, 1])), float(np.nanmean(ll[:, 0])))

    m = folium.Map(
        location=list(center),
        zoom_start=zoom,
        tiles="CartoDB positron",
        control_scale=True,
    )
    folium.TileLayer("OpenStreetMap", name="OSM", overlay=False, control=True).add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Dark", overlay=False, control=True).add_to(m)

    cmap = make_cmap(field, vmin, vmax, name=cmap_name)
    cmap.caption = field_caption(field, vmin, vmax)

    summary = []
    for i, p in enumerate(npz_paths):
        show = (i == 1) if len(npz_paths) >= 2 else True
        name, n_ok, radius = add_layer(m, p, cmap, vmin, vmax, field, show=show)
        summary.append(f"{name}: {n_ok} cells")

    cmap.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)

    title = {
        "effective_p": "Austin effective L^p — bright = sprawl (low p), dark = Euclidean (~p=2)",
        "mean_circuity": "Austin circuity",
        "mean_excess_m": "Austin excess distance",
    }.get(field, field)
    header = (
        "<div style=\"position: fixed; top: 10px; left: 60px; z-index:9999;"
        " background: rgba(255,255,255,0.85); padding: 8px 12px;"
        " font: 13px/1.3 -apple-system, sans-serif; border-radius: 4px;"
        " box-shadow: 0 1px 4px rgba(0,0,0,0.2)\">"
        f"<b>{title}</b> — toggle radii at top-right<br>"
        f"{' · '.join(summary)}"
        "</div>"
    )
    m.get_root().html.add_child(folium.Element(header))

    out = Path(out_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out))
    print(f"saved {out}  ({' · '.join(summary)})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", nargs="+", required=True)
    ap.add_argument("--out", default="data/circuity_multi.html")
    ap.add_argument("--field", default="mean_circuity",
                    choices=["mean_circuity", "mean_excess_m", "effective_p"])
    ap.add_argument("--vmin", type=float, default=None)
    ap.add_argument("--vmax", type=float, default=None)
    ap.add_argument("--zoom", type=int, default=None)
    ap.add_argument("--center", default=None,
                    help="lat,lon (overrides --city default)")
    ap.add_argument("--cmap", default="inferno", choices=["inferno", "spectral", "seismic_r"])
    ap.add_argument("--city", default=None,
                    help="city key for default UTM, center, zoom")
    a = ap.parse_args()

    if a.city:
        city = get_city(a.city)
        set_utm_epsg(city.utm_epsg)
        default_center = city.center
        default_zoom = city.default_zoom
    else:
        default_center = (30.2672, -97.7431)
        default_zoom = 12

    if a.center:
        center = tuple(float(x) for x in a.center.split(","))
    else:
        center = default_center
    zoom = a.zoom if a.zoom is not None else default_zoom

    main(a.npz, a.out, a.field, a.vmin, a.vmax, zoom, center, cmap_name=a.cmap)
