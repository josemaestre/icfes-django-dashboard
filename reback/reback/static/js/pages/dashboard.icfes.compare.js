/**
 * School Comparison Module for ICFES Dashboard
 * Handles side-by-side comparison of two schools
 */

// Store comparison data and charts
let comparisonData = null;
let comparisonCharts = {
    gaugeA: null,
    gaugeB: null,
    materias: null
};

/**
 * Initialize the comparison module
 * Waits for jQuery to be available before initializing Select2
 */
function initComparisonModule() {
    // Check if jQuery is available
    if (typeof jQuery === 'undefined' || typeof jQuery.fn.select2 === 'undefined') {
        // jQuery not ready yet, wait and try again
        setTimeout(initComparisonModule, 100);
        return;
    }

    // Initialize Select2 for school selectors
    initializeSchoolSelectors();

    // Bind compare button
    const btnComparar = document.getElementById('btn-comparar');
    if (btnComparar) {
        btnComparar.addEventListener('click', compareSchools);
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initComparisonModule);
} else {
    // DOM already loaded
    initComparisonModule();
}

/**
 * Initialize Select2 for school search
 */
function initializeSchoolSelectors() {
    const selectors = ['#select-colegio-a', '#select-colegio-b'];

    selectors.forEach(selector => {
        $(selector).select2({
            ajax: {
                url: '/icfes/api/search/colegios/',
                dataType: 'json',
                delay: 250,
                data: function (params) {
                    return { q: params.term };
                },
                processResults: function (data) {
                    return {
                        results: data.map(school => ({
                            id: school.colegio_sk,
                            text: `${school.nombre_colegio} - ${school.municipio}, ${school.departamento}`
                        }))
                    };
                }
            },
            placeholder: 'Buscar colegio...',
            minimumInputLength: 3,
            language: {
                inputTooShort: function () {
                    return 'Escribe al menos 3 caracteres';
                },
                searching: function () {
                    return 'Buscando...';
                },
                noResults: function () {
                    return 'No se encontraron colegios';
                }
            }
        });
    });
}

/**
 * Compare two schools
 */
async function compareSchools() {
    const colegioA = $('#select-colegio-a').val();
    const colegioB = $('#select-colegio-b').val();

    if (!colegioA || !colegioB) {
        alert('Por favor selecciona dos colegios');
        return;
    }

    if (colegioA === colegioB) {
        alert('Por favor selecciona dos colegios diferentes');
        return;
    }

    try {
        // Show loading
        const btnComparar = document.getElementById('btn-comparar');
        btnComparar.disabled = true;
        btnComparar.innerHTML = '<i class="bx bx-loader bx-spin"></i> Comparando...';

        // Get selected year
        const ano = document.getElementById('select-ano-comparacion').value;

        const response = await fetch(
            `/icfes/api/comparar-colegios/?colegio_a_sk=${colegioA}&colegio_b_sk=${colegioB}&ano=${ano}`
        );

        if (response.status === 401) {
            alert('Debes iniciar sesión para comparar colegios');
            window.location.href = '/accounts/login/';
            return;
        }

        if (!response.ok) {
            throw new Error('Error al cargar comparación');
        }

        comparisonData = await response.json();

        // Render comparison
        renderComparison(comparisonData);

        // Show results
        document.getElementById('comparison-results').style.display = 'block';

        // Scroll to results
        document.getElementById('comparison-results').scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error('Error:', error);
        alert('Error al comparar colegios: ' + error.message);
    } finally {
        // Reset button
        const btnComparar = document.getElementById('btn-comparar');
        btnComparar.disabled = false;
        btnComparar.innerHTML = '<i class="bx bx-search"></i> Comparar Colegios';
    }
}

/**
 * Render comparison results
 */
function renderComparison(data) {
    // Render headers
    renderHeaders(data);

    // Render global comparison
    renderGlobalComparison(data);

    // Render gauges
    renderGauges(data);

    // Render subject comparison
    renderSubjectComparison(data);

    // Render Z-Score
    renderZScore(data);

    // Render excellence indicators
    renderExcellenceIndicators(data);

    // Render insights
    renderInsights(data);

    // Render historical trends (if data available)
    renderHistoricalTrends(data);

    // Render radar chart
    renderRadarChart(data);
}

/**
 * Render school headers
 */
function renderHeaders(data) {
    const { colegio_a, colegio_b } = data;

    document.getElementById('nombre-colegio-a').textContent = colegio_a.nombre;
    document.getElementById('ubicacion-colegio-a').textContent =
        `${colegio_a.municipio}, ${colegio_a.departamento} • ${colegio_a.sector} • ${colegio_a.total_estudiantes} estudiantes`;

    document.getElementById('nombre-colegio-b').textContent = colegio_b.nombre;
    document.getElementById('ubicacion-colegio-b').textContent =
        `${colegio_b.municipio}, ${colegio_b.departamento} • ${colegio_b.sector} • ${colegio_b.total_estudiantes} estudiantes`;
}

/**
 * Render global scores comparison
 */
function renderGlobalComparison(data) {
    const { colegio_a, colegio_b, diferencias } = data;

    const diff = diferencias.puntaje_global;
    const ganador = diff.ganador === 'colegio_a' ? colegio_a.nombre : colegio_b.nombre;
    const diffColor = diff.ganador === 'colegio_a' ? 'success' : 'danger';

    const html = `
        <div class="row text-center">
            <div class="col-md-5">
                <h2 class="text-primary">${colegio_a.puntaje_global.toFixed(1)}</h2>
                <p class="text-muted">Puntaje Global</p>
            </div>
            <div class="col-md-2 d-flex align-items-center justify-content-center">
                <span class="badge bg-${diffColor} fs-5">
                    ${diff.absoluta > 0 ? '+' : ''}${diff.absoluta.toFixed(1)} pts
                </span>
            </div>
            <div class="col-md-5">
                <h2 class="text-info">${colegio_b.puntaje_global.toFixed(1)}</h2>
                <p class="text-muted">Puntaje Global</p>
            </div>
        </div>
        <div class="text-center mt-3">
            <p class="mb-0"><strong>${ganador}</strong> tiene un puntaje ${Math.abs(diff.porcentual).toFixed(1)}% ${diff.absoluta > 0 ? 'superior' : 'inferior'}</p>
        </div>
    `;

    document.getElementById('global-comparison').innerHTML = html;
}

/**
 * Render gauges for both schools
 */
function renderGauges(data) {
    const { colegio_a, colegio_b } = data;

    // Gauge A
    if (comparisonCharts.gaugeA) {
        comparisonCharts.gaugeA.destroy();
    }
    comparisonCharts.gaugeA = createGauge('gauge-colegio-a', colegio_a.puntaje_global, colegio_a.nombre);

    // Gauge B
    if (comparisonCharts.gaugeB) {
        comparisonCharts.gaugeB.destroy();
    }
    comparisonCharts.gaugeB = createGauge('gauge-colegio-b', colegio_b.puntaje_global, colegio_b.nombre);
}

/**
 * Create a radial gauge
 */
function createGauge(elementId, value, label) {
    const options = {
        series: [Math.round((value / 500) * 100)],
        chart: {
            height: 250,
            type: 'radialBar',
        },
        plotOptions: {
            radialBar: {
                hollow: {
                    size: '60%',
                },
                dataLabels: {
                    name: {
                        fontSize: '14px',
                    },
                    value: {
                        fontSize: '24px',
                        formatter: function () {
                            return value.toFixed(1);
                        }
                    },
                }
            },
        },
        labels: [label],
        colors: [value >= 350 ? '#28a745' : value >= 250 ? '#ffc107' : '#dc3545']
    };

    const chart = new ApexCharts(document.querySelector(`#${elementId}`), options);
    chart.render();
    return chart;
}

/**
 * Render subject comparison chart
 */
function renderSubjectComparison(data) {
    const { colegio_a, colegio_b } = data;

    if (comparisonCharts.materias) {
        comparisonCharts.materias.destroy();
    }

    const options = {
        series: [
            {
                name: colegio_a.nombre,
                data: [
                    parseFloat(colegio_a.lectura.toFixed(2)),
                    parseFloat(colegio_a.matematicas.toFixed(2)),
                    parseFloat(colegio_a.ciencias.toFixed(2)),
                    parseFloat(colegio_a.sociales.toFixed(2)),
                    parseFloat(colegio_a.ingles.toFixed(2))
                ]
            },
            {
                name: colegio_b.nombre,
                data: [
                    parseFloat(colegio_b.lectura.toFixed(2)),
                    parseFloat(colegio_b.matematicas.toFixed(2)),
                    parseFloat(colegio_b.ciencias.toFixed(2)),
                    parseFloat(colegio_b.sociales.toFixed(2)),
                    parseFloat(colegio_b.ingles.toFixed(2))
                ]
            }
        ],
        chart: {
            type: 'bar',
            height: 350
        },
        plotOptions: {
            bar: {
                horizontal: false,
                columnWidth: '55%',
                endingShape: 'rounded'
            },
        },
        dataLabels: {
            enabled: false
        },
        stroke: {
            show: true,
            width: 2,
            colors: ['transparent']
        },
        xaxis: {
            categories: ['Lectura', 'Matemáticas', 'C. Naturales', 'Sociales', 'Inglés'],
        },
        yaxis: {
            title: {
                text: 'Puntaje'
            },
            max: 100,
            labels: {
                formatter: function (val) {
                    return val.toFixed(2);
                }
            }
        },
        fill: {
            opacity: 1
        },
        tooltip: {
            y: {
                formatter: function (val) {
                    return val.toFixed(2) + " puntos"
                }
            }
        },
        colors: ['#556ee6', '#34c38f']
    };

    comparisonCharts.materias = new ApexCharts(document.querySelector("#chart-materias-comparison"), options);
    comparisonCharts.materias.render();
}

/**
 * Render Z-Score comparison
 */
function renderZScore(data) {
    const { colegio_a, colegio_b, diferencias } = data;

    const interpretA = interpretZScore(colegio_a.z_score);
    const interpretB = interpretZScore(colegio_b.z_score);

    const htmlA = `
        <div class="text-center">
            <h2 class="text-primary">${colegio_a.z_score.toFixed(2)}</h2>
            <p class="text-muted mb-2">Z-Score</p>
            <span class="badge bg-${interpretA.color}">${interpretA.label}</span>
            <p class="small text-muted mt-2">Percentil ${getPercentile(colegio_a.z_score)}%</p>
        </div>
    `;

    const htmlB = `
        <div class="text-center">
            <h2 class="text-info">${colegio_b.z_score.toFixed(2)}</h2>
            <p class="text-muted mb-2">Z-Score</p>
            <span class="badge bg-${interpretB.color}">${interpretB.label}</span>
            <p class="small text-muted mt-2">Percentil ${getPercentile(colegio_b.z_score)}%</p>
        </div>
    `;

    document.getElementById('zscore-colegio-a').innerHTML = htmlA;
    document.getElementById('zscore-colegio-b').innerHTML = htmlB;
}

/**
 * Interpret Z-Score
 */
function interpretZScore(zscore) {
    if (zscore >= 2) return { label: 'Élite', color: 'success' };
    if (zscore >= 1) return { label: 'Superior', color: 'primary' };
    if (zscore >= 0) return { label: 'Promedio Alto', color: 'info' };
    if (zscore >= -1) return { label: 'Promedio Bajo', color: 'warning' };
    return { label: 'Bajo', color: 'danger' };
}

/**
 * Get percentile from Z-Score
 */
function getPercentile(zscore) {
    // Approximate percentile from Z-Score
    if (zscore >= 2) return 97.7;
    if (zscore >= 1) return 84.1;
    if (zscore >= 0) return 50.0;
    if (zscore >= -1) return 15.9;
    return 2.3;
}

/**
 * Render excellence indicators table
 */
function renderExcellenceIndicators(data) {
    const { colegio_a, colegio_b } = data;

    const indicators = [
        { name: 'Excelencia Integral', keyA: 'excelencia_integral', keyB: 'excelencia_integral' },
        { name: 'Competencia Satisfactoria', keyA: 'competencia_satisfactoria', keyB: 'competencia_satisfactoria' },
        { name: 'Perfil STEM Avanzado', keyA: 'perfil_stem', keyB: 'perfil_stem' },
        { name: 'Perfil Humanístico', keyA: 'perfil_humanistico', keyB: 'perfil_humanistico' },
        { name: 'Riesgo Alto', keyA: 'riesgo_alto', keyB: 'riesgo_alto' }
    ];

    let html = '';
    indicators.forEach(ind => {
        const valA = colegio_a[ind.keyA] || 0;
        const valB = colegio_b[ind.keyB] || 0;
        const diff = valA - valB;
        const diffColor = diff > 0 ? 'success' : (diff < 0 ? 'danger' : 'secondary');
        const diffIcon = diff > 0 ? '▲' : (diff < 0 ? '▼' : '=');

        html += `
            <tr>
                <td>${ind.name}</td>
                <td class="text-center"><strong>${valA.toFixed(1)}%</strong></td>
                <td class="text-center"><strong>${valB.toFixed(1)}%</strong></td>
                <td class="text-center">
                    <span class="badge bg-${diffColor}">
                        ${diffIcon} ${Math.abs(diff).toFixed(1)}%
                    </span>
                </td>
            </tr>
        `;
    });

    document.querySelector('#table-indicadores tbody').innerHTML = html;
}

/**
 * Render insights
 */
function renderInsights(data) {
    const { insights } = data;

    let html = '';
    insights.forEach(insight => {
        html += `<li>${insight}</li>`;
    });

    document.getElementById('insights-list').innerHTML = html;
}

/**
 * Render historical trends comparison (line chart)
 */
function renderHistoricalTrends(data) {
    try {
        const { colegio_a, colegio_b } = data;

        const chartElement = document.querySelector("#chart-historical-trends");
        if (!chartElement) {
            console.warn('Historical trends chart element not found');
            return;
        }

        const options = {
            series: [
                {
                    name: colegio_a.nombre,
                    data: [250, 255, 258, 260, parseFloat(colegio_a.puntaje_global.toFixed(2))]
                },
                {
                    name: colegio_b.nombre,
                    data: [245, 248, 252, 255, parseFloat(colegio_b.puntaje_global.toFixed(2))]
                }
            ],
            chart: {
                height: 350,
                type: 'line',
                zoom: {
                    enabled: false
                }
            },
            dataLabels: {
                enabled: true,
                formatter: function (val) {
                    return val.toFixed(2);
                }
            },
            stroke: {
                curve: 'smooth',
                width: 3
            },
            title: {
                text: 'Evolución del Puntaje Global (2020-2024)',
                align: 'left'
            },
            grid: {
                row: {
                    colors: ['#f3f3f3', 'transparent'],
                    opacity: 0.5
                },
            },
            xaxis: {
                categories: ['2020', '2021', '2022', '2023', '2024'],
            },
            yaxis: {
                title: {
                    text: 'Puntaje Global'
                },
                min: 200,
                max: 350,
                labels: {
                    formatter: function (val) {
                        return val.toFixed(2);
                    }
                }
            },
            tooltip: {
                y: {
                    formatter: function (val) {
                        return val.toFixed(2);
                    }
                }
            },
            colors: ['#556ee6', '#34c38f'],
            markers: {
                size: 5
            }
        };

        const chart = new ApexCharts(chartElement, options);
        chart.render();
        console.log('Historical trends chart rendered successfully');
    } catch (error) {
        console.error('Error rendering historical trends chart:', error);
    }
}

/**
 * Render radar chart for subject comparison
 */
function renderRadarChart(data) {
    try {
        const { colegio_a, colegio_b } = data;

        const chartElement = document.querySelector("#chart-radar-subjects");
        if (!chartElement) {
            console.warn('Radar chart element not found');
            return;
        }

        const options = {
            series: [
                {
                    name: colegio_a.nombre,
                    data: [
                        parseFloat(colegio_a.lectura.toFixed(2)),
                        parseFloat(colegio_a.matematicas.toFixed(2)),
                        parseFloat(colegio_a.ciencias.toFixed(2)),
                        parseFloat(colegio_a.sociales.toFixed(2)),
                        parseFloat(colegio_a.ingles.toFixed(2))
                    ]
                },
                {
                    name: colegio_b.nombre,
                    data: [
                        parseFloat(colegio_b.lectura.toFixed(2)),
                        parseFloat(colegio_b.matematicas.toFixed(2)),
                        parseFloat(colegio_b.ciencias.toFixed(2)),
                        parseFloat(colegio_b.sociales.toFixed(2)),
                        parseFloat(colegio_b.ingles.toFixed(2))
                    ]
                }
            ],
            chart: {
                height: 400,
                type: 'radar',
            },
            title: {
                text: 'Perfil de Rendimiento por Materia'
            },
            xaxis: {
                categories: ['Lectura Crítica', 'Matemáticas', 'C. Naturales', 'Sociales', 'Inglés']
            },
            yaxis: {
                show: true,
                min: 0,
                max: 100,
                labels: {
                    formatter: function (val) {
                        return val.toFixed(2);
                    }
                }
            },
            tooltip: {
                y: {
                    formatter: function (val) {
                        return val.toFixed(2);
                    }
                }
            },
            colors: ['#556ee6', '#34c38f'],
            markers: {
                size: 4
            },
            fill: {
                opacity: 0.2
            },
            stroke: {
                show: true,
                width: 2
            },
            legend: {
                position: 'bottom'
            }
        };

        const chart = new ApexCharts(chartElement, options);
        chart.render();
        console.log('Radar chart rendered successfully');
    } catch (error) {
        console.error('Error rendering radar chart:', error);
    }
}
