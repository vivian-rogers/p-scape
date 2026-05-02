"""Geographic helpers.

The module keeps a single active UTM projection.  Default is UTM 14N (Austin).
Switch via ``set_utm_epsg(epsg)`` or, more commonly, ``pnorm.cities.use_city(key)``.

``AUSTIN_BBOX`` and the ``to_utm`` / ``to_lonlat`` helpers stay backwards-compatible —
existing code that doesn't know about cities continues to work in Austin's zone.
"""

from __future__ import annotations

from pyproj import Transformer

AUSTIN_BBOX = (-97.88, 30.12, -97.58, 30.50)

_DEFAULT_UTM_EPSG = 32614  # UTM 14N — Austin
_state = {"epsg": _DEFAULT_UTM_EPSG}
_transformers: dict[int, tuple[Transformer, Transformer]] = {}


def _make(epsg: int) -> tuple[Transformer, Transformer]:
    return (
        Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True),
        Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True),
    )


def _get() -> tuple[Transformer, Transformer]:
    epsg = _state["epsg"]
    if epsg not in _transformers:
        _transformers[epsg] = _make(epsg)
    return _transformers[epsg]


def set_utm_epsg(epsg: int) -> None:
    _state["epsg"] = int(epsg)


def current_utm_epsg() -> int:
    return _state["epsg"]


def to_utm(lon, lat):
    return _get()[0].transform(lon, lat)


def to_lonlat(x, y):
    return _get()[1].transform(x, y)
