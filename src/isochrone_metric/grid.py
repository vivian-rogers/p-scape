"""Run the per-origin ellipse fit over a grid of points and persist results."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from pyproj import Transformer
from tqdm import tqdm

from .routing import fetch_isochrones
from .tensor import DEFAULT_PROJECTED_CRS, WGS84, LocalTensor, fit_local_tensor


@dataclass(frozen=True)
class GridResult:
    lat: float
    lon: float
    t_seconds: float
    g11: float
    g12: float
    g22: float
    fast_speed_mps: float
    slow_speed_mps: float
    anisotropy: float
    mean_speed_mps: float
    fast_axis_deg: float  # bearing of the fast (low-eigenvalue) axis, 0=East, CCW
    residual_rms: float
    error: str | None = None


def _result_from_tensor(lat: float, lon: float, lt: LocalTensor) -> GridResult:
    w, V = np.linalg.eigh(lt.g)  # ascending
    fast_axis = V[:, 0]
    fast_axis_deg = float(np.rad2deg(np.arctan2(fast_axis[1], fast_axis[0])))
    fast_speed = 1.0 / float(np.sqrt(w[0]))
    slow_speed = 1.0 / float(np.sqrt(w[1]))
    return GridResult(
        lat=lat,
        lon=lon,
        t_seconds=lt.t_seconds,
        g11=float(lt.g[0, 0]),
        g12=float(lt.g[0, 1]),
        g22=float(lt.g[1, 1]),
        fast_speed_mps=fast_speed,
        slow_speed_mps=slow_speed,
        anisotropy=float(lt.anisotropy),
        mean_speed_mps=float(lt.mean_speed),
        fast_axis_deg=fast_axis_deg,
        residual_rms=float(lt.residual_rms),
    )


def make_grid(bbox: tuple[float, float, float, float], n_lat: int, n_lon: int) -> list[tuple[float, float]]:
    """Uniform lat/lon grid inside (south, west, north, east). Returns list of (lat, lon)."""
    s, w, n, e = bbox
    lats = np.linspace(s, n, n_lat)
    lons = np.linspace(w, e, n_lon)
    return [(float(la), float(lo)) for la in lats for lo in lons]


def _process_one(
    lat: float,
    lon: float,
    minutes: float,
    costing: str,
    url: str,
) -> GridResult:
    try:
        isos = fetch_isochrones(lat, lon, [minutes], costing=costing, url=url)
        if not isos:
            return GridResult(lat, lon, minutes * 60, *([float("nan")] * 9), error="no isochrone returned")
        lt = fit_local_tensor(isos[0].polygon, lat, lon, minutes * 60)
        return _result_from_tensor(lat, lon, lt)
    except Exception as exc:  # noqa: BLE001
        return GridResult(lat, lon, minutes * 60, *([float("nan")] * 9), error=f"{type(exc).__name__}: {exc}")


def run_grid(
    origins: Iterable[tuple[float, float]],
    minutes: float = 10.0,
    *,
    costing: str = "auto",
    url: str = "http://localhost:8002",
    max_workers: int = 8,
    progress: bool = True,
) -> list[GridResult]:
    """Fetch + fit for every origin. Concurrent against the local Valhalla."""
    origins = list(origins)
    results: list[GridResult] = [None] * len(origins)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {
            ex.submit(_process_one, la, lo, minutes, costing, url): i
            for i, (la, lo) in enumerate(origins)
        }
        it = as_completed(futs)
        if progress:
            it = tqdm(it, total=len(futs), desc="fit")
        for fut in it:
            i = futs[fut]
            results[i] = fut.result()
    return results


def save_results_jsonl(results: list[GridResult], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for r in results:
            fh.write(json.dumps(asdict(r)) + "\n")


def project_origins_to_xy(
    results: list[GridResult], crs: str = DEFAULT_PROJECTED_CRS
) -> np.ndarray:
    """(N, 2) array of origin coords in the projected CRS."""
    tr = Transformer.from_crs(WGS84, crs, always_xy=True)
    lons = np.array([r.lon for r in results])
    lats = np.array([r.lat for r in results])
    xs, ys = tr.transform(lons, lats)
    return np.column_stack([xs, ys])
