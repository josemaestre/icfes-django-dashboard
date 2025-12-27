
// ============================================================================
// SCHOOL SEARCH FUNCTIONALITY
// ============================================================================

let currentSchoolSk = null;
let schoolCharts = {};

// Initialize school search when tab is shown
document.addEventListener('DOMContentLoaded', function () {
    // Use event delegation since elements are in a tab
    document.body.addEventListener('click', function (e) {
        if (e.target && e.target.id === 'searchColegioBtn') {
            e.preventDefault();
            performSchoolSearch();
        }
    });

    document.body.addEventListener('input', function (e) {
        if (e.target && e.target.id === 'searchColegioInput') {
            debounceSearch();
        }
    });

    document.body.addEventListener('keypress', function (e) {
        if (e.target && e.target.id === 'searchColegioInput' && e.key === 'Enter') {
            e.preventDefault();
            performSchoolSearch();
        }
    });
});

// Debounce search
let searchTimeout;
function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(performSchoolSearch, 300);
}

// Perform school search
async function performSchoolSearch() {
    const searchInput = document.getElementById('searchColegioInput');
    const resultsDiv = document.getElementById('searchColegioResults');

    if (!searchInput || !resultsDiv) return;

    const query = searchInput.value;

    if (query.length < 3) {
        resultsDiv.innerHTML = '';
        return;
    }

    try {
        const response = await fetch(`/icfes/api/search/colegios/?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        resultsDiv.innerHTML = '';
        if (data.length === 0) {
            resultsDiv.innerHTML = '<div class="alert alert-info">No se encontraron colegios</div>';
            return;
        }

        const listGroup = document.createElement('div');
        listGroup.className = 'list-group';

        data.forEach(school => {
            const item = document.createElement('button');
            item.className = 'list-group-item list-group-item-action';
            item.innerHTML = `
                <strong>${school.nombre_colegio}</strong><br>
                <small class="text-muted">${school.codigo_dane} - ${school.municipio}, ${school.departamento}</small>
            `;
            item.onclick = () => loadSchoolDetail(school);
            listGroup.appendChild(item);
        });

        resultsDiv.appendChild(listGroup);
    } catch (error) {
        console.error('Error searching schools:', error);
        resultsDiv.innerHTML = '<div class="alert alert-danger">Error al buscar colegios</div>';
    }
}

// Load school detail
async function loadSchoolDetail(school) {
    currentSchoolSk = school.colegio_sk;
    document.getElementById('searchColegioResults').innerHTML = '';
    document.getElementById('schoolDetailSection').style.display = 'block';

    // Update header
    document.getElementById('schoolDetailName').textContent = school.nombre_colegio;
    document.getElementById('schoolDetailDane').textContent = school.codigo_dane;
    document.getElementById('schoolDetailSector').textContent = school.sector;
    document.getElementById('schoolDetailLocation').textContent = `${school.municipio}, ${school.departamento}`;

    // Load data
    await loadSchoolResumen(school.colegio_sk);
    await loadSchoolHistorico(school.colegio_sk);
    await loadSchoolComparacion(school.colegio_sk);
}

// Load school summary
async function loadSchoolResumen(sk) {
    try {
        const response = await fetch(`/icfes/api/colegio/${sk}/resumen/`);
        const data = await response.json();

        if (data.ultimo_ano) {
            document.getElementById('schoolStatPuntaje').textContent =
                data.ultimo_ano.avg_punt_global ? data.ultimo_ano.avg_punt_global.toFixed(1) : '--';
            document.getElementById('schoolStatRanking').textContent =
                data.ultimo_ano.ranking_nacional || '--';
            document.getElementById('schoolStatEstudiantes').textContent =
                data.ultimo_ano.total_estudiantes || '--';
        }

        if (data.rango_historico) {
            document.getElementById('schoolStatAnos').textContent =
                data.rango_historico.total_anos || '--';
        }
    } catch (error) {
        console.error('Error loading school summary:', error);
    }
}

// Load historical chart
async function loadSchoolHistorico(sk) {
    try {
        const response = await fetch(`/icfes/api/colegio/${sk}/historico/`);
        const data = await response.json();

        const options = {
            series: [{
                name: 'Colegio',
                data: data.map(d => d.avg_punt_global).reverse()
            }, {
                name: 'Promedio Municipal',
                data: data.map(d => d.promedio_municipal_global).reverse()
            }, {
                name: 'Promedio Nacional',
                data: data.map(d => d.promedio_nacional_global).reverse()
            }],
            chart: {
                type: 'line',
                height: 350,
                toolbar: { show: false }
            },
            xaxis: {
                categories: data.map(d => d.ano).reverse()
            },
            stroke: {
                curve: 'smooth',
                width: 3
            },
            colors: [colors.primary, colors.warning, colors.success]
        };

        if (schoolCharts.historico) schoolCharts.historico.destroy();
        schoolCharts.historico = new ApexCharts(document.querySelector('#schoolChartHistorico'), options);
        schoolCharts.historico.render();
    } catch (error) {
        console.error('Error loading historical chart:', error);
    }
}

// Load comparison chart
async function loadSchoolComparacion(sk) {
    try {
        const response = await fetch(`/icfes/api/colegio/${sk}/comparacion/`);
        const data = await response.json();

        // Radar chart
        const radarOptions = {
            series: [{
                name: 'Puntaje',
                data: [
                    data.avg_punt_matematicas,
                    data.avg_punt_lectura_critica,
                    data.avg_punt_c_naturales,
                    data.avg_punt_sociales_ciudadanas,
                    data.avg_punt_ingles
                ]
            }],
            chart: {
                type: 'radar',
                height: 350
            },
            xaxis: {
                categories: ['Matemáticas', 'Lectura', 'C. Naturales', 'Sociales', 'Inglés']
            },
            colors: [colors.primary]
        };

        if (schoolCharts.radar) schoolCharts.radar.destroy();
        schoolCharts.radar = new ApexCharts(document.querySelector('#schoolChartRadar'), radarOptions);
        schoolCharts.radar.render();

        // Comparison bar chart
        const barOptions = {
            series: [{
                name: 'Puntaje',
                data: [
                    data.puntaje_colegio,
                    data.promedio_municipal_global,
                    data.promedio_departamental_global,
                    data.promedio_nacional_global
                ]
            }],
            chart: {
                type: 'bar',
                height: 350,
                toolbar: { show: false }
            },
            plotOptions: {
                bar: {
                    horizontal: false,
                    columnWidth: '55%',
                    borderRadius: 3
                }
            },
            xaxis: {
                categories: ['Colegio', 'Municipal', 'Departamental', 'Nacional']
            },
            colors: [colors.primary]
        };

        if (schoolCharts.comparacion) schoolCharts.comparacion.destroy();
        schoolCharts.comparacion = new ApexCharts(document.querySelector('#schoolChartComparacion'), barOptions);
        schoolCharts.comparacion.render();
    } catch (error) {
        console.error('Error loading comparison charts:', error);
    }
}
