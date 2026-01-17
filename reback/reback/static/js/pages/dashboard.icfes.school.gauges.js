/**
 * Theme: Reback - Responsive Bootstrap 5 Admin Dashboard
 * Module/App: ICFES Dashboard - School Gauges
 */

// ============================================================================
// SCHOOL PERFORMANCE GAUGES FUNCTIONALITY
// ============================================================================

// Store school gauge chart instances
let schoolGaugeCharts = {
    global: null,
    lectura: null,
    matematicas: null,
    ciencias: null,
    sociales: null,
    ingles: null
};

// Initialize school gauges when a school is selected
function initializeSchoolGauges(schoolData) {
    // Create gauges if they don't exist
    if (!schoolGaugeCharts.global) {
        schoolGaugeCharts.global = createSchoolGlobalGauge(0);
        schoolGaugeCharts.lectura = createSchoolSubjectGauge('#school-gauge-lectura', 0, '#6f42c1');
        schoolGaugeCharts.matematicas = createSchoolSubjectGauge('#school-gauge-matematicas', 0, '#007bff');
        schoolGaugeCharts.ciencias = createSchoolSubjectGauge('#school-gauge-ciencias', 0, '#28a745');
        schoolGaugeCharts.sociales = createSchoolSubjectGauge('#school-gauge-sociales', 0, '#fd7e14');
        schoolGaugeCharts.ingles = createSchoolSubjectGauge('#school-gauge-ingles', 0, '#17a2b8');
    }

    // Update gauges with school data
    updateSchoolGauges(schoolData);
}

// Create school global score gauge (0-500)
function createSchoolGlobalGauge(score) {
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
        colors: [getSchoolColorByScore(score)],
        series: [percentage],
        labels: ['Puntaje Global'],
        responsive: [{
            breakpoint: 380,
            options: {
                chart: {
                    height: 220
                }
            }
        }]
    };

    const chart = new ApexCharts(document.querySelector("#school-gauge-global"), options);
    chart.render();
    return chart;
}

// Create school subject gauge (0-100)
function createSchoolSubjectGauge(elementId, score, color) {
    const options = {
        chart: {
            height: 140,
            type: 'radialBar',
        },
        plotOptions: {
            radialBar: {
                startAngle: -135,
                endAngle: 135,
                hollow: {
                    size: '60%'
                },
                dataLabels: {
                    name: {
                        show: false
                    },
                    value: {
                        offsetY: 5,
                        fontSize: '16px',
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
        responsive: [{
            breakpoint: 380,
            options: {
                chart: {
                    height: 120
                }
            }
        }]
    };

    const chart = new ApexCharts(document.querySelector(elementId), options);
    chart.render();
    return chart;
}

// Update school gauges with data
function updateSchoolGauges(schoolData) {
    // Extract scores - using correct field names from API
    const globalScore = schoolData.colegio_global || 0;
    const lecturaScore = schoolData.colegio_lectura || 0;
    const matematicasScore = schoolData.colegio_matematicas || 0;
    const cienciasScore = schoolData.colegio_c_naturales || 0;
    const socialesScore = schoolData.colegio_sociales || 0;
    const inglesScore = schoolData.colegio_ingles || 0;

    // Extract comparison data
    const municipalGlobal = schoolData.promedio_municipal_global || 0;
    const departamentalGlobal = schoolData.promedio_departamental_global || 0;
    const nacionalGlobal = schoolData.promedio_nacional_global || 0;

    // Update global gauge
    updateSchoolGlobalGauge(globalScore, municipalGlobal, departamentalGlobal, nacionalGlobal);

    // Update subject gauges
    // Note: We don't have municipal/departmental data per subject from the API yet
    // So we'll just show the scores for now
    updateSchoolSubjectGauge('lectura', lecturaScore);
    updateSchoolSubjectGauge('matematicas', matematicasScore);
    updateSchoolSubjectGauge('ciencias', cienciasScore);
    updateSchoolSubjectGauge('sociales', socialesScore);
    updateSchoolSubjectGauge('ingles', inglesScore);
}

// Update school global gauge
function updateSchoolGlobalGauge(score, municipalAvg, departamentalAvg, nacionalAvg) {
    const percentage = (score / 500) * 100;

    // Update chart
    if (schoolGaugeCharts.global) {
        schoolGaugeCharts.global.updateOptions({
            colors: [getSchoolColorByScore(score)],
            series: [percentage]
        });
    }

    // Update text value
    document.getElementById('school-gauge-global-actual').textContent = score.toFixed(1);

    // Update comparison
    const comparisonHTML = showSchoolComparison(score, municipalAvg, departamentalAvg, nacionalAvg);
    document.getElementById('school-gauge-global-comparison').innerHTML = comparisonHTML;
}

// Update school subject gauge
function updateSchoolSubjectGauge(subject, score) {
    if (schoolGaugeCharts[subject]) {
        schoolGaugeCharts[subject].updateSeries([score]);
    }

    // Update value text
    const valueElement = document.getElementById(`school-gauge-${subject}-value`);
    if (valueElement) {
        valueElement.textContent = score.toFixed(1);
    }
}

// Show comparison badges for school
function showSchoolComparison(schoolScore, municipalScore, departamentalScore, nacionalScore) {
    let html = '';

    if (municipalScore > 0) {
        const diffMunicipal = schoolScore - municipalScore;
        const classMunicipal = diffMunicipal >= 0 ? 'text-success' : 'text-danger';
        const iconMunicipal = diffMunicipal >= 0 ? '▲' : '▼';
        html += `<small class="${classMunicipal}">vs Municipal: ${iconMunicipal} ${Math.abs(diffMunicipal).toFixed(1)} pts</small><br>`;
    }

    if (departamentalScore > 0) {
        const diffDepartamental = schoolScore - departamentalScore;
        const classDepartamental = diffDepartamental >= 0 ? 'text-success' : 'text-danger';
        const iconDepartamental = diffDepartamental >= 0 ? '▲' : '▼';
        html += `<small class="${classDepartamental}">vs Departamental: ${iconDepartamental} ${Math.abs(diffDepartamental).toFixed(1)} pts</small><br>`;
    }

    if (nacionalScore > 0) {
        const diffNacional = schoolScore - nacionalScore;
        const classNacional = diffNacional >= 0 ? 'text-success' : 'text-danger';
        const iconNacional = diffNacional >= 0 ? '▲' : '▼';
        html += `<small class="${classNacional}">vs Nacional: ${iconNacional} ${Math.abs(diffNacional).toFixed(1)} pts</small>`;
    }

    return html;
}

// Get color based on score (for global gauge)
function getSchoolColorByScore(score) {
    if (score < 250) return '#dc3545'; // Red
    if (score < 350) return '#ffc107'; // Yellow
    if (score < 450) return '#28a745'; // Green
    return '#007bff'; // Blue
}
