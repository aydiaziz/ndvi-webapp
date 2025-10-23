from pathlib import Path

from flask import Flask, jsonify, request, url_for

try:
    from .ndvi_utils import compute_ndvi
    from .sentinel_api import download_sentinel_bands
except ImportError:  # pragma: no cover - fallback when running as a script
    from ndvi_utils import compute_ndvi
    from sentinel_api import download_sentinel_bands

try:  # pragma: no cover - exercised indirectly in tests
    from flask_cors import CORS
except ModuleNotFoundError:  # pragma: no cover - fallback when flask-cors is missing
    def CORS(app, *_, **__):
        """Gracefully degrade when flask-cors is unavailable."""

        @app.after_request
        def add_cors_headers(response):  # pragma: no cover - simple fallback
            response.headers.setdefault("Access-Control-Allow-Origin", "*")
            response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
            response.headers.setdefault(
                "Access-Control-Allow-Methods", "GET,POST,OPTIONS"
            )
            return response

        @app.before_request
        def handle_preflight():  # pragma: no cover - simple fallback
            if request.method == "OPTIONS":
                response = app.make_default_options_response()
                return add_cors_headers(response)

        return app


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
NDVI_DIR = STATIC_DIR / "ndvi"

NDVI_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

CORS(app)


@app.route("/.well-known/appspecific/com.chrome.devtools.json", methods=["GET"])
def chrome_devtools_manifest():
    """Expose a Chrome DevTools manifest to satisfy discovery requests."""

    base_url = request.url_root.rstrip("/")

    return jsonify(
        {
            "app_name": "ndvi-webapp",
            "description": "Remote debugging configuration for the NDVI web application.",
            "targets": [
                {
                    "type": "web",
                    "title": "NDVI Web Application",
                    "url": f"{base_url}/",
                }
            ],
        }
    )


def _relative_to_static(path: Path) -> str:
    """Return a path relative to the Flask static directory."""

    try:
        return path.resolve().relative_to(STATIC_DIR.resolve()).as_posix()
    except ValueError:
        return path.name

@app.route('/ndvi', methods=['POST', 'OPTIONS'])
def ndvi():
    if request.method == "OPTIONS":  # pragma: no cover - handled by browser preflight
        return ("", 204)

    data = request.get_json(silent=True) or {}
    geometry = data.get("geometry")

    try:
        if not geometry:
            raise ValueError("Missing geometry in request body")

        red_band_path, nir_band_path = download_sentinel_bands(geometry)
        ndvi_result = compute_ndvi(
            red_band_path, nir_band_path, output_dir=NDVI_DIR
        )

        png_path = Path(ndvi_result["png_path"])
        geotiff_path = Path(ndvi_result["geotiff_path"])

        png_rel_path = _relative_to_static(png_path)
        geotiff_rel_path = _relative_to_static(geotiff_path)

        png_url = url_for("static", filename=png_rel_path, _external=True)
        geotiff_url = url_for("static", filename=geotiff_rel_path, _external=True)
        response_payload = {
            "status": "success",
            "ndvi_file": f"static/{geotiff_rel_path}",
            "ndvi_file_url": geotiff_url,
            "ndvi_overlay_url": png_url,
            "bounds": ndvi_result["bounds"],
        }

        return jsonify(response_payload)
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"status": "error", "message": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True)
