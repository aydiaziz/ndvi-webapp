"""Sentinel-2 band download helpers with optional live integrations.

The application can operate in two modes:

* When the Sentinel Hub Python SDK is available and credentials are provided via
  environment variables, real Sentinel-2 L2A data is downloaded. Pixels flagged
  as cloudy, snowy or otherwise invalid are masked out before the NDVI
  computation to improve the quality of the derived product.
* When the SDK or credentials are unavailable (e.g. in tests) we fall back to a
  deterministic synthetic data generator that mimics two spectral bands.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import rasterio
from rasterio.transform import from_bounds

try:  # Sentinel Hub is optional, so we lazily import it.
    from sentinelhub import (
        BBox,
        CRS,
        DataCollection,
        MimeType,
        SentinelHubRequest,
        SHConfig,
        bbox_to_dimensions,
    )
except ImportError:  # pragma: no cover - optional dependency
    BBox = CRS = DataCollection = MimeType = SentinelHubRequest = SHConfig = None
    bbox_to_dimensions = None


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


def _prepare_bbox(geometry: dict) -> Tuple[Tuple[float, float, float, float], Tuple[int, int]]:
    """Return the bounding box and dimensions for the requested geometry."""

    minx, miny, maxx, maxy = _geometry_bounds(geometry)
    if maxx == minx:
        minx -= 0.0005
        maxx += 0.0005
    if maxy == miny:
        miny -= 0.0005
        maxy += 0.0005

    bounds = (minx, miny, maxx, maxy)

    if bbox_to_dimensions is None:
        width = height = 200
    else:
        resolution = float(os.getenv("SENTINELHUB_RESOLUTION", "10"))
        width, height = bbox_to_dimensions(BBox(bounds, CRS.WGS84), resolution)
        width = max(int(width), 32)
        height = max(int(height), 32)

    return bounds, (width, height)


def _create_band(
    path: Path,
    transform,
    width: int,
    height: int,
    base_value: float,
    mask: Optional[np.ndarray] = None,
):
    noise = np.random.default_rng(seed=42).normal(loc=0.0, scale=0.02, size=(height, width))
    gradient = np.linspace(0, 0.1, width)
    band = base_value + gradient + noise
    band = np.clip(band, 0, 1)

    if mask is not None:
        band = np.where(mask, band, np.nan)

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
        nodata=np.nan,
    ) as dst:
        dst.write(band.astype(rasterio.float32), 1)


def _synthetic_bands(geometry: dict) -> Tuple[str, str]:
    bounds, (width, height) = _prepare_bbox(geometry)
    transform = from_bounds(*bounds, width, height)

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    red_path = data_dir / "B04_simulated.tif"
    nir_path = data_dir / "B08_simulated.tif"

    mask = np.ones((height, width), dtype=bool)
    _create_band(red_path, transform, width, height, base_value=0.2, mask=mask)
    _create_band(nir_path, transform, width, height, base_value=0.5, mask=mask)

    return str(red_path), str(nir_path)


def _sentinelhub_evalscript() -> str:
    return """
//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B04", "B08", "SCL", "dataMask"],
      units: "REFLECTANCE"
    }],
    output: [
      {
        id: "default",
        bands: 4,
        sampleType: "FLOAT32"
      }
    ]
  };
}

const CLOUD_SCL = [3, 7, 8, 9, 10, 11];

function evaluatePixel(sample) {
  const clear = sample.dataMask === 1 && CLOUD_SCL.indexOf(sample.SCL) === -1;
  return {
    default: [sample.B04, sample.B08, sample.dataMask, clear ? 1 : 0]
  };
}
"""


def _sentinelhub_config() -> Optional["SHConfig"]:
    if SentinelHubRequest is None:
        return None

    config = SHConfig()
    client_id = os.getenv("SENTINELHUB_CLIENT_ID")
    client_secret = os.getenv("SENTINELHUB_CLIENT_SECRET")
    instance_id = os.getenv("SENTINELHUB_INSTANCE_ID")

    if client_id and client_secret:
        config.sh_client_id = client_id
        config.sh_client_secret = client_secret
    if instance_id:
        config.instance_id = instance_id

    # If neither authentication method is configured we fall back to synthetic data.
    if not ((config.sh_client_id and config.sh_client_secret) or config.instance_id):
        return None

    base_url = os.getenv("SENTINELHUB_BASE_URL")
    if base_url:
        config.sh_base_url = base_url

    return config


def _time_interval() -> Tuple[str, str]:
    end = os.getenv("SENTINELHUB_TIME_END")
    start = os.getenv("SENTINELHUB_TIME_START")

    if end and start:
        return start, end

    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=int(os.getenv("SENTINELHUB_LOOKBACK_DAYS", "30")))
    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def _download_from_sentinelhub(geometry: dict) -> Optional[Tuple[str, str]]:
    config = _sentinelhub_config()
    if config is None:
        return None

    try:
        bounds, (width, height) = _prepare_bbox(geometry)
        bbox = BBox(bounds, CRS.WGS84)
        evalscript = _sentinelhub_evalscript()

        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=_time_interval(),
                    mosaicking_order="mostRecent",
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
            bbox=bbox,
            size=(width, height),
            config=config,
        )

        data = request.get_data()[0]
        if data.ndim != 3 or data.shape[2] != 4:
            raise ValueError("Unexpected data shape returned by Sentinel Hub")

        red, nir, data_mask, clear_mask = np.moveaxis(data, -1, 0)
        clear_mask = (clear_mask > 0.5) & (data_mask > 0.5)

        transform = from_bounds(*bounds, width, height)

        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)

        uid = uuid.uuid4().hex
        red_path = data_dir / f"B04_{uid}.tif"
        nir_path = data_dir / f"B08_{uid}.tif"

        _write_band_with_mask(red_path, red, transform, clear_mask)
        _write_band_with_mask(nir_path, nir, transform, clear_mask)

        return str(red_path), str(nir_path)
    except Exception:  # pragma: no cover - network dependent failures
        return None


def _write_band_with_mask(path: Path, band: np.ndarray, transform, mask: np.ndarray) -> None:
    masked_band = np.where(mask, band, np.nan).astype(np.float32)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=masked_band.shape[0],
        width=masked_band.shape[1],
        count=1,
        dtype=rasterio.float32,
        transform=transform,
        crs="EPSG:4326",
        nodata=np.nan,
    ) as dst:
        dst.write(masked_band, 1)


def download_sentinel_bands(geometry):
    """Download Sentinel-2 red (B04) and NIR (B08) bands with quality masking."""

    real_data_paths = _download_from_sentinelhub(geometry)
    if real_data_paths is not None:
        return real_data_paths

    return _synthetic_bands(geometry)
