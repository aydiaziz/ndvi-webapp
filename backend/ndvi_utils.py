import uuid
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


def _stretch_ndvi_for_display(
    ndvi: np.ndarray,
    valid_mask: np.ndarray,
    lower_percentile: float = 2.0,
    upper_percentile: float = 98.0,
) -> np.ndarray:
    """Enhance NDVI contrast by stretching values between selected percentiles.

    Invalid pixels are returned as ``np.nan`` so the caller can decide how to
    represent them (e.g. transparent/black).
    """

    stretched = np.full_like(ndvi, np.nan, dtype=np.float32)

    valid_values = ndvi[valid_mask]
    if valid_values.size == 0:
        return stretched

    low, high = np.nanpercentile(valid_values, [lower_percentile, upper_percentile])

    if not np.isfinite(low) or not np.isfinite(high) or np.isclose(low, high):
        # Fallback to the canonical NDVI range.
        low, high = -1.0, 1.0

    # Stretch and clip to the [-1, 1] range.
    stretched_values = ((valid_values - low) / (high - low)) * 2.0 - 1.0
    np.clip(stretched_values, -1.0, 1.0, out=stretched_values)

    stretched[valid_mask] = stretched_values
    return stretched


def _apply_color_map(stretched_ndvi: np.ndarray) -> np.ndarray:
    """Map stretched NDVI values (-1, 1) to an RGB false-colour representation."""

    # Normalise to the [0, 1] range for interpolation.
    normalised = np.clip((stretched_ndvi + 1.0) / 2.0, 0.0, 1.0)

    color_positions = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float32)
    color_table = np.array(
        [
            (165, 0, 38),      # Very low / barren
            (215, 48, 39),     # Low vegetation
            (254, 224, 139),   # Neutral
            (102, 189, 99),    # Moderate vegetation
            (26, 152, 80),     # Dense vegetation
        ],
        dtype=np.float32,
    )

    flat = np.nan_to_num(normalised.ravel(), nan=-1.0)
    r = np.interp(flat, color_positions, color_table[:, 0])
    g = np.interp(flat, color_positions, color_table[:, 1])
    b = np.interp(flat, color_positions, color_table[:, 2])

    color_image = np.stack((r, g, b), axis=-1).reshape((*stretched_ndvi.shape, 3))
    color_image = color_image.astype(np.uint8)

    invalid_mask = np.isnan(stretched_ndvi)
    if np.any(invalid_mask):
        color_image[invalid_mask] = (0, 0, 0)

    return color_image


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

        stretched_ndvi = _stretch_ndvi_for_display(ndvi, valid_mask)
        color_data = _apply_color_map(stretched_ndvi)

        Image.fromarray(color_data, mode="RGB").save(png_path)

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

    if stats["min"] is not None and stats["max"] is not None:
        print(
            f"NDVI statistics — min: {stats['min']:.4f}, max: {stats['max']:.4f}"
        )
    else:
        print("NDVI statistics — no valid pixels found.")

    return {
        "geotiff_path": geotiff_path.as_posix(),
        "png_path": png_path.as_posix(),
        "bounds": [bounds.bottom, bounds.left, bounds.top, bounds.right],
        "statistics": stats,
    }
