const map = L.map('map').setView([36.8065, 10.1815], 11);
const resultPanel = document.getElementById('ndvi-result');

function showStatus(message, isError = false) {
  if (!resultPanel) {
    return;
  }

  resultPanel.classList.toggle('error', isError);
  resultPanel.innerHTML = message;
}

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

let ndviOverlay = null;

const drawControl = new L.Control.Draw({
  draw: {
    polygon: true,
    rectangle: true,
    polyline: false,
    circle: false,
    marker: false,
    circlemarker: false
  },
  edit: {
    featureGroup: drawnItems,
    edit: false
  }
});
map.addControl(drawControl);

map.on(L.Draw.Event.CREATED, function (event) {
  drawnItems.clearLayers();
  if (ndviOverlay) {
    map.removeLayer(ndviOverlay);
    ndviOverlay = null;
  }

  const layer = event.layer;
  drawnItems.addLayer(layer);
  const geojson = layer.toGeoJSON();

  showStatus('Calcul du NDVI en cours, merci de patienter…');

  fetch("http://localhost:5000/ndvi", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ geometry: geojson.geometry })
  })
    .then(response => response.json())
    .then(data => {
      if (data.status !== "success") {
        throw new Error(data.message || "NDVI processing failed");
      }

      const [south, west, north, east] = data.bounds;
      const imageBounds = [
        [south, west],
        [north, east]
      ];

      ndviOverlay = L.imageOverlay(data.ndvi_overlay_url, imageBounds, { opacity: 0.7 });
      ndviOverlay.addTo(map);
      map.fitBounds(imageBounds);

      const downloadUrl = data.ndvi_file_url || data.ndvi_overlay_url;
      const downloadText = downloadUrl
        ? `<a href="${downloadUrl}" target="_blank" rel="noopener">Télécharger le GeoTIFF</a>`
        : data.ndvi_file;
      showStatus(`NDVI prêt ! ${downloadText}`);
    })
    .catch(error => {
      showStatus(`Erreur : ${error.message}`, true);
    });
});
