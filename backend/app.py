from flask import Flask, request, jsonify
from ndvi_utils import compute_ndvi
from sentinel_api import download_sentinel_bands

app = Flask(__name__)

@app.route('/ndvi', methods=['POST'])
def ndvi():
    data = request.get_json()
    geojson = data.get("geometry")

    try:
        red_band_path, nir_band_path = download_sentinel_bands(geojson)
        ndvi_output = compute_ndvi(red_band_path, nir_band_path)
        return jsonify({"status": "success", "ndvi_file": ndvi_output})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
