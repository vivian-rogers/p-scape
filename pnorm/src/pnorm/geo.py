from pyproj import Transformer

AUSTIN_BBOX = (-98.00, 30.10, -97.55, 30.55)

_LL_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32614", always_xy=True)
_UTM_TO_LL = Transformer.from_crs("EPSG:32614", "EPSG:4326", always_xy=True)


def to_utm(lon, lat):
    return _LL_TO_UTM.transform(lon, lat)


def to_lonlat(x, y):
    return _UTM_TO_LL.transform(x, y)
