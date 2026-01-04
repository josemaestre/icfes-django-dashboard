// Global variables
let map;
let heatLayer;
let currentCategoria = 'excelencia_integral';

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
    const tipoUbicacion = document.getElementById('mapaTipoUbicacion').value;

    // Show loading
    document.getElementById('mapLoading').style.display = 'block';
    document.getElementById('mapHeatmap').style.opacity = '0.5';

    try {
        const params = new URLSearchParams({ ano, categoria, tipo_ubicacion: tipoUbicacion });
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
            radius: 35,
            blur: 20,
            maxZoom: 17,
            max: 1.0,  // Normalize to 1.0 for better visibility
            minOpacity: 0.3,
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
        case 'perfil_bilingue':
            return { 0.0: 'white', 0.5: 'gold', 0.7: 'orange', 1.0: 'darkorange' };
        case 'riesgo_alto':
        case 'critico_ingles':
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
        'perfil_bilingue': 'Las zonas más <strong class="text-warning">intensas</strong> indican mayor concentración de estudiantes con <strong>perfil bilingüe avanzado</strong> (nivel 4 en Inglés). Oportunidad para programas internacionales.',
        'riesgo_alto': 'Las zonas más <strong class="text-danger">intensas</strong> indican mayor concentración de estudiantes en <strong>riesgo alto</strong> (nivel 1 en 2+ materias).',
        'critico_ingles': 'Las zonas más <strong class="text-danger">intensas</strong> indican mayor concentración de estudiantes con <strong>necesidad crítica en Inglés</strong> (nivel 1). Oportunidad para academias de inglés.',
        'todos': 'Las zonas más <strong class="text-primary">intensas</strong> indican mayor concentración de <strong>todos los estudiantes</strong>.'
    };

    document.getElementById('mapaLeyenda').innerHTML = legends[categoria] || '';
}

// Event listeners
document.getElementById('mapaCategoria')?.addEventListener('change', loadHeatmapData);
document.getElementById('mapaAno')?.addEventListener('change', function () {
    loadDepartamentos();  // Reload departments when year changes
    loadHeatmapData();
});
document.getElementById('mapaDepartamento')?.addEventListener('change', function () {
    const departamento = this.value;
    if (departamento) {
        loadMunicipios(departamento);
    } else {
        // Clear municipalities when "Todos" is selected
        const municipioSelect = document.getElementById('mapaMunicipio');
        municipioSelect.innerHTML = '<option value="">Todos</option>';
    }
    loadHeatmapData();
});
document.getElementById('mapaMunicipio')?.addEventListener('change', loadHeatmapData);
document.getElementById('mapaTipoUbicacion')?.addEventListener('change', function () {
    const tipo = this.value;
    const helpTitle = document.getElementById('tipoUbicacionHelp');
    const helpDesc = document.getElementById('tipoUbicacionDesc');

    if (tipo === 'colegio') {
        helpTitle.textContent = '📍 Colegio:';
        helpDesc.textContent = 'Muestra dónde están ubicadas las instituciones educativas (oferta educativa)';
    } else {
        helpTitle.textContent = '🏠 Residencia:';
        helpDesc.textContent = 'Muestra dónde viven los estudiantes (demanda educativa)';
    }

    loadHeatmapData();
});

// Load departments from API
async function loadDepartamentos() {
    const ano = document.getElementById('mapaAno').value;

    try {
        const response = await fetch(`/icfes/api/mapa-departamentos/?ano=${ano}`);
        const data = await response.json();

        const select = document.getElementById('mapaDepartamento');
        select.innerHTML = '<option value="">Todos</option>';

        data.forEach(item => {
            const option = document.createElement('option');
            option.value = item.departamento;
            option.textContent = `${item.departamento} (${item.total_estudiantes.toLocaleString()})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading departments:', error);
    }
}

// Load municipalities from API
async function loadMunicipios(departamento) {
    const ano = document.getElementById('mapaAno').value;

    try {
        const response = await fetch(`/icfes/api/mapa-municipios/?ano=${ano}&departamento=${encodeURIComponent(departamento)}`);
        const data = await response.json();

        const select = document.getElementById('mapaMunicipio');
        select.innerHTML = '<option value="">Todos</option>';

        data.forEach(item => {
            const option = document.createElement('option');
            option.value = item.municipio;
            option.textContent = `${item.municipio} (${item.total_estudiantes.toLocaleString()})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading municipalities:', error);
    }
}

// Initialize departments when map tab is first shown
document.getElementById('mapa-tab')?.addEventListener('shown.bs.tab', function () {
    if (!map) {
        initMap();
        loadDepartamentos();  // Load departments on first load
    } else {
        map.invalidateSize();
    }
});
