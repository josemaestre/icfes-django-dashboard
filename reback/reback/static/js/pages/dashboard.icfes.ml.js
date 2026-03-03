/**
 * Dashboard IA & Modelos ML
 * Fetches: /icfes/api/ml/shap/  /api/ml/social-clusters/  /api/ml/riesgo/  /api/ml/b1/
 */

const ML_URLS = {
    shap:     '/icfes/api/ml/shap/',
    clusters: '/icfes/api/ml/social-clusters/',
    riesgo:   '/icfes/api/ml/riesgo/',
    b1:       '/icfes/api/ml/b1/',
};

const CLUSTER_COLORS = [
    '#e63946','#f4a261','#2a9d8f','#457b9d','#6a4c93',
    '#264653','#e9c46a','#43aa8b',
];

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    loadShap();
    loadClusters();
    loadRiesgo();
    loadB1('OFICIAL');
});

// ---------------------------------------------------------------------------
// 1. SHAP importances + partial dependence estrato
// ---------------------------------------------------------------------------
async function loadShap() {
    try {
        const res = await fetch(ML_URLS.shap);
        const data = await res.json();

        if (data.pending || !data.importances || data.importances.length === 0) {
            document.getElementById('shap-pending-msg').classList.remove('d-none');
            document.getElementById('shap-charts-wrapper').classList.add('d-none');
            return;
        }

        // KPIs from first row
        const m = data.importances[0];
        document.getElementById('kpi-r2').textContent  = m.model_r2.toFixed(3);
        document.getElementById('kpi-mae').textContent = m.model_mae.toFixed(1) + ' pts';

        renderShapBar(data.importances);
        renderShapEstrato(data.partial_estrato);

    } catch (e) {
        console.warn('loadShap error:', e);
    }
}

function renderShapBar(importances) {
    const labels = importances.map(d => d.label);
    const values = importances.map(d => d.shap_pts);
    const colors = values.map((v, i) => i === 0 ? '#f4a261' : (i < 3 ? '#e9c46a' : '#adb5bd'));

    const options = {
        series: [{ name: 'Importancia SHAP (pts)', data: values }],
        chart: { type: 'bar', height: 340, toolbar: { show: false } },
        plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '65%' } },
        colors: colors,
        dataLabels: {
            enabled: true,
            formatter: v => v.toFixed(1) + ' pts',
            style: { fontSize: '11px', colors: ['#333'] },
            offsetX: 4,
        },
        xaxis: { categories: labels, labels: { style: { fontSize: '12px' } } },
        yaxis: { labels: { style: { fontSize: '11px' } } },
        tooltip: {
            y: { formatter: v => v.toFixed(2) + ' pts promedio' },
        },
        grid: { borderColor: '#f0f0f0' },
    };
    new ApexCharts(document.getElementById('chart-shap-bar'), options).render();
}

function renderShapEstrato(partial) {
    if (!partial || partial.length === 0) return;
    const labels = partial.map(d => d.estrato);
    const values = partial.map(d => d.puntaje_predicho);
    const brecha = (values[values.length - 1] - values[1]).toFixed(1);

    const options = {
        series: [{ name: 'Puntaje predicho', data: values }],
        chart: { type: 'line', height: 340, toolbar: { show: false } },
        stroke: { curve: 'smooth', width: 3 },
        colors: ['#2a9d8f'],
        markers: { size: 6, colors: ['#2a9d8f'], strokeWidth: 2 },
        xaxis: { categories: labels, labels: { style: { fontSize: '11px' } } },
        yaxis: { labels: { formatter: v => v.toFixed(0) } },
        annotations: {
            yaxis: [],
            xaxis: [],
            points: [{
                x: labels[labels.length - 1],
                y: values[values.length - 1],
                label: {
                    text: `+${brecha} pts vs E1`,
                    style: { background: '#2a9d8f', color: '#fff', fontSize: '11px' },
                },
            }],
        },
        tooltip: { y: { formatter: v => v.toFixed(1) + ' pts predichos' } },
        grid: { borderColor: '#f0f0f0' },
    };
    new ApexCharts(document.getElementById('chart-shap-estrato'), options).render();
}

// ---------------------------------------------------------------------------
// 2. Social Clusters
// ---------------------------------------------------------------------------
async function loadClusters() {
    try {
        const res = await fetch(ML_URLS.clusters);
        const data = await res.json();

        if (data.pending || !data.profiles || data.profiles.length === 0) {
            document.getElementById('clusters-pending-msg').classList.remove('d-none');
            document.getElementById('clusters-wrapper').classList.add('d-none');
            document.getElementById('kpi-clusters').textContent = '--';
            return;
        }

        document.getElementById('kpi-clusters').textContent = data.profiles.length;

        // Varianza PCA
        if (data.profiles[0]) {
            const p = data.profiles[0];
            document.getElementById('pca-variance-label').textContent =
                `(PC1 ${p.pca_var_pc1}% + PC2 ${p.pca_var_pc2}% varianza)`;
        }

        renderClusterCards(data.profiles);
        renderClusterScatter(data.scatter, data.profiles);

    } catch (e) {
        console.warn('loadClusters error:', e);
    }
}

function renderClusterCards(profiles) {
    const container = document.getElementById('cluster-cards');
    const cols = profiles.length <= 4 ? 'col-md-6 col-lg-3' : 'col-md-6 col-xl-4';
    container.innerHTML = profiles.map(p => `
        <div class="${cols}">
            <div class="card border-0 shadow-sm h-100" style="border-left: 4px solid ${p.cluster_color} !important;">
                <div class="card-body p-3">
                    <div class="d-flex align-items-center mb-2">
                        <span class="badge rounded-pill me-2"
                              style="background:${p.cluster_color};">&nbsp;</span>
                        <strong class="small">${p.cluster_name}</strong>
                    </div>
                    <p class="text-muted small mb-2">${p.cluster_descripcion}</p>
                    <div class="row g-1 text-center">
                        <div class="col-6">
                            <div class="bg-light rounded p-1">
                                <div class="fw-bold small">${p.avg_global}</div>
                                <div class="text-muted" style="font-size:10px;">Puntaje prom.</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="bg-light rounded p-1">
                                <div class="fw-bold small">${p.pct_nbi}%</div>
                                <div class="text-muted" style="font-size:10px;">NBI</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="bg-light rounded p-1">
                                <div class="fw-bold small">${p.pct_internet}%</div>
                                <div class="text-muted" style="font-size:10px;">Internet</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="bg-light rounded p-1">
                                <div class="fw-bold small">${p.n_colegios.toLocaleString()}</div>
                                <div class="text-muted" style="font-size:10px;">Colegios</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

function renderClusterScatter(scatter, profiles) {
    const colorMap = {};
    profiles.forEach(p => { colorMap[p.cluster_id] = p.cluster_color; });

    // Group by cluster_id
    const grouped = {};
    scatter.forEach(d => {
        if (!grouped[d.cluster_id]) {
            grouped[d.cluster_id] = { name: d.cluster_name, color: d.color, data: [] };
        }
        grouped[d.cluster_id].data.push({
            x: d.pc1, y: d.pc2,
            meta: { nombre: d.nombre, departamento: d.departamento, avg_global: d.avg_global },
        });
    });

    const series = Object.values(grouped).map(g => ({
        name: g.name,
        data: g.data.map(p => ({ x: p.x, y: p.y, meta: p.meta })),
    }));
    const colors = Object.values(grouped).map(g => g.color);

    const options = {
        series,
        chart: {
            type: 'scatter', height: 400, toolbar: { show: false },
            zoom: { enabled: true, type: 'xy' },
        },
        colors,
        markers: { size: 4, strokeWidth: 0, fillOpacity: 0.75 },
        xaxis: { title: { text: 'PC1' }, labels: { formatter: v => v.toFixed(1) } },
        yaxis: { title: { text: 'PC2' }, labels: { formatter: v => v.toFixed(1) } },
        tooltip: {
            custom: ({ series, seriesIndex, dataPointIndex, w }) => {
                const d = w.config.series[seriesIndex].data[dataPointIndex];
                const m = d.meta || {};
                return `<div class="px-2 py-1 small">
                    <strong>${m.nombre || ''}</strong><br>
                    ${m.departamento || ''} — ${m.avg_global || ''} pts
                </div>`;
            },
        },
        legend: { position: 'bottom', fontSize: '12px' },
        grid: { borderColor: '#f0f0f0' },
    };
    new ApexCharts(document.getElementById('chart-cluster-scatter'), options).render();
}

// ---------------------------------------------------------------------------
// 3. Riesgo de declive
// ---------------------------------------------------------------------------
async function loadRiesgo() {
    try {
        const res = await fetch(ML_URLS.riesgo);
        const data = await res.json();
        if (data.error) return;

        // KPI
        const alto = data.stats['Alto'] || 0;
        document.getElementById('kpi-riesgo').textContent = alto.toLocaleString();

        // Badges
        const badgesEl = document.getElementById('riesgo-badges');
        badgesEl.innerHTML = Object.entries(data.stats).map(([nivel, n]) => {
            const color = nivel === 'Alto' ? 'danger' : nivel === 'Medio' ? 'warning' : 'success';
            return `<span class="badge bg-${color}">${nivel}: ${n.toLocaleString()}</span>`;
        }).join('');

        // Tabla
        const tbody = document.getElementById('riesgo-tbody');
        tbody.innerHTML = data.colegios.map(c => {
            const color = c.nivel_riesgo === 'Alto' ? 'danger' : 'warning';
            return `<tr>
                <td class="small">${c.nombre}</td>
                <td class="small text-muted">${c.departamento}</td>
                <td class="text-end small fw-bold text-${color}">${c.prob_declive_pct}%</td>
                <td class="text-center">
                    <span class="badge bg-${color}-subtle text-${color} small">${c.nivel_riesgo}</span>
                </td>
            </tr>`;
        }).join('');

    } catch (e) {
        console.warn('loadRiesgo error:', e);
    }
}

// ---------------------------------------------------------------------------
// 4. B1 Overperformers
// ---------------------------------------------------------------------------
async function loadB1(sector) {
    // Toggle buttons
    document.getElementById('btn-b1-oficial').classList.toggle('active', sector === 'OFICIAL');
    document.getElementById('btn-b1-privado').classList.toggle('active', sector !== 'OFICIAL');

    try {
        const res = await fetch(`${ML_URLS.b1}?sector=${encodeURIComponent(sector)}`);
        const data = await res.json();
        if (data.error) return;

        if (data.colegios.length > 0) {
            const m = data.colegios[0];
            document.getElementById('b1-model-info').textContent =
                ` R²=${m.model_r2} MAE=${m.model_mae}pp`;
        }

        const tbody = document.getElementById('b1-tbody');
        tbody.innerHTML = data.colegios.map(c => `
            <tr>
                <td class="small">${c.nombre}</td>
                <td class="small text-muted">${c.departamento}</td>
                <td class="text-end small fw-bold">${c.pct_b1_real}%</td>
                <td class="text-end small text-success fw-bold">+${c.exceso_b1.toFixed(1)}</td>
            </tr>
        `).join('');

    } catch (e) {
        console.warn('loadB1 error:', e);
    }
}
