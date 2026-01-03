// Global variables
let map;
let heatLayer;
let currentCategoria = 'excelencia_integral';

// Initialize map when tab is shown
document.getElementById('mapa-tab')?.addEventListener('shown.bs.tab', function () {
    if (!map) {
        initMap();
    } else {
        map.invalidateSize();
    }
});

// Initialize Leaflet map
function initMap() {
    // Center on Colombia
    map = L.map('mapHeatmap').setView([4.5709, -74.2973], 6);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18,
        minZoom: 5
    }).addTo(map);

    // Load initial data
    loadHeatmapData();
}

// Load heatmap data
async function loadHeatmapData() {
    const ano = document.getElementById('mapaAno').value;
    const categoria = document.getElementById('mapaCategoria').value;
    const departamento = document.getElementById('mapaDepartamento').value;
    const municipio = document.getElementById('mapaMunicipio').value;

    // Show loading
    document.getElementById('mapLoading').style.display = 'block';
    document.getElementById('mapHeatmap').style.opacity = '0.5';

    try {
        const params = new URLSearchParams({ ano, categoria });
        if (departamento) params.append('departamento', departamento);
        if (municipio) params.append('municipio', municipio);

        const response = await fetch(`/icfes/api/mapa-estudiantes-heatmap/?${params}`);
        const data = await response.json();

        if (data.error) {
            throw new Error(data.details || data.error);
        }

        // Remove existing heat layer
        if (heatLayer) {
            map.removeLayer(heatLayer);
        }

        // Create new heat layer
        const gradient = getGradientForCategoria(categoria);
        heatLayer = L.heatLayer(data.data, {
            radius: 25,
            blur: 15,
            maxZoom: 17,
            max: data.stats.max_concentracion,
            gradient: gradient
        }).addTo(map);

        // Update statistics
        updateStats(data.stats);

        // Update legend
        updateLegend(categoria);

        // Zoom to data if available
        if (data.data.length > 0) {
            const bounds = L.latLngBounds(data.data.map(d => [d[0], d[1]]));
            map.fitBounds(bounds, { padding: [50, 50] });
        }

    } catch (error) {
        console.error('Error loading heatmap:', error);
        alert('Error al cargar el mapa: ' + error.message);
    } finally {
        document.getElementById('mapLoading').style.display = 'none';
        document.getElementById('mapHeatmap').style.opacity = '1';
    }
}

// Get gradient colors based on category
function getGradientForCategoria(categoria) {
    switch (categoria) {
        case 'excelencia_integral':
        case 'perfil_stem':
        case 'perfil_humanistico':
            return { 0.0: 'white', 0.5: 'yellow', 0.7: 'lime', 1.0: 'green' };
        case 'riesgo_alto':
            return { 0.0: 'white', 0.5: 'orange', 0.7: 'orangered', 1.0: 'red' };
        default:
            return { 0.0: 'white', 0.5: 'lightblue', 0.7: 'blue', 1.0: 'darkblue' };
    }
}

// Update statistics
function updateStats(stats) {
    document.getElementById('statTotalEstudiantes').textContent = stats.total_estudiantes.toLocaleString();
    document.getElementById('statMaxConcentracion').textContent = stats.max_concentracion.toLocaleString();
    document.getElementById('statZonasAltas').textContent = stats.zonas_alta_concentracion.toLocaleString();
    document.getElementById('statTotalCeldas').textContent = stats.total_celdas.toLocaleString();
}

// Update legend text
function updateLegend(categoria) {
    const legends = {
        'excelencia_integral': 'Las zonas más <strong class="text-success">intensas</strong> indican mayor concentración de estudiantes con <strong>excelencia integral</strong> (nivel 4 en todas las materias).',
        'perfil_stem': 'Las zonas más <strong class="text-success">intensas</strong> indican mayor concentración de estudiantes con <strong>perfil STEM avanzado</strong> (nivel 4 en Matemáticas y Ciencias).',
        'perfil_humanistico': 'Las zonas más <strong class="text-success">intensas</strong> indican mayor concentración de estudiantes con <strong>perfil humanístico avanzado</strong> (nivel 4 en Lectura y Sociales).',
        'riesgo_alto': 'Las zonas más <strong class="text-danger">intensas</strong> indican mayor concentración de estudiantes en <strong>riesgo alto</strong> (nivel 1 en 2+ materias).',
        'todos': 'Las zonas más <strong class="text-primary">intensas</strong> indican mayor concentración de <strong>todos los estudiantes</strong>.'
    };

    document.getElementById('mapaLeyenda').innerHTML = legends[categoria] || '';
}

// Event listeners
document.getElementById('mapaCategoria')?.addEventListener('change', loadHeatmapData);
document.getElementById('mapaAno')?.addEventListener('change', loadHeatmapData);
document.getElementById('mapaDepartamento')?.addEventListener('change', loadHeatmapData);
document.getElementById('mapaMunicipio')?.addEventListener('change', loadHeatmapData);
