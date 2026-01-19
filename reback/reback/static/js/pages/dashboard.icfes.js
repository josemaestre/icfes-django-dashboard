/**
 * Theme: Reback - Responsive Bootstrap 5 Admin Dashboard
 * Module/App: ICFES Dashboard
 */

// Global variables
let currentYear = 2024;
let charts = {};

// Color palette matching Reback theme
const colors = {
    primary: '#7f56da',
    success: '#22c55e',
    danger: '#ef4444',
    warning: '#f59e0b',
    info: '#3b82f6',
    purple: '#8b5cf6',
    pink: '#ec4899',
    teal: '#14b8a6',
};

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function () {
    loadStats();
    loadTendenciasChart();
    loadSectoresChart();
    loadDepartamentosChart();
    loadRegionalChart();
    loadColegiosTable();

    // Year selector event listener
    document.getElementById('year-selector').addEventListener('change', function () {
        currentYear = this.value;
        document.getElementById('year-display').textContent = currentYear;
        document.getElementById('table-year').textContent = currentYear;
        loadStats();
        loadSectoresChart();
        loadDepartamentosChart();
        loadRegionalChart();
        loadColegiosTable();
    });
});

// Load statistics (KPI cards)
async function loadStats() {
    try {
        const data = await window.apiCache.fetch(`/icfes/api/estadisticas/?ano=${currentYear}`);

        document.getElementById('stat-estudiantes').textContent = data.total_estudiantes.toLocaleString();
        document.getElementById('stat-colegios').textContent = data.total_colegios.toLocaleString();
        document.getElementById('stat-promedio').textContent = data.promedio_nacional.toFixed(1);
        document.getElementById('stat-departamentos').textContent = data.total_departamentos;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load national trends chart (line chart with dual Y-axis)
async function loadTendenciasChart() {
    try {
        const response = await fetch('/icfes/api/charts/tendencias/');
        const data = await response.json();

        const options = {
            series: [
                {
                    name: 'Global',
                    data: data.map(d => d.punt_global),
                    type: 'line'
                },
                {
                    name: 'Matemáticas',
                    data: data.map(d => d.punt_matematicas),
                    type: 'line'
                },
                {
                    name: 'Lectura',
                    data: data.map(d => d.punt_lectura),
                    type: 'line'
                },
                {
                    name: 'C. Naturales',
                    data: data.map(d => d.punt_c_naturales),
                    type: 'line'
                },
                {
                    name: 'Sociales',
                    data: data.map(d => d.punt_sociales),
                    type: 'line'
                },
                {
                    name: 'Inglés',
                    data: data.map(d => d.punt_ingles),
                    type: 'line'
                }
            ],
            chart: {
                height: 350,
                type: 'line',
                toolbar: {
                    show: false,
                },
            },
            stroke: {
                width: [3, 2, 2, 2, 2, 2],
                curve: 'smooth'
            },
            xaxis: {
                categories: data.map(d => d.ano),
                axisTicks: {
                    show: false,
                },
                axisBorder: {
                    show: false,
                },
            },
            yaxis: [
                {
                    // Y-axis for Global (0-500 scale)
                    seriesName: 'Global',
                    min: 200,
                    max: 300,
                    tickAmount: 5,
                    labels: {
                        offsetX: -15,
                        formatter: function (val) {
                            return val.toFixed(0);
                        }
                    },
                    title: {
                        text: 'Puntaje Global',
                        style: {
                            color: colors.primary
                        }
                    },
                    axisBorder: {
                        show: true,
                        color: colors.primary
                    }
                },
                {
                    // Y-axis for Subjects (0-100 scale)
                    opposite: true,
                    seriesName: 'Matemáticas',
                    min: 40,
                    max: 70,
                    tickAmount: 5,
                    labels: {
                        offsetX: 15,
                        formatter: function (val) {
                            return val.toFixed(0);
                        }
                    },
                    title: {
                        text: 'Puntaje Materias',
                        style: {
                            color: colors.success
                        }
                    },
                    axisBorder: {
                        show: true,
                        color: colors.success
                    }
                }
            ],
            grid: {
                show: true,
                strokeDashArray: 3,
                xaxis: {
                    lines: {
                        show: false,
                    },
                },
                yaxis: {
                    lines: {
                        show: true,
                    },
                },
                padding: {
                    top: -10,
                    right: -2,
                    bottom: -10,
                    left: -5,
                },
            },
            colors: [colors.primary, colors.danger, colors.success, colors.warning, colors.info, colors.purple],
            legend: {
                show: true,
                position: 'bottom',
                horizontalAlign: 'center',
            },
            tooltip: {
                shared: true,
                intersect: false,
                y: {
                    formatter: function (val, opts) {
                        if (opts.seriesIndex === 0) {
                            return val.toFixed(1) + ' (Global)';
                        }
                        return val.toFixed(1) + ' (Materia)';
                    }
                }
            },
        };

        if (charts.tendencias) charts.tendencias.destroy();
        charts.tendencias = new ApexCharts(document.querySelector("#chart-tendencias"), options);
        charts.tendencias.render();
    } catch (error) {
        console.error('Error loading tendencias chart:', error);
    }
}

// Load sectors comparison chart (bar chart - subjects only)
async function loadSectoresChart() {
    try {
        const response = await fetch(`/icfes/api/charts/sectores/?ano=${currentYear}`);
        const data = await response.json();

        // Only show subject scores (0-100 scale), exclude Global
        const materias = ['punt_matematicas', 'punt_lectura', 'punt_c_naturales', 'punt_sociales', 'punt_ingles'];
        const labels = ['Matemáticas', 'Lectura', 'C. Naturales', 'Sociales', 'Inglés'];

        const options = {
            series: data.map((sector, idx) => ({
                name: sector.sector,
                data: materias.map(m => sector[m])
            })),
            chart: {
                type: 'bar',
                height: 350,
                toolbar: {
                    show: false,
                },
            },
            plotOptions: {
                bar: {
                    horizontal: false,
                    columnWidth: '55%',
                    borderRadius: 3,
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
                categories: labels,
                axisTicks: {
                    show: false,
                },
                axisBorder: {
                    show: false,
                },
            },
            yaxis: {
                min: 40,
                max: 70,
                tickAmount: 6,
                labels: {
                    offsetX: -15,
                    formatter: function (val) {
                        return val.toFixed(0);
                    }
                },
                title: {
                    text: 'Puntaje (0-100)'
                }
            },
            fill: {
                opacity: 1
            },
            colors: [colors.primary, colors.success],
            grid: {
                show: true,
                strokeDashArray: 3,
                padding: {
                    top: -10,
                    right: 0,
                    bottom: -10,
                    left: 0
                },
            },
            legend: {
                show: true,
                position: 'top',
            },
            tooltip: {
                y: {
                    formatter: function (val) {
                        return val.toFixed(1) + ' pts';
                    }
                }
            }
        };

        if (charts.sectores) charts.sectores.destroy();
        charts.sectores = new ApexCharts(document.querySelector("#chart-sectores"), options);
        charts.sectores.render();
    } catch (error) {
        console.error('Error loading sectores chart:', error);
    }
}

// Load departments ranking chart (horizontal bar chart)
async function loadDepartamentosChart() {
    try {
        const response = await fetch(`/icfes/api/charts/departamentos/?ano=${currentYear}&limit=10`);
        const data = await response.json();

        const options = {
            series: [{
                name: 'Promedio',
                data: data.map(d => d.promedio)
            }],
            chart: {
                type: 'bar',
                height: 350,
                toolbar: {
                    show: false,
                },
            },
            plotOptions: {
                bar: {
                    borderRadius: 3,
                    horizontal: true,
                    distributed: true,
                }
            },
            dataLabels: {
                enabled: false
            },
            xaxis: {
                categories: data.map(d => d.departamento),
                min: 240,
                max: 280,
            },
            yaxis: {
                labels: {
                    style: {
                        fontSize: '12px'
                    }
                }
            },
            colors: data.map((_, idx) => {
                if (idx < 3) return colors.success;
                if (idx < 7) return colors.info;
                return colors.warning;
            }),
            grid: {
                show: true,
                strokeDashArray: 3,
            },
            legend: {
                show: false
            },
            tooltip: {
                y: {
                    formatter: function (val) {
                        return val.toFixed(1);
                    }
                }
            }
        };

        if (charts.departamentos) charts.departamentos.destroy();
        charts.departamentos = new ApexCharts(document.querySelector("#chart-departamentos"), options);
        charts.departamentos.render();
    } catch (error) {
        console.error('Error loading departamentos chart:', error);
    }
}

// Load regional distribution chart (donut chart)
async function loadRegionalChart() {
    try {
        const response = await fetch(`/icfes/api/charts/regional/?ano=${currentYear}`);
        const data = await response.json();

        const options = {
            chart: {
                height: 300,
                type: 'donut',
            },
            series: data.map(d => d.total_estudiantes),
            labels: data.map(d => d.region),
            colors: [colors.primary, colors.success, colors.warning, colors.danger, colors.info],
            legend: {
                show: true,
                position: 'bottom',
                horizontalAlign: 'center',
                offsetX: 0,
                offsetY: -5,
                markers: {
                    width: 9,
                    height: 9,
                    radius: 6,
                },
                itemMargin: {
                    horizontal: 10,
                    vertical: 0,
                },
            },
            stroke: {
                width: 0
            },
            plotOptions: {
                pie: {
                    donut: {
                        size: '70%',
                        labels: {
                            show: true,
                            total: {
                                showAlways: true,
                                show: true,
                                label: 'Total',
                                formatter: function (w) {
                                    return w.globals.seriesTotals.reduce((a, b) => a + b, 0).toLocaleString();
                                }
                            }
                        }
                    }
                }
            },
            dataLabels: {
                enabled: false
            },
            tooltip: {
                y: {
                    formatter: function (val) {
                        return val.toLocaleString() + ' estudiantes';
                    }
                }
            }
        };

        if (charts.regional) charts.regional.destroy();
        charts.regional = new ApexCharts(document.querySelector("#chart-regional"), options);
        charts.regional.render();
    } catch (error) {
        console.error('Error loading regional chart:', error);
    }
}

// Load top schools table
async function loadColegiosTable() {
    try {
        const response = await fetch(`/icfes/api/colegios/destacados/?ano=${currentYear}&limit=50`);
        const data = await response.json();

        const tbody = document.getElementById('table-colegios-body');
        tbody.innerHTML = '';

        data.forEach((colegio, idx) => {
            const row = document.createElement('tr');

            let badgeClass = 'bg-secondary';
            if (idx < 3) badgeClass = 'bg-success';
            else if (idx < 10) badgeClass = 'bg-info';
            else if (idx < 25) badgeClass = 'bg-primary';

            const sectorBadge = colegio.sector === 'NO OFICIAL'
                ? 'bg-warning-subtle text-warning'
                : 'bg-primary-subtle text-primary';

            row.innerHTML = `
                <td><span class="badge ${badgeClass} p-1">#${colegio.ranking_nacional}</span></td>
                <td><strong>${colegio.nombre_colegio}</strong></td>
                <td>${colegio.departamento}</td>
                <td>${colegio.municipio}</td>
                <td><span class="badge ${sectorBadge} p-1">${colegio.sector}</span></td>
                <td><strong>${colegio.avg_punt_global.toFixed(1)}</strong></td>
                <td>${colegio.total_estudiantes}</td>
            `;

            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading colegios table:', error);
        document.getElementById('table-colegios-body').innerHTML =
            '<tr><td colspan="7" class="text-center text-danger py-4">Error al cargar datos</td></tr>';
    }
}

// ============================================================================
// HIERARCHICAL TABLE FUNCTIONALITY
// ============================================================================

// Expandable table state
const expandedRows = new Set();
let hierarchyYear = 2024;

// Initialize hierarchy year selector
document.addEventListener('DOMContentLoaded', function () {
    const hierarchyYearSelector = document.getElementById('hierarchy-year-selector');
    if (hierarchyYearSelector) {
        hierarchyYearSelector.addEventListener('change', function () {
            hierarchyYear = this.value;
            loadHierarchicalTable();
        });
    }

    // Load table when tab is shown
    const explorerTab = document.querySelector('a[href="#explorador"]');
    if (explorerTab) {
        explorerTab.addEventListener('shown.bs.tab', function () {
            if (document.getElementById('hierarchical-tbody').children.length <= 1) {
                loadHierarchicalTable();
            }
        });
    }
});

// Load initial regions
async function loadHierarchicalTable() {
    const tbody = document.getElementById('hierarchical-tbody');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="11" class="text-center py-4"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando...</span></div></td></tr>';

    try {
        const response = await fetch(`/icfes/api/hierarchy/regions/?ano=${hierarchyYear}`);
        const regions = await response.json();

        tbody.innerHTML = '';
        expandedRows.clear();

        regions.forEach(region => {
            tbody.appendChild(createRegionRow(region));
        });
    } catch (error) {
        console.error('Error loading hierarchical table:', error);
        tbody.innerHTML = '<tr><td colspan="11" class="text-center text-danger py-4">Error al cargar datos</td></tr>';
    }
}

// Create region row
function createRegionRow(region) {
    const row = document.createElement('tr');
    row.className = 'hierarchy-level-0';
    row.dataset.level = 'region';
    row.dataset.id = region.region;

    const trend = getTrendIcon(region.cambio_anual || 0);
    const zScore = (region.z_score || 0).toFixed(2);
    const percentil = Math.round(region.percentil || 0);

    row.innerHTML = `
        <td>
            <a href="#" class="expand-toggle" data-level="region" data-id="${region.region}">
                <i class="bx bx-plus-circle"></i>
                <strong>${region.region}</strong>
            </a>
        </td>
        <td class="text-end"><strong>${region.punt_global.toFixed(1)}</strong></td>
        <td class="text-end">${region.punt_matematicas.toFixed(1)}</td>
        <td class="text-end">${region.punt_lectura.toFixed(1)}</td>
        <td class="text-end">${region.punt_c_naturales.toFixed(1)}</td>
        <td class="text-end">${region.punt_sociales.toFixed(1)}</td>
        <td class="text-end">${region.punt_ingles.toFixed(1)}</td>
        <td class="text-center"><span class="badge bg-primary">#${region.ranking}</span></td>
        <td class="text-center">${trend}</td>
        <td class="text-center"><span class="badge ${getZScoreBadge(zScore)}">${zScore}</span></td>
        <td class="text-center">${percentil}%</td>
    `;

    // Add click handler
    const toggle = row.querySelector('.expand-toggle');
    toggle.addEventListener('click', async (e) => {
        e.preventDefault();
        await toggleExpand('region', region.region, row);
    });

    return row;
}

// Toggle expand/collapse
async function toggleExpand(level, id, parentRow) {
    const key = `${level}-${id}`;

    if (expandedRows.has(key)) {
        // Collapse: remove child rows
        collapseChildren(parentRow);
        expandedRows.delete(key);
        parentRow.querySelector('.expand-toggle i').className = 'bx bx-plus-circle';
    } else {
        // Expand: load and insert child rows
        const toggle = parentRow.querySelector('.expand-toggle i');
        toggle.className = 'bx bx-loader bx-spin';

        try {
            const children = await loadChildren(level, id);
            insertChildren(parentRow, children, level);
            expandedRows.add(key);
            toggle.className = 'bx bx-minus-circle';
        } catch (error) {
            console.error('Error expanding row:', error);
            toggle.className = 'bx bx-plus-circle';
        }
    }
}

// Load children based on level
async function loadChildren(level, id) {
    let endpoint;
    const encodedId = encodeURIComponent(id);

    switch (level) {
        case 'region':
            endpoint = `/icfes/api/hierarchy/departments/?region=${encodedId}&ano=${hierarchyYear}`;
            break;
        case 'department':
            endpoint = `/icfes/api/hierarchy/municipalities/?department=${encodedId}&ano=${hierarchyYear}`;
            break;
        case 'municipality':
            endpoint = `/icfes/api/hierarchy/schools/?municipality=${encodedId}&ano=${hierarchyYear}`;
            break;
        default:
            return [];
    }

    const response = await fetch(endpoint);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
}

// Insert child rows
function insertChildren(parentRow, children, parentLevel) {
    const childLevel = getChildLevel(parentLevel);
    const indentLevel = getIndentLevel(childLevel);

    let insertAfter = parentRow;
    children.forEach((child) => {
        const childRow = createChildRow(child, childLevel, indentLevel);
        insertAfter.after(childRow);
        insertAfter = childRow;
    });
}

// Create child row (department, municipality, or school)
function createChildRow(data, level, indentLevel) {
    const row = document.createElement('tr');
    row.className = `hierarchy-level-${indentLevel} hierarchy-child`;
    row.dataset.level = level;
    row.dataset.id = data.id || data.nombre;

    const trend = getTrendIcon(data.cambio_anual || 0);
    const zScore = (data.z_score || 0).toFixed(2);
    const percentil = Math.round(data.percentil || 0);
    const hasChildren = level !== 'school';

    const expandIcon = hasChildren
        ? `<a href="#" class="expand-toggle" data-level="${level}" data-id="${data.id || data.nombre}">
             <i class="bx bx-plus-circle"></i>
           </a>`
        : '<i class="bx bx-circle" style="opacity:0.3; font-size:12px;"></i>';

    row.innerHTML = `
        <td style="padding-left: ${indentLevel * 20 + 10}px">
            ${expandIcon}
            ${data.nombre}
        </td>
        <td class="text-end">${data.punt_global.toFixed(1)}</td>
        <td class="text-end">${data.punt_matematicas.toFixed(1)}</td>
        <td class="text-end">${data.punt_lectura.toFixed(1)}</td>
        <td class="text-end">${data.punt_c_naturales.toFixed(1)}</td>
        <td class="text-end">${data.punt_sociales.toFixed(1)}</td>
        <td class="text-end">${data.punt_ingles.toFixed(1)}</td>
        <td class="text-center"><span class="badge bg-secondary">#${data.ranking}</span></td>
        <td class="text-center">${trend}</td>
        <td class="text-center"><span class="badge ${getZScoreBadge(zScore)}">${zScore}</span></td>
        <td class="text-center">${percentil}%</td>
    `;

    if (hasChildren) {
        const toggle = row.querySelector('.expand-toggle');
        toggle.addEventListener('click', async (e) => {
            e.preventDefault();
            await toggleExpand(level, data.id || data.nombre, row);
        });
    }

    return row;
}

// Collapse all children recursively
function collapseChildren(parentRow) {
    let nextRow = parentRow.nextElementSibling;

    while (nextRow && nextRow.classList.contains('hierarchy-child')) {
        const toRemove = nextRow;
        nextRow = nextRow.nextElementSibling;

        // Remove from expanded set if it was expanded
        const key = `${toRemove.dataset.level}-${toRemove.dataset.id}`;
        expandedRows.delete(key);

        toRemove.remove();
    }
}

// Helper functions
function getTrendIcon(cambio) {
    const val = parseFloat(cambio);
    if (isNaN(val)) return '<span class="text-muted">--</span>';
    if (val > 1) return `<span class="text-success">⬆️ +${val.toFixed(1)}%</span>`;
    if (val < -1) return `<span class="text-danger">⬇️ ${val.toFixed(1)}%</span>`;
    return `<span class="text-muted">➡️ ${val.toFixed(1)}%</span>`;
}

function getZScoreBadge(zScore) {
    const val = parseFloat(zScore);
    if (isNaN(val)) return 'bg-secondary';
    if (val > 1) return 'bg-success';
    if (val < -1) return 'bg-danger';
    return 'bg-warning';
}

function getChildLevel(parentLevel) {
    const levels = {
        region: 'department',
        department: 'municipality',
        municipality: 'school'
    };
    return levels[parentLevel];
}

function getIndentLevel(level) {
    const indents = {
        region: 0,
        department: 1,
        municipality: 2,
        school: 3
    };
    return indents[level] || 0;
}

