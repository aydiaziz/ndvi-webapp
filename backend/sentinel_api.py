"""Utility helpers to simulate Sentinel-2 band downloads.

For the prototype we generate synthetic GeoTIFF files that roughly match the
extent of the geometry sent by the frontend. The NDVI computation then works on
these generated rasters just like it would on real Sentinel-2 bands.
"""

from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import rasterio
from rasterio.transform import from_bounds


def _geometry_bounds(geometry: dict) -> Tuple[float, float, float, float]:
    """Extract the bounding box from a GeoJSON geometry."""

    def _flatten(coords: Iterable) -> Iterable[Tuple[float, float]]:
        for coord in coords:
            if isinstance(coord[0], (list, tuple)):
                yield from _flatten(coord)
            else:
                yield tuple(coord)

    coords = list(_flatten(geometry["coordinates"]))
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return min(lons), min(lats), max(lons), max(lats)


def _create_band(path: Path, transform, width: int, height: int, base_value: float):
    noise = np.random.default_rng(seed=42).normal(loc=0.0, scale=0.02, size=(height, width))
    gradient = np.linspace(0, 0.1, width)
    band = base_value + gradient + noise
    band = np.clip(band, 0, 1)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=rasterio.float32,
        transform=transform,
        crs="EPSG:4326",
    ) as dst:
        dst.write(band.astype(rasterio.float32), 1)


def download_sentinel_bands(geometry):
    """Simulate downloading Sentinel-2 red (B04) and NIR (B08) bands."""

    minx, miny, maxx, maxy = _geometry_bounds(geometry)
    if maxx == minx:
        minx -= 0.0005
        maxx += 0.0005
    if maxy == miny:
        miny -= 0.0005
        maxy += 0.0005

    width = height = 200
    transform = from_bounds(minx, miny, maxx, maxy, width, height)

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    red_path = data_dir / "B04_simulated.tif"
    nir_path = data_dir / "B08_simulated.tif"

    _create_band(red_path, transform, width, height, base_value=0.2)
    _create_band(nir_path, transform, width, height, base_value=0.5)

    return str(red_path), str(nir_path)
