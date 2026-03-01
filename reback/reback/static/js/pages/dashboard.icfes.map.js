// Global variables
let map;
let heatLayer;
let colegiosLayer = null;   // LayerGroup for school markers
let currentCategoria = 'excelencia_integral';
let currentMapMode = 'heatmap'; // 'heatmap' | 'colegios'

// Initialize Leaflet map
function initMap() {
    map = L.map('mapHeatmap').setView([4.5709, -74.2973], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18,
        minZoom: 5
    }).addTo(map);
    loadHeatmapData();
}

// ── Mode toggle (event delegation — works regardless of DOM timing) ───────────
document.addEventListener('change', function (e) {
    if (!e.target || e.target.name !== 'mapaMode') return;

    currentMapMode = e.target.value;
    const isColegios = currentMapMode === 'colegios';

    const filtrosHeatmap  = document.getElementById('filtrosHeatmap');
    const filtrosColegios = document.getElementById('filtrosColegios');
    const statsHeatmap    = document.getElementById('statsHeatmap');
    const alertaHeatmap   = document.getElementById('alertaHeatmap');
    const tituloTexto     = document.getElementById('mapaTituloTexto');

    if (filtrosHeatmap)  filtrosHeatmap.style.display  = isColegios ? 'none' : '';
    if (filtrosColegios) filtrosColegios.style.display = isColegios ? '' : 'none';
    if (statsHeatmap)    statsHeatmap.style.display    = isColegios ? 'none' : '';
    if (alertaHeatmap)   alertaHeatmap.style.display   = isColegios ? 'none' : '';
    if (tituloTexto)     tituloTexto.textContent       = isColegios
        ? 'Mapa de Colegios — Inteligencia por Capas'
        : 'Mapa de Concentración de Estudiantes';

    if (!map) return; // Map not initialized yet (tab not shown)

    if (isColegios) {
        if (heatLayer) { map.removeLayer(heatLayer); heatLayer = null; }
        loadColegiosMap();
    } else {
        if (colegiosLayer) { map.removeLayer(colegiosLayer); colegiosLayer = null; }
        loadHeatmapData();
    }
});

// ── School marker map ─────────────────────────────────────────────────────────
const CAPA_CONFIG = {
    rendimiento: {
        label: 'Color por <strong>puntaje global</strong>: 🟢 ≥300 · 🟡 250-300 · 🔴 &lt;250',
        color: c => c.puntaje >= 300 ? '#198754' : c.puntaje >= 250 ? '#ffc107' : '#dc3545',
        value: c => c.puntaje,
        fmt: c => `Puntaje: <strong>${c.puntaje}</strong> | Ranking: #${(c.ranking || '—').toLocaleString()}`
    },
    riesgo: {
        label: 'Color por <strong>nivel de riesgo ML</strong>: 🔴 Alto · 🟡 Medio · 🟢 Bajo',
        color: c => c.nivel_riesgo === 'Alto' ? '#dc3545' : c.nivel_riesgo === 'Medio' ? '#ffc107' : '#198754',
        value: c => c.prob_declive || 0,
        fmt: c => `Riesgo: <strong>${c.nivel_riesgo || 'N/D'}</strong> | Prob. declive: ${c.prob_declive != null ? c.prob_declive + '%' : '—'}`
    },
    potencial: {
        label: 'Color por <strong>potencial contextual ML</strong>: 🟢 Excepcional/Por encima · 🟡 Esperado · 🔴 Bajo/En riesgo',
        color: c => ['Excepcional','Por encima'].includes(c.potencial) ? '#0d9488'
                  : c.potencial === 'Esperado' ? '#6c757d'
                  : c.potencial ? '#fd7e14' : '#adb5bd',
        value: c => 1,
        fmt: c => `Potencial: <strong>${c.potencial || 'N/D'}</strong>`
    },
    ingles: {
        label: 'Color por <strong>% estudiantes en B1+</strong>: 🟢 ≥20% · 🟡 10-20% · 🔴 &lt;10%',
        color: c => c.pct_b1 == null ? '#adb5bd' : c.pct_b1 >= 20 ? '#0891b2' : c.pct_b1 >= 10 ? '#fbbf24' : '#ef4444',
        value: c => c.pct_b1 || 0,
        fmt: c => `Inglés B1+: <strong>${c.pct_b1 != null ? c.pct_b1 + '%' : 'N/D'}</strong> | Puntaje inglés: ${c.avg_ingles || '—'}`
    }
};

async function loadColegiosMap() {
    if (!map) return;
    const ano   = document.getElementById('mapaColegiosAno')?.value || '2024';
    const capa  = document.getElementById('mapaCapa')?.value || 'rendimiento';
    const depto = document.getElementById('mapaColegiosDepto')?.value || '';

    document.getElementById('mapLoading').style.display = 'block';
    document.getElementById('mapHeatmap').style.opacity = '0.5';

    try {
        const params = new URLSearchParams({ ano, capa });
        if (depto) params.append('departamento', depto);
        const resp = await fetch(`/icfes/api/mapa-colegios/?${params}`);
        const json = await resp.json();
        const colegios = json.colegios || [];

        // Remove old layer
        if (colegiosLayer) { map.removeLayer(colegiosLayer); }
        colegiosLayer = L.layerGroup();
        const cfg = CAPA_CONFIG[capa];

        // Update legend
        document.getElementById('mapaColegiosLeyenda').innerHTML = cfg.label;

        // Stats counters
        let alto = 0, medio = 0, bajo = 0;

        colegios.forEach(c => {
            const color = cfg.color(c);
            const radius = Math.max(5, Math.min(12, 5 + Math.sqrt(c.estudiantes || 0) / 10));

            const marker = L.circleMarker([c.lat, c.lng], {
                radius,
                fillColor: color,
                color: '#fff',
                weight: 1,
                opacity: 0.9,
                fillOpacity: 0.8
            });

            // Popup
            const sectorBadge = c.sector === 'OFICIAL'
                ? '<span class="badge bg-primary">Oficial</span>'
                : '<span class="badge bg-warning text-dark">Privado</span>';

            marker.bindPopup(`
                <div style="min-width:200px;font-size:13px;">
                  <strong>${c.nombre}</strong><br>
                  <small class="text-muted">${c.municipio}, ${c.depto}</small>
                  ${sectorBadge}<br><hr class="my-1">
                  ${cfg.fmt(c)}<br>
                  <small>Estudiantes: ${(c.estudiantes || 0).toLocaleString()}</small><br>
                  <a href="/icfes/colegio/?sk=${c.sk}" target="_blank" class="btn btn-sm btn-outline-primary mt-1 w-100">
                    Ver detalle →
                  </a>
                </div>
            `, { maxWidth: 240 });

            marker.addTo(colegiosLayer);

            // Count for stats
            if (color === '#198754' || color === '#0d9488' || color === '#0891b2') alto++;
            else if (color === '#ffc107' || color === '#6c757d' || color === '#fbbf24') medio++;
            else bajo++;
        });

        colegiosLayer.addTo(map);

        // Update stats
        document.getElementById('statColegiosTotal').textContent = colegios.length.toLocaleString();
        document.getElementById('statColegiosTop').textContent   = alto.toLocaleString();
        document.getElementById('statColegiosMedio').textContent = medio.toLocaleString();
        document.getElementById('statColegiosBajo').textContent  = bajo.toLocaleString();

        // Fit map
        if (colegios.length > 0) {
            const bounds = L.latLngBounds(colegios.map(c => [c.lat, c.lng]));
            map.fitBounds(bounds, { padding: [40, 40] });
        }

    } catch (err) {
        console.error('Error loading colegios map:', err);
    } finally {
        document.getElementById('mapLoading').style.display = 'none';
        document.getElementById('mapHeatmap').style.opacity = '1';
    }
}

// Listeners for colegios mode filters
document.getElementById('mapaColegiosAno')?.addEventListener('change', () => { if (currentMapMode === 'colegios') loadColegiosMap(); });
document.getElementById('mapaCapa')?.addEventListener('change', () => { if (currentMapMode === 'colegios') loadColegiosMap(); });
document.getElementById('mapaColegiosDepto')?.addEventListener('change', () => { if (currentMapMode === 'colegios') loadColegiosMap(); });

// Populate departamentos for colegios mode (reuse existing API)
async function loadColegiosDeptos() {
    try {
        const ano = document.getElementById('mapaColegiosAno')?.value || '2024';
        const resp = await fetch(`/icfes/api/mapa-departamentos/?ano=${ano}`);
        const data = await resp.json();
        const sel = document.getElementById('mapaColegiosDepto');
        if (!sel) return;
        sel.innerHTML = '<option value="">Todos</option>';
        data.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.departamento;
            opt.textContent = d.departamento;
            sel.appendChild(opt);
        });
    } catch (e) { console.warn('Error loading deptos for colegios:', e); }
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
        loadDepartamentos();
        loadColegiosDeptos();
    } else {
        map.invalidateSize();
    }
});
