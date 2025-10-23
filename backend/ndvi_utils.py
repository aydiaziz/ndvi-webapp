import uuid
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


def _scale_to_byte(array: np.ndarray) -> np.ndarray:
    """Scale NDVI values (-1, 1) to the 0-255 byte range."""
    scaled = ((array + 1) / 2.0) * 255.0
    return np.clip(scaled, 0, 255).astype(np.uint8)


def compute_ndvi(red_path, nir_path, output_dir="static/ndvi"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src:
        red = red_src.read(1).astype(np.float32)
        nir = nir_src.read(1).astype(np.float32)

        denominator = nir + red
        valid_mask = denominator != 0

        ndvi = np.full_like(red, np.nan, dtype=np.float32)
        np.divide(nir - red, denominator, out=ndvi, where=valid_mask)
        np.clip(ndvi, -1.0, 1.0, out=ndvi)

        meta = red_src.meta.copy()
        meta.update(dtype=rasterio.float32, count=1, nodata=-9999.0)

        uid = uuid.uuid4().hex
        geotiff_path = (output_dir / f"ndvi_{uid}.tif").resolve()
        png_path = (output_dir / f"ndvi_{uid}.png").resolve()

        with rasterio.open(geotiff_path, "w", **meta) as dst:
            dst.write(np.where(np.isnan(ndvi), -9999.0, ndvi).astype(rasterio.float32), 1)

        png_data = _scale_to_byte(np.nan_to_num(ndvi, nan=-1.0))
        Image.fromarray(png_data, mode="L").save(png_path)

        bounds = red_src.bounds

        if np.any(valid_mask):
            valid_values = ndvi[valid_mask]
            stats = {
                "min": float(np.nanmin(valid_values)),
                "max": float(np.nanmax(valid_values)),
                "mean": float(np.nanmean(valid_values)),
            }
        else:
            stats = {"min": None, "max": None, "mean": None}

    return {
        "geotiff_path": geotiff_path.as_posix(),
        "png_path": png_path.as_posix(),
        "bounds": [bounds.bottom, bounds.left, bounds.top, bounds.right],
        "statistics": stats,
    }
