from pathlib import Path

from flask import Flask, jsonify, request, url_for

from ndvi_utils import compute_ndvi
from sentinel_api import download_sentinel_bands
from flask_cors import CORS



app = Flask(__name__)
CORS(app)

@app.route('/ndvi', methods=['POST'])
def ndvi():
    data = request.get_json(silent=True) or {}
    geometry = data.get("geometry")

    try:
        if not geometry:
            raise ValueError("Missing geometry in request body")

        red_band_path, nir_band_path = download_sentinel_bands(geometry)
        ndvi_result = compute_ndvi(red_band_path, nir_band_path)

        png_path = Path(ndvi_result["png_path"])
        png_url = url_for('static', filename=str(png_path.relative_to('static')))

        response_payload = {
            "status": "success",
            "ndvi_file": ndvi_result["geotiff_path"],
            "ndvi_overlay_url": png_url,
            "bounds": ndvi_result["bounds"],
        }

        return jsonify(response_payload)
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({"status": "error", "message": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True)
