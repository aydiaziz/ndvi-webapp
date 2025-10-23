const map = L.map('map').setView([36.8, 10.2], 10);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

const drawControl = new L.Control.Draw({
  edit: { featureGroup: drawnItems }
});
map.addControl(drawControl);

map.on(L.Draw.Event.CREATED, function (e) {
  const layer = e.layer;
  drawnItems.addLayer(layer);
  const geojson = layer.toGeoJSON();

  fetch("/ndvi", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ geometry: geojson.geometry })
  })
  .then(res => res.json())
  .then(data => {
    if (data.ndvi_file) {
      alert("NDVI processed: " + data.ndvi_file);
    } else {
      alert("Error: " + data.message);
    }
  });
});
