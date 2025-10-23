const map = L.map('map').setView([36.8065, 10.1815], 11);
const resultPanel = document.getElementById('ndvi-result');

function showStatus(message, isError = false) {
  if (!resultPanel) {
    return;
  }

  resultPanel.classList.toggle('error', isError);
  resultPanel.innerHTML = message;
}

function formatStat(value) {
  if (value === null || Number.isNaN(value)) {
    return 'N/A';
  }

  return Number.parseFloat(value).toFixed(3);
}

function renderStatistics(stats = {}) {
  const { min = null, max = null, mean = null } = stats;

  if (min === null && max === null && mean === null) {
    return '';
  }

  return `
    <section class="ndvi-stats" role="group" aria-label="Statistiques NDVI">
      <div><span class="label">Min</span><span class="value">${formatStat(min)}</span></div>
      <div><span class="label">Moyenne</span><span class="value">${formatStat(mean)}</span></div>
      <div><span class="label">Max</span><span class="value">${formatStat(max)}</span></div>
    </section>
  `;
}

function renderDownloadActions({ ndvi_file_url, ndvi_overlay_url, ndvi_file }) {
  const links = [];

  if (ndvi_file_url) {
    links.push(`
      <a href="${ndvi_file_url}" target="_blank" rel="noopener">
        Télécharger le GeoTIFF
      </a>
    `);
  }

  if (ndvi_overlay_url) {
    links.push(`
      <a href="${ndvi_overlay_url}" target="_blank" rel="noopener">
        Ouvrir la superposition PNG
      </a>
    `);
  }

  if (!links.length && ndvi_file) {
    return `<p class="ndvi-hint">Fichier NDVI : ${ndvi_file}</p>`;
  }

  if (!links.length) {
    return '';
  }

  const uniqueLinks = Array.from(new Set(links));

  return `
    <div class="ndvi-actions" role="group" aria-label="Actions NDVI">
      ${uniqueLinks.join('')}
    </div>
  `;
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

  showStatus(`
    <h2>Analyse NDVI en cours…</h2>
    <p>Nous récupérons les bandes Sentinel-2 et préparons le résultat. Cela peut
    prendre quelques instants.</p>
  `);

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

      const statsHtml = renderStatistics(data.statistics);
      const actionsHtml = renderDownloadActions(data);

      showStatus(`
        <h2>Analyse NDVI terminée ✅</h2>
        <p>La zone sélectionnée a été traitée avec succès. Vous pouvez télécharger les
        fichiers générés ou explorer la carte pour visualiser la superposition.</p>
        ${actionsHtml}
        ${statsHtml ? `<div class="ndvi-summary">${statsHtml}</div>` : ''}
      `);
    })
    .catch(error => {
      showStatus(`
        <h2>Analyse NDVI impossible ❌</h2>
        <p>${error.message}</p>
        <p class="ndvi-hint">Vérifiez votre connexion internet et assurez-vous que la
        zone tracée se trouve dans une région couverte par Sentinel-2.</p>
      `, true);
    });
});
