from pathlib import Path
from urllib.parse import urlparse

import pytest

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import backend.app as backend_app


@pytest.fixture()
def client():
    return backend_app.app.test_client()


def _cleanup_generated_files(*paths: Path):
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            continue


def test_ndvi_endpoint_serves_generated_overlay(client):
    geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [10.1815, 36.8065],
                [10.1915, 36.8065],
                [10.1915, 36.8165],
                [10.1815, 36.8165],
                [10.1815, 36.8065],
            ]
        ],
    }

    response = client.post("/ndvi", json={"geometry": geometry})
    assert response.status_code == 200

    data = response.get_json()
    assert data["status"] == "success"

    overlay_url = data["ndvi_overlay_url"]
    parsed = urlparse(overlay_url)
    assert parsed.path.startswith("/static/ndvi/")

    overlay_response = client.get(parsed.path)
    assert overlay_response.status_code == 200
    assert overlay_response.data  # file should contain data

    png_name = Path(parsed.path).name
    png_path = Path(backend_app.NDVI_DIR, png_name)
    geotiff_relative = data["ndvi_file"]
    assert geotiff_relative.startswith("static/ndvi/")
    geotiff_name = Path(geotiff_relative).name
    geotiff_path = Path(backend_app.NDVI_DIR, geotiff_name)

    try:
        assert png_path.exists()
        assert geotiff_path.exists()
    finally:
        _cleanup_generated_files(png_path, geotiff_path)


def test_chrome_devtools_manifest_available(client):
    response = client.get("/.well-known/appspecific/com.chrome.devtools.json")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["app_name"] == "ndvi-webapp"
    assert payload["targets"], "Expected at least one debugging target"

    first_target = payload["targets"][0]
    assert first_target["type"] == "web"
    assert first_target["title"]
    assert first_target["url"].endswith("/")
