from __future__ import annotations

import numpy as np
import requests


class OSRM:
    def __init__(self, base_url: str = "http://localhost:5000", timeout: float = 30.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def _coords(self, pts):
        return ";".join(f"{lon:.6f},{lat:.6f}" for lon, lat in pts)

    def route(self, src, dst) -> float:
        url = f"{self.base}/route/v1/driving/{src[0]:.6f},{src[1]:.6f};{dst[0]:.6f},{dst[1]:.6f}"
        r = requests.get(url, params={"overview": "false"}, timeout=self.timeout)
        r.raise_for_status()
        js = r.json()
        if js.get("code") != "Ok":
            raise RuntimeError(f"OSRM error: {js.get('code')} {js.get('message', '')}")
        return float(js["routes"][0]["duration"])

    def table(self, sources, destinations=None, annotations="duration", return_snapped=False):
        """Return duration matrix.

        - annotations='duration,distance' → returns (durations, distances)
        - return_snapped=True → additionally returns (src_snapped_lonlat, dst_snapped_lonlat)
        """
        if destinations is None:
            coords = self._coords(sources)
            params = {"annotations": annotations}
        else:
            coords = self._coords(list(sources) + list(destinations))
            ns, nd = len(sources), len(destinations)
            params = {
                "annotations": annotations,
                "sources": ";".join(str(i) for i in range(ns)),
                "destinations": ";".join(str(i) for i in range(ns, ns + nd)),
            }
        r = requests.get(f"{self.base}/table/v1/driving/{coords}", params=params, timeout=self.timeout)
        r.raise_for_status()
        js = r.json()
        if js.get("code") != "Ok":
            raise RuntimeError(f"OSRM error: {js.get('code')} {js.get('message', '')}")

        if "," in annotations:
            result = (
                np.asarray(js["durations"], dtype=float),
                np.asarray(js["distances"], dtype=float),
            )
        else:
            key = "distances" if annotations == "distance" else "durations"
            result = np.asarray(js[key], dtype=float)

        if return_snapped:
            src_snap = np.asarray([w["location"] for w in js["sources"]], dtype=float)
            dst_snap = np.asarray([w["location"] for w in js["destinations"]], dtype=float)
            return (*result, src_snap, dst_snap) if isinstance(result, tuple) else (result, src_snap, dst_snap)
        return result
