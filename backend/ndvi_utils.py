import numpy as np
import rasterio

def compute_ndvi(red_path, nir_path):
    with rasterio.open(red_path) as red_src, rasterio.open(nir_path) as nir_src:
        red = red_src.read(1).astype(float)
        nir = nir_src.read(1).astype(float)
        ndvi = (nir - red) / (nir + red + 1e-6)

        meta = red_src.meta
        meta.update(dtype=rasterio.float32)

        output_path = "ndvi.tif"
        with rasterio.open(output_path, 'w', **meta) as dst:
            dst.write(ndvi.astype(rasterio.float32), 1)

    return output_path
