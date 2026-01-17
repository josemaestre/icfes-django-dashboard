/**
 * Theme: Reback - Responsive Bootstrap 5 Admin Dashboard
 * Module/App: ICFES Dashboard - Gauges
 */

// ============================================================================
// PERFORMANCE GAUGES FUNCTIONALITY
// ============================================================================

// Store gauge chart instances
let gaugeCharts = {
    global: null,
    lectura: null,
    matematicas: null,
    ciencias: null,
    sociales: null,
    ingles: null
};

// Store location data for comparison
let locationData = null;
let currentLocation = 'nacional';

// Initialize gauges on page load
document.addEventListener('DOMContentLoaded', function () {
    initializeGauges();
    loadGaugeData();

    // Update gauges when year changes
    const yearSelector = document.getElementById('year-selector');
    if (yearSelector) {
        yearSelector.addEventListener('change', function () {
            loadGaugeData();
        });
    }

    // Update gauges when location changes
    const locationSelector = document.getElementById('location-selector');
    if (locationSelector) {
        locationSelector.addEventListener('change', function () {
            currentLocation = this.value;
            loadGaugeData();
        });
    }
});

// Initialize all gauge charts
function initializeGauges() {
    // Create global gauge (0-500 scale)
    gaugeCharts.global = createGlobalGauge(0);

    // Create subject gauges (0-100 scale)
    gaugeCharts.lectura = createSubjectGauge('#gauge-lectura', 0, '#6f42c1');
    gaugeCharts.matematicas = createSubjectGauge('#gauge-matematicas', 0, '#007bff');
    gaugeCharts.ciencias = createSubjectGauge('#gauge-ciencias', 0, '#28a745');
    gaugeCharts.sociales = createSubjectGauge('#gauge-sociales', 0, '#fd7e14');
    gaugeCharts.ingles = createSubjectGauge('#gauge-ingles', 0, '#17a2b8');
}

// Create global score gauge (0-500)
function createGlobalGauge(score) {
    const percentage = (score / 500) * 100;

    const options = {
        chart: {
            height: 280,
            type: 'radialBar',
        },
        plotOptions: {
            radialBar: {
                startAngle: -135,
                endAngle: 135,
                dataLabels: {
                    name: {
                        fontSize: '14px',
                        color: '#888',
                        offsetY: 100
                    },
                    value: {
                        offsetY: 50,
                        fontSize: '28px',
                        fontWeight: 'bold',
                        formatter: function (val) {
                            return Math.round((val / 100) * 500);
                        }
                    }
                },
                track: {
                    background: "rgba(170,184,197, 0.2)",
                    strokeWidth: '100%',
                },
            }
        },
        fill: {
            type: 'gradient',
            gradient: {
                shade: 'dark',
                type: 'horizontal',
                shadeIntensity: 0.5,
                gradientToColors: ['#22c55e'],
                inverseColors: true,
                opacityFrom: 1,
                opacityTo: 1,
                stops: [0, 100]
            }
        },
        stroke: {
            dashArray: 4
        },
        colors: [getColorByScore(score)],
        series: [percentage],
        labels: ['Puntaje Global'],
        annotations: {
            points: []
        },
        responsive: [{
            breakpoint: 380,
            options: {
                chart: {
                    height: 220
                }
            }
        }]
    };

    const chart = new ApexCharts(document.querySelector("#gauge-global"), options);
    chart.render();
    return chart;
}

// Create subject gauge (0-100)
function createSubjectGauge(elementId, score, color) {
    const options = {
        chart: {
            height: 180,
            type: 'radialBar',
        },
        plotOptions: {
            radialBar: {
                startAngle: -135,
                endAngle: 135,
                dataLabels: {
                    name: {
                        show: false
                    },
                    value: {
                        offsetY: 5,
                        fontSize: '18px',
                        fontWeight: 'bold',
                        formatter: function (val) {
                            return Math.round(val);
                        }
                    }
                },
                track: {
                    background: "rgba(170,184,197, 0.2)",
                    strokeWidth: '100%',
                },
            }
        },
        fill: {
            type: 'solid'
        },
        stroke: {
            dashArray: 4
        },
        colors: [color],
        series: [score],
        annotations: {
            points: []
        },
        responsive: [{
            breakpoint: 380,
            options: {
                chart: {
                    height: 140
                }
            }
        }]
    };

    const chart = new ApexCharts(document.querySelector(elementId), options);
    chart.render();
    return chart;
}

// Load gauge data from API
async function loadGaugeData() {
    try {
        const year = document.getElementById('year-selector')?.value || 2024;

        // Fetch global score from estadisticas API
        const statsResponse = await fetch(`/icfes/api/estadisticas/?ano=${year}`);
        const statsData = await statsResponse.json();

        // Fetch subject scores from tendencias API (get the data for the selected year)
        const tendenciasResponse = await fetch('/icfes/api/charts/tendencias/');
        const tendenciasData = await tendenciasResponse.json();

        // Find the data for the selected year
        const yearData = tendenciasData.find(d => d.ano == year);

        // Fetch location data if not nacional
        if (currentLocation !== 'nacional') {
            const locationResponse = await fetch(`/icfes/api/promedios-ubicacion/?ano=${year}&departamento=${encodeURIComponent(currentLocation)}`);
            locationData = await locationResponse.json();
        } else {
            locationData = null;
        }

        if (yearData) {
            // Update global gauge
            const globalScore = statsData.promedio_nacional || 0;
            const locationGlobalScore = locationData?.punt_global || null;
            updateGlobalGauge(globalScore, locationGlobalScore);

            // Update subject gauges with data from tendencias
            updateSubjectGauge('lectura', yearData.punt_lectura || 0, locationData?.punt_lectura || null);
            updateSubjectGauge('matematicas', yearData.punt_matematicas || 0, locationData?.punt_matematicas || null);
            updateSubjectGauge('ciencias', yearData.punt_c_naturales || 0, locationData?.punt_c_naturales || null);
            updateSubjectGauge('sociales', yearData.punt_sociales || 0, locationData?.punt_sociales || null);
            updateSubjectGauge('ingles', yearData.punt_ingles || 0, locationData?.punt_ingles || null);

            // Update location info text
            updateLocationInfo();
        } else {
            console.warn(`No data found for year ${year}`);
        }

    } catch (error) {
        console.error('Error loading gauge data:', error);
    }
}

// Update global gauge
function updateGlobalGauge(score, referenceScore = null) {
    const percentage = (score / 500) * 100;
    const meta = 400;
    const distance = meta - score;

    // Update chart
    if (gaugeCharts.global) {
        gaugeCharts.global.updateOptions({
            colors: [getColorByScore(score)],
            series: [percentage]
        });
    }

    // Update text values
    document.getElementById('gauge-global-actual').textContent = score.toFixed(1);

    // Update distance text with comparison if available
    let distanceHTML = '';
    if (distance > 0) {
        distanceHTML = `<span class="text-warning">Falta: ${distance.toFixed(1)} pts</span>`;
    } else {
        distanceHTML = `<span class="text-success">✓ Meta alcanzada!</span>`;
    }

    // Add comparison if location is selected
    if (referenceScore && currentLocation !== 'nacional') {
        const diff = score - referenceScore;
        const diffClass = diff >= 0 ? 'text-success' : 'text-danger';
        const diffIcon = diff >= 0 ? '▲' : '▼';
        distanceHTML += `<br><small class="${diffClass}">vs ${currentLocation}: ${diffIcon} ${Math.abs(diff).toFixed(1)} pts</small>`;
    }

    document.getElementById('gauge-global-distance').innerHTML = distanceHTML;
}

// Update subject gauge
function updateSubjectGauge(subject, score, referenceScore = null) {
    if (gaugeCharts[subject]) {
        gaugeCharts[subject].updateSeries([score]);
    }

    // Update value text with comparison
    const valueElement = document.getElementById(`gauge-${subject}-value`);
    if (valueElement) {
        let valueHTML = score.toFixed(1);

        // Add comparison if location is selected
        if (referenceScore && currentLocation !== 'nacional') {
            const diff = score - referenceScore;
            const diffClass = diff >= 0 ? 'text-success' : 'text-danger';
            const diffIcon = diff >= 0 ? '▲' : '▼';
            valueHTML += `<br><small class="${diffClass}">${diffIcon} ${Math.abs(diff).toFixed(1)}</small>`;
        }

        valueElement.innerHTML = valueHTML;
    }
}

// Update location info text
function updateLocationInfo() {
    const infoElement = document.getElementById('location-info');
    if (!infoElement) return;

    if (currentLocation === 'nacional') {
        infoElement.textContent = '';
    } else if (locationData) {
        const students = locationData.total_estudiantes || 0;
        infoElement.innerHTML = `<i class="bx bx-user"></i> ${students.toLocaleString()} estudiantes`;
    }
}

// Get color based on score (for global gauge)
function getColorByScore(score) {
    if (score < 250) return '#dc3545'; // Red
    if (score < 350) return '#ffc107'; // Yellow
    if (score < 450) return '#28a745'; // Green
    return '#007bff'; // Blue
}
