# NDVI WebApp

The NDVI WebApp is a lightweight demonstration of how to calculate and visualize Normalized Difference Vegetation Index (NDVI) imagery in a browser. A small Flask backend generates synthetic Sentinel-2 bands, computes NDVI, and serves static overlays that the Leaflet-based frontend can display on top of a basemap.

## Features

- **Automated NDVI generation** – The backend simulates downloading Sentinel-2 red (B04) and near-infrared (B08) bands and computes NDVI rasters from them.
- **GeoTIFF + PNG outputs** – Each NDVI request produces both a GeoTIFF asset for analysis and a contrast-stretched PNG overlay suitable for web maps.
- **Simple frontend viewer** – The frontend (vanilla HTML/JS) lets you draw an area of interest, submit it to the backend, and display the returned NDVI overlay.
- **CORS-enabled API** – Flask responses are CORS-enabled so the frontend can be served from the filesystem or another static host.

## Repository layout

```
.
├── backend
│   ├── app.py            # Flask application exposing the /ndvi API
│   ├── ndvi_utils.py     # NDVI computation helpers
│   ├── sentinel_api.py   # Synthetic Sentinel-2 band generator
│   └── static/ndvi       # Generated NDVI assets (created at runtime)
└── frontend
    └── index.html        # Leaflet application for map interaction
```

## Prerequisites

- Python 3.9+
- `pip` for dependency management

The project does not require external Sentinel APIs. The backend produces deterministic synthetic scenes for demonstration purposes.

## Getting started

1. **Create and activate a virtual environment (recommended):**

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **Install backend dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Flask server:**

   ```bash
   flask --app app run
   ```

   By default the server listens on `http://127.0.0.1:5000`.

4. **Open the frontend:**

   - Option A: open `frontend/index.html` directly in your browser.
   - Option B: serve the `frontend/` directory with any static file server (e.g. `python -m http.server 8080`).

## API overview

### `POST /ndvi`

Request body:

```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[lon, lat], ...]]
  }
}
```

Response payload:

```json
{
  "status": "success",
  "ndvi_file": "static/ndvi/ndvi_<id>.tif",
  "ndvi_overlay_url": "/static/ndvi/ndvi_<id>.png",
  "bounds": [south, west, north, east]
}
```

- `ndvi_file` points to the generated GeoTIFF.
- `ndvi_overlay_url` is a static URL for the PNG overlay that can be added to Leaflet as an image overlay using the provided bounds.

If the backend encounters an error, the response has `status: "error"` and a descriptive `message`.

## Development tips

- Generated NDVI assets live in `backend/static/ndvi`. Clean this directory between runs if you want to remove stale rasters.
- Adjust the synthetic band characteristics in `backend/sentinel_api.py` to experiment with different NDVI patterns.
- To inspect raw NDVI arrays or metadata, open the generated GeoTIFFs with tools such as QGIS, `rasterio`, or `gdalinfo`.

## Testing the endpoint manually

With the server running, you can trigger an NDVI calculation from the command line:

```bash
curl -X POST http://127.0.0.1:5000/ndvi \
  -H "Content-Type: application/json" \
  -d '{
        "geometry": {
          "type": "Polygon",
          "coordinates": [[
            [-105.00341892242432, 39.75383843460583],
            [-105.0008225440979, 39.751891803969535],
            [-104.99820470809937, 39.75361210428282],
            [-105.000821, 39.755099],
            [-105.00341892242432, 39.75383843460583]
          ]]
        }
      }'
```

The response JSON includes the overlay URL that the frontend expects.

## License

This project is provided as-is for demonstration purposes. Adapt it freely for your own NDVI or remote sensing prototypes.
