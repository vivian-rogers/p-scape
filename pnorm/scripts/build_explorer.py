"""Build a single self-contained HTML 'explorer' that lets the user pick city,
mode (walking / driving), and ring radius.

Loads every available `<city>_<mode>_r<R>.npz` (and the `_foot_core_` legacy
naming for cities that predate the unified-bbox convention), resolves p(C)
per cell, embeds everything inline as JSON, and emits a Leaflet page with
three dropdowns + a big colorbar labeled "P".
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pnorm.cities import CITIES
from pnorm.lp_inversion import p_of_circuity

OUT = Path("data/explorer.html")

# Per-city filename pattern. Some early runs used "_foot_core_" instead of
# "_foot_" because they predate the unified-bbox convention.
FOOT_RADII = [200, 400, 800]
CAR_RADII = [1000, 2000, 3000]

CITY_FOOT_PREFIX = {
    "austin":    "austin_foot",
    "nyc":       "nyc_foot",
    "dc":        "dc_foot",
    "houston":   "houston_foot_core",
    "sf":        "sf_foot_core",
    "barcelona": "barcelona_foot_core",
}
CITY_CAR_PREFIX = {
    "austin":    "austin_car",
    "nyc":       "nyc_car",
    "dc":        "dc_car",
    "houston":   "houston_car",
    "sf":        "sf_car",
    "barcelona": "barcelona_car",
}

PRETTY = {
    "austin": "Austin, TX",
    "nyc": "New York City",
    "dc": "Washington, DC",
    "houston": "Houston, TX",
    "sf": "San Francisco",
    "barcelona": "Barcelona",
}


def load_layer(npz_path: Path) -> dict:
    d = np.load(npz_path)
    ll = d["lonlat"]
    c = d["mean_circuity"]
    spacing = float(d["spacing_m"])
    radius = float(d["radius_m"])
    ok = np.isfinite(c)
    p = p_of_circuity(c[ok])
    valid_idx = np.where(ok)[0]
    cells = []
    for j, i in enumerate(valid_idx):
        cells.append([round(float(ll[i, 1]), 5),  # lat
                      round(float(ll[i, 0]), 5),  # lng
                      round(float(p[j]), 3)])     # p
    return {
        "spacing_m": spacing,
        "radius_m": radius,
        "cells": cells,
    }


def main() -> None:
    layers: dict[str, dict] = {}
    cities_present = []

    for city, prefix in CITY_FOOT_PREFIX.items():
        any_layer = False
        for r in FOOT_RADII:
            path = Path("data") / f"{prefix}_r{r}.npz"
            if path.exists():
                key = f"{city}__foot__{r}"
                layers[key] = load_layer(path)
                any_layer = True
        if any_layer:
            cities_present.append(city)
        for r in CAR_RADII:
            prefix_car = CITY_CAR_PREFIX.get(city)
            if prefix_car:
                path = Path("data") / f"{prefix_car}_r{r}.npz"
                if path.exists():
                    key = f"{city}__car__{r}"
                    layers[key] = load_layer(path)
                    if not any_layer:
                        cities_present.append(city)
                        any_layer = True

    cities_present = sorted(set(cities_present), key=lambda c: list(CITY_FOOT_PREFIX).index(c))

    # Quick reporting + per-city radii lists
    radii_for = {}
    for city in cities_present:
        for mode in ("foot", "car"):
            rs = sorted(int(k.split("__")[2]) for k in layers if k.startswith(f"{city}__{mode}__"))
            if rs:
                radii_for[f"{city}__{mode}"] = rs

    for k, l in layers.items():
        ps = [c[2] for c in l["cells"]]
        med = float(np.median(ps)) if ps else float("nan")
        print(f"  {k:<28}  cells={len(l['cells']):>6}  spacing={l['spacing_m']:.0f}m  median_p={med:.3f}")

    centers = {
        city: {
            "lat": CITIES[city].center[0],
            "lng": CITIES[city].center[1],
            "zoom": CITIES[city].default_zoom,
        }
        for city in cities_present
    }

    payload = {
        "layers": layers,
        "centers": centers,
        "pretty": {c: PRETTY[c] for c in cities_present},
        "cities": cities_present,
        "radii": radii_for,
    }
    payload_json = json.dumps(payload, separators=(",", ":"))

    html = HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    size_mb = OUT.stat().st_size / 1024 / 1024
    total_cells = sum(len(l["cells"]) for l in layers.values())
    print(f"\nwrote {OUT}  ({size_mb:.1f} MB, {len(layers)} layers, {total_cells:,} cells)")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Effective P-norm explorer</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
  html, body { margin: 0; padding: 0; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  #wrap { display: grid; grid-template-rows: auto 1fr; height: 100vh; }
  #header {
    background: #fafafa;
    border-bottom: 1px solid #ddd;
    padding: 14px 22px;
    display: flex;
    align-items: center;
    gap: 22px;
    flex-wrap: wrap;
  }
  #header h1 { margin: 0; font-size: 20px; }
  #header .formula {
    font-family: "Times New Roman", serif;
    color: #333;
    font-size: 16px;
  }
  #header .formula .var { font-style: italic; }
  #controls { display: flex; align-items: center; gap: 8px; }
  #controls label { font-size: 13px; color: #555; }
  #controls select {
    font-size: 14px;
    padding: 4px 8px;
    border: 1px solid #bbb;
    border-radius: 4px;
    background: white;
  }
  #map { width: 100%; height: 100%; }
  #info {
    position: absolute;
    bottom: 24px;
    left: 16px;
    z-index: 999;
    background: rgba(255,255,255,0.94);
    padding: 12px 14px;
    border-radius: 6px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.18);
    font-size: 13px;
  }
  #info .stat-row { margin: 2px 0; }
  #legend {
    position: absolute;
    right: 16px;
    bottom: 24px;
    z-index: 999;
    background: rgba(255,255,255,0.94);
    padding: 14px 18px 14px 18px;
    border-radius: 6px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.18);
    font-size: 13px;
    width: 350px;
  }
  #legend .label-P {
    text-align: center;
    font-weight: bold;
    font-size: 18px;
    font-style: italic;
    margin-bottom: 6px;
    font-family: "Times New Roman", serif;
  }
  #legend canvas { display: block; width: 100%; height: 24px; }
  #legend .ticks {
    position: relative;
    height: 22px;
    font-size: 12px;
    color: #444;
    margin-top: 4px;
  }
  #legend .ticks span {
    position: absolute;
    transform: translateX(-50%);
    white-space: nowrap;
  }
  #legend .endpoints {
    display: flex;
    justify-content: space-between;
    color: #888;
    font-size: 11px;
    margin-top: 6px;
  }
</style>
</head>
<body>
<div id="wrap">
  <div id="header">
    <h1>Effective <em>P</em>-norm of urban networks</h1>
    <div class="formula">
      &#x2016;<span class="var">v</span>&#x2016;<sub><span class="var">p</span></sub> =
      (|<span class="var">x</span>|<sup><span class="var">p</span></sup> +
      |<span class="var">y</span>|<sup><span class="var">p</span></sup>)<sup>1/<span class="var">p</span></sup>
      &nbsp; — &nbsp;
      <span class="var">p</span>=1 is taxicab (Manhattan grid),
      <span class="var">p</span>=2 is Euclidean (straight-line).
    </div>
    <div id="controls">
      <label for="cityPick">City</label>
      <select id="cityPick"></select>
      <label for="modePick">Mode</label>
      <select id="modePick">
        <option value="foot">walking</option>
        <option value="car">driving</option>
      </select>
      <label for="radiusPick">Radius</label>
      <select id="radiusPick"></select>
      <label for="opacityPick">Opacity</label>
      <input id="opacityPick" type="range" min="0" max="100" step="1" value="65" style="width: 110px;">
      <span id="opacityVal" style="font-size: 12px; color: #555; min-width: 32px; display: inline-block;">65%</span>
    </div>
  </div>
  <div id="map"></div>
  <div id="info">Loading…</div>
  <div id="zoomWarn" style="display:none; position:absolute; top:90px; left:50%; transform:translateX(-50%); z-index:999; background: rgba(255, 244, 200, 0.95); padding: 8px 14px; border-radius: 4px; box-shadow: 0 1px 6px rgba(0,0,0,0.18); font-size: 13px; color: #553;">
    Zoom in for crisp rendering — hexes are sub-pixel at this zoom level.
  </div>
  <div id="legend">
    <div class="label-P">P</div>
    <canvas id="legendCanvas" width="320" height="24"></canvas>
    <div class="ticks">
      <span style="left:0%">0</span>
      <span style="left:25%">0.5</span>
      <span style="left:50%">1</span>
      <span style="left:75%">1.5</span>
      <span style="left:100%">2</span>
    </div>
    <div class="endpoints">
      <span>sprawl / cul-de-sac</span>
      <span>taxicab</span>
      <span>Euclidean</span>
    </div>
  </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
  const PAYLOAD = __PAYLOAD__;
  const VMIN = 0, VMAX = 2;

  const PALETTE = [
    [0.00, [77, 0, 0]],
    [0.10, [163, 0, 0]],
    [0.20, [250, 0, 0]],
    [0.30, [255, 81, 81]],
    [0.40, [255, 168, 168]],
    [0.50, [255, 255, 255]],
    [0.60, [168, 168, 255]],
    [0.70, [82, 81, 255]],
    [0.80, [0, 0, 250]],
    [0.90, [0, 0, 163]],
    [1.00, [0, 0, 77]],
  ];

  function paletteAt(t) {
    t = Math.max(0, Math.min(1, t));
    for (let i = 1; i < PALETTE.length; i++) {
      if (t <= PALETTE[i][0]) {
        const [t0, c0] = PALETTE[i - 1];
        const [t1, c1] = PALETTE[i];
        const f = (t - t0) / (t1 - t0);
        const r = Math.round(c0[0] + f * (c1[0] - c0[0]));
        const g = Math.round(c0[1] + f * (c1[1] - c0[1]));
        const b = Math.round(c0[2] + f * (c1[2] - c0[2]));
        return `rgb(${r},${g},${b})`;
      }
    }
    return `rgb(${PALETTE[PALETTE.length - 1][1].join(',')})`;
  }

  function pColor(p) {
    if (!isFinite(p)) return '#888';
    return paletteAt((p - VMIN) / (VMAX - VMIN));
  }

  (function paintLegend() {
    const canvas = document.getElementById('legendCanvas');
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    for (let x = 0; x < w; x++) {
      ctx.fillStyle = paletteAt(x / (w - 1));
      ctx.fillRect(x, 0, 1, h);
    }
    ctx.strokeStyle = '#444';
    ctx.lineWidth = 1;
    [0, 0.25, 0.5, 0.75, 1].forEach(t => {
      const x = Math.round(t * (w - 1)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, 6);
      ctx.moveTo(x, h - 6);
      ctx.lineTo(x, h);
      ctx.stroke();
    });
  })();

  // Tiny overlap to close sub-pixel rasterization gaps. With the shared-canvas
  // CSS-opacity approach below, overlaps don't compound, so this is purely a
  // gap-closing knob — bump it up if you still see seams.
  const HEX_OVERLAP = 1.015;

  function hexLatLngs(lat, lng, spacingM) {
    const r = spacingM / Math.sqrt(3) * HEX_OVERLAP;
    const cosLat = Math.cos(lat * Math.PI / 180);
    const dLat = r / 111320;
    const dLng = r / (111320 * cosLat);
    const out = [];
    for (let k = 0; k < 6; k++) {
      const a = Math.PI / 6 + k * Math.PI / 3;
      out.push([lat + dLat * Math.sin(a), lng + dLng * Math.cos(a)]);
    }
    return out;
  }

  // Below this many pixels per hex, individual cells rasterize to <2 px and we
  // get moiré. Suggest the user zoom in.
  const MIN_PIXELS_PER_HEX = 4;
  function pixelsPerHex(lat, spacingM) {
    const z = map.getZoom();
    const metersPerPixel = 156543.03392 * Math.cos(lat * Math.PI / 180) / Math.pow(2, z);
    return spacingM / metersPerPixel;
  }

  const map = L.map('map', { preferCanvas: true }).setView([39, -77], 4);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  // One shared canvas renderer for all hexes. We draw each polygon at
  // fillOpacity=1 (no per-cell alpha) and then dim the whole canvas via
  // CSS opacity on its DOM container. This avoids the "vein" pattern that
  // appears when translucent neighbors overlap and compound their alpha.
  const hexRenderer = L.canvas({ padding: 0.1 });
  hexRenderer.addTo(map);

  const cityPick = document.getElementById('cityPick');
  const modePick = document.getElementById('modePick');
  const radiusPick = document.getElementById('radiusPick');
  const opacityPick = document.getElementById('opacityPick');
  const opacityVal = document.getElementById('opacityVal');

  PAYLOAD.cities.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = PAYLOAD.pretty[c] || c;
    cityPick.appendChild(opt);
  });

  function radiiFor(city, mode) {
    return PAYLOAD.radii[city + '__' + mode] || [];
  }

  function defaultRadius(city, mode) {
    const rs = radiiFor(city, mode);
    if (!rs.length) return null;
    // prefer the middle radius
    return rs[Math.floor(rs.length / 2)];
  }

  function refreshRadiusDropdown(preserveR) {
    const city = cityPick.value;
    const mode = modePick.value;
    const rs = radiiFor(city, mode);
    radiusPick.innerHTML = '';
    rs.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r;
      opt.textContent = (mode === 'foot') ? `${r} m` : `${(r / 1000).toFixed(0)} km`;
      radiusPick.appendChild(opt);
    });
    let pick = preserveR && rs.includes(preserveR) ? preserveR : defaultRadius(city, mode);
    if (pick != null) radiusPick.value = pick;
    radiusPick.disabled = rs.length === 0;
  }

  let layerGroup = null;

  function renderLayer() {
    if (layerGroup) { map.removeLayer(layerGroup); layerGroup = null; }
    const city = cityPick.value;
    const mode = modePick.value;
    const r = parseInt(radiusPick.value, 10);
    const center = PAYLOAD.centers[city];
    if (center) map.setView([center.lat, center.lng], center.zoom);
    const info = document.getElementById('info');

    const key = city + '__' + mode + '__' + r;
    const data = PAYLOAD.layers[key];
    if (!data) {
      info.innerHTML = `<b>${PAYLOAD.pretty[city] || city}</b><br>${mode === 'foot' ? 'walking' : 'driving'} not available for this radius.`;
      return;
    }

    const cells = data.cells;
    const spacing = data.spacing_m;
    const radius = data.radius_m;
    const polys = [];
    let pVals = [];
    for (let i = 0; i < cells.length; i++) {
      const [lat, lng, p] = cells[i];
      const verts = hexLatLngs(lat, lng, spacing);
      polys.push(L.polygon(verts, {
        renderer: hexRenderer,
        stroke: false,
        fillColor: pColor(p),
        fillOpacity: 1,
      }).bindTooltip(`p = ${p.toFixed(2)}`, { sticky: true }));
      pVals.push(p);
    }
    layerGroup = L.layerGroup(polys).addTo(map);
    applyOpacity();

    // Zoom-out warning. If hexes are smaller than ~4 px the rasterization
    // can produce moiré that no amount of overlap fixes; suggest zooming in.
    const ppx = pixelsPerHex(cells[0][0], spacing);
    if (ppx < MIN_PIXELS_PER_HEX) {
      const warn = document.getElementById('zoomWarn');
      if (warn) warn.style.display = 'block';
    } else {
      const warn = document.getElementById('zoomWarn');
      if (warn) warn.style.display = 'none';
    }

    pVals.sort((a, b) => a - b);
    const median = pVals[Math.floor(pVals.length / 2)];
    const p10 = pVals[Math.floor(pVals.length * 0.1)];
    const p90 = pVals[Math.floor(pVals.length * 0.9)];
    info.innerHTML =
      `<b>${PAYLOAD.pretty[city] || city}</b> &middot; ${mode === 'foot' ? 'walking' : 'driving'}<br>` +
      `<span class="stat-row">ring radius <b>${(radius >= 1000 ? (radius / 1000).toFixed(1) + ' km' : radius.toFixed(0) + ' m')}</b>, ${cells.length.toLocaleString()} cells</span><br>` +
      `<span class="stat-row">median p = <b>${median.toFixed(3)}</b></span><br>` +
      `<span class="stat-row">p10 / p90 = ${p10.toFixed(2)} / ${p90.toFixed(2)}</span>`;
  }

  cityPick.addEventListener('change', () => {
    const prev = parseInt(radiusPick.value, 10);
    refreshRadiusDropdown(prev);
    renderLayer();
  });
  modePick.addEventListener('change', () => {
    refreshRadiusDropdown();
    renderLayer();
  });
  radiusPick.addEventListener('change', renderLayer);

  function applyOpacity() {
    const o = parseInt(opacityPick.value, 10) / 100;
    opacityVal.textContent = `${opacityPick.value}%`;
    const c = hexRenderer._container;
    if (c) c.style.opacity = String(o);
  }
  opacityPick.addEventListener('input', applyOpacity);

  map.on('zoomend', () => {
    // refresh the zoom warning without re-rendering the layer
    const city = cityPick.value, mode = modePick.value, r = parseInt(radiusPick.value, 10);
    const data = PAYLOAD.layers[city + '__' + mode + '__' + r];
    if (!data || !data.cells.length) return;
    const ppx = pixelsPerHex(data.cells[0][0], data.spacing_m);
    document.getElementById('zoomWarn').style.display = ppx < MIN_PIXELS_PER_HEX ? 'block' : 'none';
  });

  refreshRadiusDropdown();
  renderLayer();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
