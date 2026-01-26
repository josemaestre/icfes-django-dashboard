
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

    // Load data - fetch once and pass to functions that need it
    const resumenData = await loadSchoolResumen(school.colegio_sk);
    const historicalData = await loadSchoolHistorico(school.colegio_sk);
    // Pass resumenData and historicalData to avoid duplicate API calls
    await loadSchoolComparacion(school.colegio_sk, resumenData, historicalData);

    // Load excellence indicators
    if (typeof loadIndicadoresExcelencia === 'function') {
        await loadIndicadoresExcelencia(school.colegio_sk);
    }

    // Load niveles distribution (donut chart)
    if (typeof loadDistribucionNiveles === 'function') {
        await loadDistribucionNiveles(school.colegio_sk);
    }

    // Render historical table
    if (typeof renderPerformanceTable === 'function' && historicalData) {
        renderPerformanceTable(historicalData);
    }
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

        // Cluster display
        if (data.cluster && data.cluster.cluster_name) {
            document.getElementById('schoolStatCluster').textContent = data.cluster.cluster_name;
            document.getElementById('schoolStatClusterDesc').textContent = `Grupo ${data.cluster.cluster_id}`;
            // Load similar schools
            loadSimilarSchools(sk);
        } else {
            document.getElementById('schoolStatCluster').textContent = 'No Clasificado';
            document.getElementById('schoolStatClusterDesc').textContent = 'Sin cluster asignado';
            document.getElementById('similarSchoolsTableBody').innerHTML = `
                <tr><td colspan="3" class="text-center text-muted py-3">
                    <small>No hay datos de cluster disponibles</small>
                </td></tr>
            `;
        }

        // Z-Score display with interpretation
        if (data.z_score && data.z_score.z_score_global !== null) {
            const zScore = data.z_score.z_score_global;
            const zScoreElement = document.getElementById('schoolStatZScore');
            const interpretationElement = document.getElementById('schoolStatZScoreInterpretation');

            // Display z-score with color coding
            zScoreElement.textContent = zScore.toFixed(2);

            // Color coding based on z-score
            if (zScore >= 2) {
                zScoreElement.className = 'mb-0 fw-bold text-success';
                interpretationElement.innerHTML = '<span class="badge bg-success">⭐ Élite</span>';
            } else if (zScore >= 1) {
                zScoreElement.className = 'mb-0 fw-bold text-success';
                interpretationElement.innerHTML = '<span class="badge bg-success">Muy Superior</span>';
            } else if (zScore >= 0.5) {
                zScoreElement.className = 'mb-0 fw-bold text-info';
                interpretationElement.innerHTML = '<span class="badge bg-info">Superior</span>';
            } else if (zScore >= -0.5) {
                zScoreElement.className = 'mb-0 fw-bold text-secondary';
                interpretationElement.innerHTML = '<span class="badge bg-secondary">Promedio</span>';
            } else if (zScore >= -1) {
                zScoreElement.className = 'mb-0 fw-bold text-warning';
                interpretationElement.innerHTML = '<span class="badge bg-warning">Por Debajo</span>';
            } else {
                zScoreElement.className = 'mb-0 fw-bold text-danger';
                interpretationElement.innerHTML = '<span class="badge bg-danger">Muy Bajo</span>';
            }

            // Show Z-Score explanation
            const explanationSection = document.getElementById('zscoreExplanation');
            if (explanationSection) {
                explanationSection.style.display = 'block';
            }
        } else {
            document.getElementById('schoolStatZScore').textContent = '--';
            document.getElementById('schoolStatZScoreInterpretation').innerHTML = '<span class="text-muted">Sin datos</span>';
        }

        return data; // Return data for reuse in other functions
    } catch (error) {
        console.error('Error loading school summary:', error);
        return null;
    }
}

// Load similar schools based on cluster
async function loadSimilarSchools(sk) {
    try {
        const response = await fetch(`/icfes/api/colegio/${sk}/similares/?limit=5`);
        const data = await response.json();

        const tbody = document.getElementById('similarSchoolsTableBody');
        if (!tbody) return;

        if (data.error || !data.length) {
            tbody.innerHTML = `
                <tr><td colspan="3" class="text-center text-muted py-3">
                    <small>No se encontraron colegios similares</small>
                </td></tr>
            `;
            return;
        }

        tbody.innerHTML = '';
        data.forEach(school => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <strong class="d-block text-truncate" style="max-width: 200px;" title="${school.nombre_colegio}">
                        ${school.nombre_colegio}
                    </strong>
                    <small class="text-muted">${school.municipio}</small>
                </td>
                <td class="text-center">
                    <span class="badge bg-primary">${school.avg_punt_global ? school.avg_punt_global.toFixed(1) : '--'}</span>
                </td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-primary" onclick="loadSchoolDetail({colegio_sk: '${school.colegio_sk}', nombre_colegio: '${school.nombre_colegio.replace(/'/g, "\\'")}', codigo_dane: '', sector: '', municipio: '${school.municipio}', departamento: '${school.departamento || ''}'})">
                        <i class="bx bx-search-alt"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading similar schools:', error);
        const tbody = document.getElementById('similarSchoolsTableBody');
        if (tbody) {
            tbody.innerHTML = `
                <tr><td colspan="3" class="text-center text-danger py-3">
                    <small>Error cargando colegios similares</small>
                </td></tr>
            `;
        }
    }
}

// Load historical chart
async function loadSchoolHistorico(sk) {
    try {
        const response = await fetch(`/icfes/api/colegio/${sk}/historico/`);
        const data = await response.json();

        // Deduplicate by year, keeping most recent entry
        const uniqueData = {};
        data.forEach(d => {
            if (!uniqueData[d.ano]) {
                uniqueData[d.ano] = d;
            }
        });

        // Sort by year ascending (oldest to newest)
        const sortedData = Object.values(uniqueData).sort((a, b) => parseInt(a.ano) - parseInt(b.ano));

        console.log(`Historical data loaded: ${sortedData.length} years from ${sortedData[0]?.ano} to ${sortedData[sortedData.length - 1]?.ano}`);
        console.log('Years:', sortedData.map(d => d.ano));

        const options = {
            series: [{
                name: 'Colegio',
                data: sortedData.map(d => d.avg_punt_global)
            }, {
                name: 'Promedio Municipal',
                data: sortedData.map(d => d.promedio_municipal_global)
            }, {
                name: 'Promedio Nacional',
                data: sortedData.map(d => d.promedio_nacional_global)
            }],
            chart: {
                type: 'line',
                height: 350,
                toolbar: { show: true },
                zoom: {
                    enabled: true,
                    type: 'x',
                    autoScaleYaxis: true
                }
            },
            xaxis: {
                categories: sortedData.map(d => d.ano),
                type: 'category',
                labels: {
                    rotate: -45,
                    rotateAlways: false,
                    hideOverlappingLabels: true,
                    showDuplicates: false,
                    trim: false,
                    minHeight: undefined,
                    maxHeight: 120,
                    style: {
                        fontSize: '11px'
                    }
                },
                tickAmount: undefined, // Show all ticks
                tickPlacement: 'on'
            },
            yaxis: {
                labels: {
                    formatter: function (val) {
                        return Math.round(val);
                    }
                }
            },
            stroke: {
                curve: 'smooth',
                width: 3
            },
            markers: {
                size: 4,
                hover: {
                    size: 6
                }
            },
            tooltip: {
                y: {
                    formatter: function (val) {
                        return val ? val.toFixed(2) : '0.00';
                    }
                },
                x: {
                    formatter: function (val) {
                        return 'Año ' + val;
                    }
                }
            },
            legend: {
                show: true,
                position: 'top',
                horizontalAlign: 'left'
            },
            colors: [colors.primary, colors.warning, colors.success]
        };

        if (schoolCharts.historico) schoolCharts.historico.destroy();
        schoolCharts.historico = new ApexCharts(document.querySelector('#schoolChartHistorico'), options);
        schoolCharts.historico.render();

        return sortedData; // Return data for table
    } catch (error) {
        console.error('Error loading historical chart:', error);
        return [];
    }
}

// Load comparison chart - UPDATED to use new optimized endpoint
// Now accepts resumenData and historicalData to avoid duplicate API calls
async function loadSchoolComparacion(sk, resumenData = null, historicalData = null) {
    try {
        // Use passed resumenData or fetch if not provided
        if (!resumenData) {
            const resumenResponse = await fetch(`/icfes/api/colegio/${sk}/resumen/`);
            resumenData = await resumenResponse.json();
        }
        const latestYear = resumenData?.ultimo_ano?.ano || 2022;

        // Use new optimized endpoint for chart data
        const response = await fetch(`/icfes/api/colegio/${sk}/comparacion-chart-data/?ano=${latestYear}`);
        const chartData = await response.json();

        // Radar chart - Now with 4 series (Colegio, Municipal, Departamental, Nacional)
        const radarOptions = {
            series: chartData.datasets,
            chart: {
                type: 'radar',
                height: 350
            },
            yaxis: {
                show: true,
                min: 0,
                max: 100,
                tickAmount: 5,
                labels: {
                    formatter: function (val) {
                        return Math.round(val);
                    }
                }
            },
            xaxis: {
                categories: chartData.labels
            },
            tooltip: {
                y: {
                    formatter: function (val) {
                        return val ? val.toFixed(2) : '0.00';
                    }
                }
            },
            colors: [colors.primary, colors.warning, colors.info, colors.success],
            plotOptions: {
                radar: {
                    polygons: {
                        strokeColors: '#b0b0b0',
                        fill: {
                            colors: ['#e0e0e0', '#ececec']
                        }
                    }
                }
            },
            fill: {
                opacity: 0.3
            },
            stroke: {
                width: 2
            },
            markers: {
                size: 4
            },
            legend: {
                show: true,
                position: 'bottom'
            }
        };

        if (schoolCharts.radar) schoolCharts.radar.destroy();
        schoolCharts.radar = new ApexCharts(document.querySelector('#schoolChartRadar'), radarOptions);
        schoolCharts.radar.render();

        // Get full comparison data for bar chart and table
        const contextResponse = await fetch(`/icfes/api/colegio/${sk}/comparacion-contexto/?ano=${latestYear}`);
        const contextData = await contextResponse.json();

        // Comparison bar chart - Global scores only
        const barOptions = {
            series: [{
                name: 'Puntaje Global',
                data: [
                    contextData.colegio_global,
                    contextData.promedio_municipal_global,
                    contextData.promedio_departamental_global,
                    contextData.promedio_nacional_global
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
                    borderRadius: 3,
                    dataLabels: {
                        position: 'top'
                    }
                }
            },
            dataLabels: {
                enabled: true,
                formatter: function (val) {
                    return val.toFixed(2);
                },
                offsetY: -20,
                style: {
                    fontSize: '12px',
                    colors: ['#304758']
                }
            },
            xaxis: {
                categories: [
                    contextData.nombre_colegio.substring(0, 20) + '...',
                    contextData.municipio,
                    contextData.departamento,
                    'Nacional'
                ]
            },
            yaxis: {
                labels: {
                    formatter: function (val) {
                        return Math.round(val);
                    }
                }
            },
            tooltip: {
                y: {
                    formatter: function (val) {
                        return val ? val.toFixed(2) : '0.00';
                    }
                }
            },
            colors: [colors.primary]
        };

        if (schoolCharts.comparacion) schoolCharts.comparacion.destroy();
        schoolCharts.comparacion = new ApexCharts(document.querySelector('#schoolChartComparacion'), barOptions);
        schoolCharts.comparacion.render();

        // Update performance table with new data
        updatePerformanceTable(contextData);

        // Update comparison context section (NEW)
        updateComparisonContext(contextData);

        // Update strategic insights section (NEW)
        if (typeof window.updateStrategicInsights === 'function') {
            console.log('Calling updateStrategicInsights...');
            // Use passed historicalData or fetch if not provided
            let histData = historicalData;
            if (!histData) {
                const historicalResponse = await fetch(`/icfes/api/colegio/${sk}/historico/`);
                histData = await historicalResponse.json();
            }
            window.updateStrategicInsights(contextData, histData);
        } else {
            console.warn('updateStrategicInsights function not found');
        }

        // Initialize school gauges (NEW)
        if (typeof initializeSchoolGauges === 'function') {
            console.log('Initializing school gauges...');
            initializeSchoolGauges(contextData);
        } else {
            console.warn('initializeSchoolGauges function not found');
        }

    } catch (error) {
        console.error('Error loading comparison charts:', error);
    }
}

// New function to update performance table with context data
function updatePerformanceTable(data) {
    const subjects = [
        { key: 'lectura', name: 'Lectura Crítica' },
        { key: 'matematicas', name: 'Matemáticas' },
        { key: 'c_naturales', name: 'C. Naturales' },
        { key: 'sociales', name: 'Sociales' },
        { key: 'ingles', name: 'Inglés' }
    ];

    const tableBody = document.querySelector('#performanceTable tbody');
    if (!tableBody) return;

    tableBody.innerHTML = '';

    subjects.forEach(subject => {
        const schoolScore = data[`colegio_${subject.key}`] || 0;
        const municipalScore = data[`promedio_municipal_${subject.key}`] || 0;
        const departamentalScore = data[`promedio_departamental_${subject.key}`] || 0;
        const nacionalScore = data[`promedio_nacional_${subject.key}`] || 0;
        const brecha = schoolScore - nacionalScore;
        const estado = brecha >= 0 ?
            '<span class="badge bg-success">Por encima</span>' :
            '<span class="badge bg-danger">Por debajo</span>';

        const row = `
            <tr>
                <td><strong>${subject.name}</strong></td>
                <td>${schoolScore.toFixed(2)}</td>
                <td>${municipalScore.toFixed(2)}</td>
                <td>${departamentalScore.toFixed(2)}</td>
                <td>${nacionalScore.toFixed(2)}</td>
                <td class="${brecha >= 0 ? 'text-success' : 'text-danger'}">
                    ${brecha >= 0 ? '+' : ''}${brecha.toFixed(2)}
                </td>
                <td>${estado}</td>
            </tr>
        `;
        tableBody.innerHTML += row;
    });

    // Add global row
    const globalBrecha = data.colegio_global - data.promedio_nacional_global;
    const globalEstado = globalBrecha >= 0 ?
        '<span class="badge bg-success">Por encima</span>' :
        '<span class="badge bg-danger">Por debajo</span>';

    const globalRow = `
        <tr class="table-active">
            <td><strong>GLOBAL</strong></td>
            <td><strong>${data.colegio_global.toFixed(2)}</strong></td>
            <td><strong>${data.promedio_municipal_global.toFixed(2)}</strong></td>
            <td><strong>${data.promedio_departamental_global.toFixed(2)}</strong></td>
            <td><strong>${data.promedio_nacional_global.toFixed(2)}</strong></td>
            <td class="${globalBrecha >= 0 ? 'text-success' : 'text-danger'}">
                <strong>${globalBrecha >= 0 ? '+' : ''}${globalBrecha.toFixed(2)}</strong>
            </td>
            <td>${globalEstado}</td>
        </tr>
    `;
    tableBody.innerHTML += globalRow;
}

// New function to update comparison context section
function updateComparisonContext(data) {
    // Update Brechas (Gaps)
    updateBrechaDisplay('brechaMunicipal', 'brechaMunicipalBar', data.brecha_municipal_global);
    updateBrechaDisplay('brechaDepartamental', 'brechaDepartamentalBar', data.brecha_departamental_global);
    updateBrechaDisplay('brechaNacional', 'brechaNacionalBar', data.brecha_nacional_global);

    // Update Percentiles
    updatePercentilDisplay('percentilMunicipal', 'percentilMunicipalBar', data.percentil_municipal);
    updatePercentilDisplay('percentilDepartamental', 'percentilDepartamentalBar', data.percentil_departamental);
    updatePercentilDisplay('percentilNacional', 'percentilNacionalBar', data.percentil_nacional);

    // Update Classifications
    updateClasificacionDisplay('clasificacionMunicipal', data.clasificacion_vs_municipal);
    updateClasificacionDisplay('clasificacionDepartamental', data.clasificacion_vs_departamental);
    updateClasificacionDisplay('clasificacionNacional', data.clasificacion_vs_nacional);
}

// Helper function to update brecha display
function updateBrechaDisplay(badgeId, barId, value) {
    const badge = document.getElementById(badgeId);
    const bar = document.getElementById(barId);

    if (!badge || !bar) return;

    const formattedValue = value >= 0 ? `+${value.toFixed(2)}` : value.toFixed(2);
    badge.textContent = formattedValue;

    // Color based on value
    if (value >= 10) {
        badge.className = 'badge bg-success';
        bar.className = 'progress-bar bg-success';
    } else if (value >= 0) {
        badge.className = 'badge bg-info';
        bar.className = 'progress-bar bg-info';
    } else if (value >= -10) {
        badge.className = 'badge bg-warning';
        bar.className = 'progress-bar bg-warning';
    } else {
        badge.className = 'badge bg-danger';
        bar.className = 'progress-bar bg-danger';
    }

    // Bar width (scale from -30 to +30 to 0-100%)
    const percentage = Math.min(100, Math.max(0, ((value + 30) / 60) * 100));
    bar.style.width = percentage + '%';
}

// Helper function to update percentil display
function updatePercentilDisplay(spanId, barId, value) {
    const span = document.getElementById(spanId);
    const bar = document.getElementById(barId);

    if (!span || !bar) return;

    const percentile = Math.round(value);
    span.textContent = percentile + '%';
    bar.style.width = percentile + '%';

    // Color based on percentile
    if (percentile >= 75) {
        bar.className = 'progress-bar bg-success';
    } else if (percentile >= 50) {
        bar.className = 'progress-bar bg-info';
    } else if (percentile >= 25) {
        bar.className = 'progress-bar bg-warning';
    } else {
        bar.className = 'progress-bar bg-danger';
    }
}

// Helper function to update clasificacion display
function updateClasificacionDisplay(divId, value) {
    const div = document.getElementById(divId);

    if (!div) return;

    div.textContent = value;

    // Color based on classification
    if (value.includes('Muy Superior')) {
        div.className = 'alert alert-success mb-0 py-2';
    } else if (value.includes('Superior')) {
        div.className = 'alert alert-info mb-0 py-2';
    } else if (value.includes('Similar')) {
        div.className = 'alert alert-secondary mb-0 py-2';
    } else if (value.includes('Inferior')) {
        div.className = 'alert alert-warning mb-0 py-2';
    } else if (value.includes('Muy Inferior')) {
        div.className = 'alert alert-danger mb-0 py-2';
    }
}

// ============================================================================
// EXCELLENCE INDICATORS
// ============================================================================

let chartComparacionExcelencia = null;

// Load excellence indicators for a school
async function loadIndicadoresExcelencia(sk) {
    try {
        const response = await fetch(`/icfes/api/colegio/${sk}/indicadores-excelencia/`);
        const data = await response.json();

        if (!data || data.length === 0) {
            // Hide section if no data
            document.getElementById('indicadoresExcelenciaSection').style.display = 'none';
            return;
        }

        // Show section
        document.getElementById('indicadoresExcelenciaSection').style.display = 'block';

        const actual = data[0]; // Most recent year
        const anterior = data.length > 1 ? data[1] : null;

        // Update cards
        updateIndicadorCard('ExcelenciaIntegral', actual, anterior, {
            pct: 'pct_excelencia_integral',
            nacional: 'nacional_excelencia',
            ranking: 'ranking_excelencia'
        });

        updateIndicadorCard('CompetenciaSatisfactoria', actual, anterior, {
            pct: 'pct_competencia_satisfactoria_integral',
            nacional: 'nacional_competencia',
            ranking: 'ranking_competencia'
        });

        updateIndicadorCard('PerfilStem', actual, anterior, {
            pct: 'pct_perfil_stem_avanzado',
            nacional: 'nacional_stem',
            ranking: 'ranking_stem'
        });

        updateIndicadorCard('PerfilHumanistico', actual, anterior, {
            pct: 'pct_perfil_humanistico_avanzado',
            nacional: 'nacional_humanistico',
            ranking: 'ranking_humanistico'
        });

        // Update Riesgo Alto card (5th indicator - inverted logic)
        updateRiesgoAltoCard(actual, anterior);

        // Render comparison chart
        renderComparacionExcelenciaChart(actual);
    } catch (error) {
        console.error('Error loading excellence indicators:', error);
        document.getElementById('indicadoresExcelenciaSection').style.display = 'none';
    }
}

// Update indicator card
function updateIndicadorCard(tipo, actual, anterior, config) {
    const valor = actual[config.pct] || 0;
    const ranking = actual[config.ranking] || 0;

    // Update percentage
    const pctElement = document.getElementById(`pct${tipo}`);
    if (pctElement) {
        pctElement.textContent = valor.toFixed(1) + '%';
    }

    // Update ranking (Top X% Nacional)
    const topPct = 100 - ranking;
    const rankingElement = document.getElementById(`ranking${tipo}`);
    if (rankingElement) {
        rankingElement.textContent = `Top ${topPct.toFixed(0)}% Nacional`;
    }

    // Calculate trend vs previous year
    const tendenciaElement = document.getElementById(`tendencia${tipo}`);
    if (tendenciaElement) {
        if (anterior) {
            const cambio = valor - (anterior[config.pct] || 0);
            const icon = cambio >= 0 ? '↑' : '↓';
            const color = cambio >= 0 ? 'text-success' : 'text-danger';
            tendenciaElement.innerHTML = `
                <span class="${color}">
                    ${icon} ${Math.abs(cambio).toFixed(1)}% vs año anterior
                </span>
            `;
        } else {
            tendenciaElement.innerHTML = '<span class="text-muted">Sin datos previos</span>';
        }
    }
}

// Render excellence comparison chart
function renderComparacionExcelenciaChart(data) {
    // Destroy previous chart if exists
    if (chartComparacionExcelencia) {
        chartComparacionExcelencia.destroy();
    }

    const options = {
        series: [{
            name: 'Tu Colegio',
            data: [
                data.pct_excelencia_integral || 0,
                data.pct_competencia_satisfactoria_integral || 0,
                data.pct_perfil_stem_avanzado || 0,
                data.pct_perfil_humanistico_avanzado || 0
            ]
        }, {
            name: 'Promedio Nacional',
            data: [
                data.nacional_excelencia || 0,
                data.nacional_competencia || 0,
                data.nacional_stem || 0,
                data.nacional_humanistico || 0
            ]
        }],
        chart: {
            type: 'bar',
            height: 350
        },
        plotOptions: {
            bar: {
                horizontal: true,
                dataLabels: {
                    position: 'top'
                }
            }
        },
        dataLabels: {
            enabled: true,
            formatter: function (val) {
                return val.toFixed(1) + '%';
            },
            offsetX: 30,
            style: {
                fontSize: '12px',
                colors: ['#304758']
            }
        },
        xaxis: {
            categories: [
                'Excelencia Integral',
                'Competencia Satisfactoria',
                'Perfil STEM',
                'Perfil Humanístico'
            ],
            labels: {
                formatter: function (val) {
                    return val.toFixed(1) + '%';
                }
            }
        },
        yaxis: {
            labels: {
                style: {
                    fontSize: '12px'
                }
            }
        },
        colors: [colors.primary, colors.success],
        legend: {
            position: 'top',
            horizontalAlign: 'left'
        },
        tooltip: {
            y: {
                formatter: function (val) {
                    return val.toFixed(2) + '%';
                }
            }
        }
    };

    chartComparacionExcelencia = new ApexCharts(
        document.querySelector("#chartComparacionExcelencia"),
        options
    );
    chartComparacionExcelencia.render();
}

// Update Riesgo Alto card (inverted logic - lower is better)
function updateRiesgoAltoCard(actual, anterior) {
    const valor = actual.pct_riesgo_alto || 0;
    const nacional = actual.nacional_riesgo || 0;
    const ranking = actual.ranking_riesgo || 0;

    // Update percentage
    const pctElement = document.getElementById('pctRiesgoAlto');
    if (pctElement) {
        pctElement.textContent = valor.toFixed(1) + '%';
    }

    // Update difference vs national (inverted: negative is good)
    const diferencia = valor - nacional;
    const diferenciaElement = document.getElementById('diferenciaRiesgo');
    if (diferenciaElement) {
        const signo = diferencia >= 0 ? '+' : '';
        diferenciaElement.textContent = `${signo}${diferencia.toFixed(1)}%`;

        // Color: green if below national, red if above
        if (diferencia <= -5) {
            diferenciaElement.className = 'mb-0 text-success fw-bold';
        } else if (diferencia < 0) {
            diferenciaElement.className = 'mb-0 text-info fw-bold';
        } else if (diferencia < 5) {
            diferenciaElement.className = 'mb-0 text-warning fw-bold';
        } else {
            diferenciaElement.className = 'mb-0 text-danger fw-bold';
        }
    }

    // Update ranking (inverted: lower percentile is better for risk)
    const rankingElement = document.getElementById('rankingRiesgo');
    if (rankingElement) {
        if (ranking < 25) {
            rankingElement.textContent = `✅ Bajo Riesgo (Bottom ${ranking.toFixed(0)}%)`;
            rankingElement.className = 'badge bg-success';
        } else if (ranking < 50) {
            rankingElement.textContent = `Riesgo Moderado (${ranking.toFixed(0)}%)`;
            rankingElement.className = 'badge bg-warning';
        } else {
            rankingElement.textContent = `⚠️ Alto Riesgo (${ranking.toFixed(0)}%)`;
            rankingElement.className = 'badge bg-danger';
        }
    }

    // Calculate trend vs previous year (inverted: decrease is good)
    const tendenciaElement = document.getElementById('tendenciaRiesgo');
    if (tendenciaElement) {
        if (anterior && anterior.pct_riesgo_alto !== undefined) {
            const cambio = valor - anterior.pct_riesgo_alto;
            const icon = cambio <= 0 ? '↓' : '↑';
            const color = cambio <= 0 ? 'text-success' : 'text-danger';
            const texto = cambio <= 0 ? 'Mejora' : 'Aumento';
            tendenciaElement.innerHTML = `
                <span class="${color}">
                    ${icon} ${Math.abs(cambio).toFixed(1)}% ${texto} vs año anterior
                </span>
            `;
        } else {
            tendenciaElement.innerHTML = '<span class="text-muted">Sin datos previos</span>';
        }
    }
}

// Export function to be called from loadSchoolDetail
window.loadIndicadoresExcelencia = loadIndicadoresExcelencia;

// ============================================================================
// DISTRIBUCIÓN DE NIVELES DE DESEMPEÑO (DONUT CHART)
// ============================================================================

let nivelesDonutChart = null;
let nivelesData = null;

// Initialize niveles event listeners
document.addEventListener('DOMContentLoaded', function () {
    const subjectSelector = document.getElementById('nivelesSubjectSelector');
    if (subjectSelector) {
        subjectSelector.addEventListener('change', function () {
            if (nivelesData && currentSchoolSk) {
                renderNivelesDonut(this.value);
            }
        });
    }
});

// Load niveles distribution data for a school
async function loadDistribucionNiveles(sk) {
    console.log(`[DEBUG] loadDistribucionNiveles called for sk: ${sk}`);
    try {
        const response = await fetch(`/icfes/api/colegio/${sk}/distribucion-niveles/`);
        console.log(`[DEBUG] fetch response status: ${response.status}`);
        const data = await response.json();

        if (!data || !data.materias) {
            console.warn('No data returned for niveles distribution');
            return;
        }

        // Store data globally for subject switching
        nivelesData = data;

        // Render initial chart (default to matematicas)
        const subjectSelector = document.getElementById('nivelesSubjectSelector');
        const selectedSubject = subjectSelector ? subjectSelector.value : 'matematicas';
        renderNivelesDonut(selectedSubject);

        console.log('Niveles distribution loaded successfully');
    } catch (error) {
        console.error('Error loading niveles distribution:', error);
    }
}

// Render donut chart for selected subject
function renderNivelesDonut(subject) {
    if (!nivelesData || !nivelesData.materias || !nivelesData.materias[subject]) {
        console.warn(`No data for subject: ${subject}`);
        return;
    }

    const subjectData = nivelesData.materias[subject];

    // Colors for levels (matching ICFES style)
    const colores = {
        nivel_1: '#dc3545', // Rojo - Insuficiente
        nivel_2: '#ffc107', // Amarillo - Mínimo
        nivel_3: '#17a2b8', // Azul - Satisfactorio
        nivel_4: '#28a745'  // Verde - Avanzado
    };

    // Prepare data for chart
    const series = [
        subjectData.nivel_1?.porcentaje || 0,
        subjectData.nivel_2?.porcentaje || 0,
        subjectData.nivel_3?.porcentaje || 0,
        subjectData.nivel_4?.porcentaje || 0
    ];

    const labels = ['Nivel 1 - Insuficiente', 'Nivel 2 - Mínimo', 'Nivel 3 - Satisfactorio', 'Nivel 4 - Avanzado'];

    // Destroy previous chart if exists
    if (nivelesDonutChart) {
        nivelesDonutChart.destroy();
    }

    const options = {
        series: series,
        chart: {
            type: 'donut',
            height: 320
        },
        labels: labels,
        colors: [colores.nivel_1, colores.nivel_2, colores.nivel_3, colores.nivel_4],
        plotOptions: {
            pie: {
                donut: {
                    size: '65%',
                    labels: {
                        show: true,
                        name: {
                            show: true,
                            fontSize: '14px',
                            fontWeight: 600
                        },
                        value: {
                            show: true,
                            fontSize: '20px',
                            fontWeight: 700,
                            formatter: function (val) {
                                return parseFloat(val).toFixed(1) + '%';
                            }
                        },
                        total: {
                            show: true,
                            label: 'Total',
                            fontSize: '14px',
                            formatter: function (w) {
                                const total = nivelesData.total_estudiantes ||
                                    Object.values(subjectData).reduce((sum, n) => sum + (n?.cantidad || 0), 0);
                                return total + ' estudiantes';
                            }
                        }
                    }
                }
            }
        },
        dataLabels: {
            enabled: true,
            formatter: function (val, opts) {
                return parseFloat(val).toFixed(1) + '%';
            },
            style: {
                fontSize: '12px',
                fontWeight: 600
            },
            dropShadow: {
                enabled: false
            }
        },
        legend: {
            show: false // We have custom legend
        },
        tooltip: {
            y: {
                formatter: function (value, { seriesIndex }) {
                    const niveles = ['nivel_1', 'nivel_2', 'nivel_3', 'nivel_4'];
                    const count = subjectData[niveles[seriesIndex]]?.cantidad || 0;
                    return `${value.toFixed(1)}% (${count} estudiantes)`;
                }
            }
        },
        responsive: [{
            breakpoint: 480,
            options: {
                chart: {
                    height: 280
                }
            }
        }]
    };

    nivelesDonutChart = new ApexCharts(document.querySelector("#schoolNivelesDonut"), options);
    nivelesDonutChart.render();

    // Update legend bars
    updateNivelesLeyenda(subjectData);
}

// Update legend progress bars
function updateNivelesLeyenda(subjectData) {
    // Nivel 4
    const nivel4 = subjectData.nivel_4 || { porcentaje: 0, cantidad: 0 };
    document.getElementById('nivel4-pct').textContent = nivel4.porcentaje.toFixed(1) + '%';
    document.getElementById('nivel4-bar').style.width = nivel4.porcentaje + '%';
    document.getElementById('nivel4-count').textContent = nivel4.cantidad;

    // Nivel 3
    const nivel3 = subjectData.nivel_3 || { porcentaje: 0, cantidad: 0 };
    document.getElementById('nivel3-pct').textContent = nivel3.porcentaje.toFixed(1) + '%';
    document.getElementById('nivel3-bar').style.width = nivel3.porcentaje + '%';
    document.getElementById('nivel3-count').textContent = nivel3.cantidad;

    // Nivel 2
    const nivel2 = subjectData.nivel_2 || { porcentaje: 0, cantidad: 0 };
    document.getElementById('nivel2-pct').textContent = nivel2.porcentaje.toFixed(1) + '%';
    document.getElementById('nivel2-bar').style.width = nivel2.porcentaje + '%';
    document.getElementById('nivel2-count').textContent = nivel2.cantidad;

    // Nivel 1
    const nivel1 = subjectData.nivel_1 || { porcentaje: 0, cantidad: 0 };
    document.getElementById('nivel1-pct').textContent = nivel1.porcentaje.toFixed(1) + '%';
    document.getElementById('nivel1-bar').style.width = nivel1.porcentaje + '%';
    document.getElementById('nivel1-count').textContent = nivel1.cantidad;
}

// Export function to be called from loadSchoolDetail
window.loadDistribucionNiveles = loadDistribucionNiveles;
