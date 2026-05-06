"""Build a single self-contained HTML 'explorer' that lets the user pick city
and mode (walking / driving) from one tab.

Reads the canonical `<city>_<mode>_r400.npz` (foot) and `<city>_<mode>_r2000.npz`
(car) per city, resolves p(C) per cell, embeds everything inline as JSON, and
emits a Leaflet page with two dropdowns + a big colorbar labeled "P".
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pnorm.cities import CITIES
from pnorm.lp_inversion import p_of_circuity

OUT = Path("data/explorer.html")

# Map (city, mode) → npz file. Some early cities used "_foot_core" suffix
# instead of "_foot" because they predate the unified-bbox convention.
DATASETS: dict[tuple[str, str], str] = {
    ("austin", "foot"):    "austin_foot_r400.npz",
    ("austin", "car"):     "austin_car_r2000.npz",
    ("nyc", "foot"):       "nyc_foot_r400.npz",
    ("nyc", "car"):        "nyc_car_r2000.npz",
    ("dc", "foot"):        "dc_foot_r400.npz",
    ("dc", "car"):         "dc_car_r2000.npz",
    ("houston", "foot"):   "houston_foot_core_r400.npz",
    ("houston", "car"):    "houston_car_r2000.npz",
    ("sf", "foot"):        "sf_foot_core_r400.npz",
    ("sf", "car"):         "sf_car_r2000.npz",
    ("barcelona", "foot"): "barcelona_foot_core_r400.npz",
    ("barcelona", "car"):  "barcelona_car_r2000.npz",
    ("venice", "foot"):    "venice_foot_r400.npz",
}

PRETTY = {
    "austin": "Austin, TX",
    "nyc": "New York City",
    "dc": "Washington, DC",
    "houston": "Houston, TX",
    "sf": "San Francisco",
    "barcelona": "Barcelona",
    "venice": "Venice",
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
    summary = []
    for (city, mode), fname in DATASETS.items():
        path = Path("data") / fname
        if not path.exists():
            print(f"  skip: {path} (not found)")
            continue
        layer = load_layer(path)
        layers[f"{city}__{mode}"] = layer
        ps = [c[2] for c in layer["cells"]]
        summary.append((city, mode, len(ps), float(np.median(ps)) if ps else float("nan")))
        print(f"  {city:<10} {mode:<5} cells={len(layer['cells']):>6}  spacing={layer['spacing_m']:.0f}m  median_p={float(np.median(ps)):.3f}")

    cities_present = sorted({c for (c, _) in DATASETS if any(k.startswith(c + "__") for k in layers)})
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
    }
    payload_json = json.dumps(payload, separators=(",", ":"))

    html = HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"\nwrote {OUT}  ({size_mb:.1f} MB, {sum(len(l['cells']) for l in layers.values())} cells)")


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
    </div>
  </div>
  <div id="map"></div>
  <div id="info">Loading…</div>
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
  // matplotlib-style seismic reversed: red at low, white in middle, blue at high.
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

  // Draw the legend gradient.
  (function paintLegend() {
    const canvas = document.getElementById('legendCanvas');
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    for (let x = 0; x < w; x++) {
      ctx.fillStyle = paletteAt(x / (w - 1));
      ctx.fillRect(x, 0, 1, h);
    }
    // overlay tick marks
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

  function hexLatLngs(lat, lng, spacingM) {
    // pointy-top hex: r = spacing / sqrt(3), corner angles π/6 + k·π/3
    const r = spacingM / Math.sqrt(3);
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

  // Build the map.
  const map = L.map('map', { preferCanvas: true }).setView([39, -77], 4);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(map);

  // Populate city dropdown.
  const cityPick = document.getElementById('cityPick');
  PAYLOAD.cities.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = PAYLOAD.pretty[c] || c;
    cityPick.appendChild(opt);
  });

  let layerGroup = null;

  function renderLayer(city, mode) {
    if (layerGroup) { map.removeLayer(layerGroup); layerGroup = null; }
    const key = city + '__' + mode;
    const data = PAYLOAD.layers[key];
    const center = PAYLOAD.centers[city];
    map.setView([center.lat, center.lng], center.zoom);
    const info = document.getElementById('info');

    if (!data) {
      info.innerHTML = `<b>${PAYLOAD.pretty[city] || city}</b><br>${mode === 'foot' ? 'walking' : 'driving'} data not available.`;
      return;
    }

    const cells = data.cells;
    const spacing = data.spacing_m;
    const radius = data.radius_m;
    const polys = [];
    let pSum = 0, pCount = 0, pVals = [];
    for (let i = 0; i < cells.length; i++) {
      const [lat, lng, p] = cells[i];
      const verts = hexLatLngs(lat, lng, spacing);
      polys.push(L.polygon(verts, {
        color: '#222',
        weight: 0,
        fillColor: pColor(p),
        fillOpacity: 0.65,
      }).bindTooltip(`p = ${p.toFixed(2)}`, { sticky: true }));
      pSum += p;
      pCount += 1;
      pVals.push(p);
    }
    layerGroup = L.layerGroup(polys).addTo(map);

    pVals.sort((a, b) => a - b);
    const median = pVals[Math.floor(pVals.length / 2)];
    const p10 = pVals[Math.floor(pVals.length * 0.1)];
    const p90 = pVals[Math.floor(pVals.length * 0.9)];
    info.innerHTML =
      `<b>${PAYLOAD.pretty[city] || city}</b> &middot; ${mode === 'foot' ? 'walking' : 'driving'}<br>` +
      `<span class="stat-row">ring radius <b>${(radius / 1000).toFixed(1)} km</b>, ${cells.length.toLocaleString()} cells</span><br>` +
      `<span class="stat-row">median p = <b>${median.toFixed(3)}</b></span><br>` +
      `<span class="stat-row">p10 / p90 = ${p10.toFixed(2)} / ${p90.toFixed(2)}</span>`;
  }

  document.getElementById('cityPick').addEventListener('change', e => {
    renderLayer(e.target.value, document.getElementById('modePick').value);
  });
  document.getElementById('modePick').addEventListener('change', e => {
    renderLayer(document.getElementById('cityPick').value, e.target.value);
  });

  renderLayer(PAYLOAD.cities[0], 'foot');
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
