from __future__ import annotations

import asyncio
from typing import Iterable

import httpx
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


class AsyncOSRM:
    """Async OSRM client for K-different-origins Monte Carlo sampling.

    The K=48 per-ray-jittered scheme can't be batched into a single /table
    call (each ray has a unique source), so we fire K /route calls in
    parallel with a bounded concurrency semaphore. Use as an async context
    manager:

        async with AsyncOSRM("http://localhost:5001", concurrency=16) as osrm:
            results = await osrm.route_batch(origin_dest_pairs)

    Each routed pair returns (d_route_m, src_snapped_lonlat, dst_snapped_lonlat),
    or None if OSRM couldn't route it. Caller is responsible for snap-offset
    checks and bad-ray filtering.
    """

    def __init__(self, base_url: str = "http://localhost:5000",
                 timeout: float = 30.0, concurrency: int = 16):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.concurrency = concurrency
        self._client: httpx.AsyncClient | None = None
        self._sem: asyncio.Semaphore | None = None

    async def __aenter__(self):
        # HTTP/2 keep-alive matters here — without it every request opens a
        # fresh TCP socket and the loopback HTTP overhead dominates the
        # OSRM compute. httpx pools connections by default.
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(
                max_keepalive_connections=self.concurrency,
                max_connections=self.concurrency,
            ),
        )
        self._sem = asyncio.Semaphore(self.concurrency)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._client.aclose()
        self._client = None
        self._sem = None

    async def table(self, sources: list[tuple[float, float]],
                    destinations: list[tuple[float, float]]):
        """Async /table call. Returns (distances_K×M, src_snap_K×2, dst_snap_M×2) or None.

        OSRM's /table batches a shared multi-source / multi-destination graph
        traversal, which is dramatically cheaper than the same number of
        /route calls. For K-jittered Monte Carlo sampling we issue a single
        /table per tile with sources = K jittered origins and destinations =
        K ring-radius destinations, then read the diagonal — wastes 96% of
        the K² matrix but eliminates per-request HTTP+JSON overhead, which
        was the real bottleneck on a per-/route async implementation.
        """
        all_pts = list(sources) + list(destinations)
        coords = ";".join(f"{lon:.6f},{lat:.6f}" for lon, lat in all_pts)
        ns, nd = len(sources), len(destinations)
        params = {
            "annotations": "distance",
            "sources": ";".join(str(i) for i in range(ns)),
            "destinations": ";".join(str(i) for i in range(ns, ns + nd)),
        }
        url = f"{self.base}/table/v1/driving/{coords}"
        async with self._sem:
            try:
                r = await self._client.get(url, params=params)
                r.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException):
                return None
        js = r.json()
        if js.get("code") != "Ok":
            return None
        distances = np.asarray(js.get("distances", []), dtype=float)
        src_snap = np.asarray([w["location"] for w in js.get("sources", [])], dtype=float)
        dst_snap = np.asarray([w["location"] for w in js.get("destinations", [])], dtype=float)
        if distances.shape != (ns, nd) or src_snap.shape != (ns, 2) or dst_snap.shape != (nd, 2):
            return None
        return distances, src_snap, dst_snap
