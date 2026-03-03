/**
 * Dashboard IA & Modelos ML
 * Carga datos de modelos ML + narrativa IA generativa (Claude).
 */

const ML_URLS = {
    shap:             '/icfes/api/ml/shap/',
    clusters:         '/icfes/api/ml/social-clusters/',
    riesgo:           '/icfes/api/ml/riesgo/',
    b1:               '/icfes/api/ml/b1/',
    iaAnalisis:       '/icfes/api/ml/ia-analisis/',
    palancasNacional: '/icfes/api/ml/palancas-nacional/',
};

// ---------------------------------------------------------------------------
// Boot — primero datos/gráficas, luego narrativa IA
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    Promise.all([
        loadShap(),
        loadClusters(),
        loadRiesgo(),
        loadB1('OFICIAL'),
        loadPalancasNacional(),
    ]).finally(() => {
        // La narrativa IA solo aparece cuando los gráficos ya están visibles
        loadIaAnalisis();
    });
});

// ---------------------------------------------------------------------------
// 1. SHAP importances + partial dependence estrato
// ---------------------------------------------------------------------------
async function loadShap() {
    try {
        const res  = await fetch(ML_URLS.shap);
        const data = await res.json();

        if (data.pending || !data.importances || data.importances.length === 0) {
            document.getElementById('shap-pending-msg').classList.remove('d-none');
            document.getElementById('shap-charts-wrapper').classList.add('d-none');
            return;
        }

        const m = data.importances[0];
        document.getElementById('kpi-r2').textContent  = m.model_r2.toFixed(3);
        document.getElementById('kpi-mae').textContent = m.model_mae.toFixed(1) + ' pts';

        // Headline dinámico en el hero
        document.getElementById('hero-headline').innerHTML =
            `<i class="bx bx-brain me-2 text-info"></i>` +
            `"${m.label}" es el factor que más determina el puntaje ICFES`;

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

    new ApexCharts(document.getElementById('chart-shap-bar'), {
        series: [{ name: 'Importancia SHAP (pts)', data: values }],
        chart: { type: 'bar', height: 340, toolbar: { show: false } },
        plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '65%' } },
        colors,
        dataLabels: {
            enabled: true,
            formatter: v => v.toFixed(1) + ' pts',
            style: { fontSize: '11px', colors: ['#333'] },
            offsetX: 4,
        },
        xaxis: { categories: labels, labels: { style: { fontSize: '12px' } } },
        yaxis: { labels: { style: { fontSize: '11px' } } },
        tooltip: { y: { formatter: v => v.toFixed(2) + ' pts promedio' } },
        grid: { borderColor: '#f0f0f0' },
    }).render();
}

function renderShapEstrato(partial) {
    if (!partial || partial.length === 0) return;
    const labels = partial.map(d => d.estrato);
    const values = partial.map(d => d.puntaje_predicho);
    const brecha = (values[values.length - 1] - values[1]).toFixed(1);

    new ApexCharts(document.getElementById('chart-shap-estrato'), {
        series: [{ name: 'Puntaje predicho', data: values }],
        chart: { type: 'line', height: 340, toolbar: { show: false } },
        stroke: { curve: 'smooth', width: 3 },
        colors: ['#2a9d8f'],
        markers: { size: 6, colors: ['#2a9d8f'], strokeWidth: 2 },
        xaxis: { categories: labels, labels: { style: { fontSize: '11px' } } },
        yaxis: { labels: { formatter: v => v.toFixed(0) } },
        annotations: {
            points: [{
                x: labels[labels.length - 1],
                y: values[values.length - 1],
                label: {
                    text: `${brecha} pts vs E1`,
                    style: { background: '#2a9d8f', color: '#fff', fontSize: '11px' },
                },
            }],
        },
        tooltip: { y: { formatter: v => v.toFixed(1) + ' pts predichos' } },
        grid: { borderColor: '#f0f0f0' },
    }).render();
}

// ---------------------------------------------------------------------------
// 2. Social Clusters (K-Means + PCA)
// ---------------------------------------------------------------------------
async function loadClusters() {
    try {
        const res  = await fetch(ML_URLS.clusters);
        const data = await res.json();

        if (data.pending || !data.profiles || data.profiles.length === 0) {
            document.getElementById('clusters-pending-msg').classList.remove('d-none');
            document.getElementById('clusters-wrapper').classList.add('d-none');
            document.getElementById('kpi-clusters').textContent = '--';
            return;
        }

        document.getElementById('kpi-clusters').textContent = data.profiles.length;

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
    const cols = profiles.length <= 4 ? 'col-md-6 col-lg-3' : 'col-md-6 col-xl-4 col-lg-6';
    container.innerHTML = profiles.map(p => `
        <div class="${cols}">
            <div class="card border-0 shadow-sm h-100"
                 style="border-left: 4px solid ${p.cluster_color} !important;">
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

    new ApexCharts(document.getElementById('chart-cluster-scatter'), {
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
    }).render();
}

// ---------------------------------------------------------------------------
// 3. Riesgo de declive
// ---------------------------------------------------------------------------
async function loadRiesgo() {
    try {
        const res  = await fetch(ML_URLS.riesgo);
        const data = await res.json();
        if (data.error) return;

        const alto = data.stats['Alto'] || 0;
        document.getElementById('kpi-riesgo').textContent = alto.toLocaleString();

        document.getElementById('riesgo-badges').innerHTML =
            Object.entries(data.stats).map(([nivel, n]) => {
                const color = nivel === 'Alto' ? 'danger' : nivel === 'Medio' ? 'warning' : 'success';
                return `<span class="badge bg-${color}">${nivel}: ${n.toLocaleString()}</span>`;
            }).join('');

        document.getElementById('riesgo-tbody').innerHTML = data.colegios.map(c => {
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
    document.getElementById('btn-b1-oficial').classList.toggle('active', sector === 'OFICIAL');
    document.getElementById('btn-b1-privado').classList.toggle('active', sector !== 'OFICIAL');

    try {
        const res  = await fetch(`${ML_URLS.b1}?sector=${encodeURIComponent(sector)}`);
        const data = await res.json();
        if (data.error) return;

        if (data.colegios.length > 0) {
            const m = data.colegios[0];
            document.getElementById('b1-model-info').textContent =
                ` R²=${m.model_r2} MAE=${m.model_mae}pp`;
        }

        document.getElementById('b1-tbody').innerHTML = data.colegios.map(c => `
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

// ---------------------------------------------------------------------------
// 5. Narrativa IA generativa (Claude, pre-generada)
// ---------------------------------------------------------------------------
async function loadIaAnalisis() {
    showEl('shap-ia-loading');

    try {
        const res  = await fetch(ML_URLS.iaAnalisis);
        const data = await res.json();

        hideEl('shap-ia-loading');

        if (!data.disponible) {
            showEl('shap-ia-unavailable');
            return;
        }

        const fecha = new Date(data.fecha_generacion).toLocaleDateString('es-CO', {
            day: '2-digit', month: 'short', year: 'numeric',
        });
        const metaText =
            `Generado por ${data.modelo_ia} · ${fecha} · ${(data.tokens_output || 0).toLocaleString()} tokens`;

        // SHAP
        if (data.shap_narrative) {
            document.getElementById('shap-ia-meta').textContent = metaText;
            document.getElementById('shap-ia-text').textContent = data.shap_narrative;
            showEl('shap-ia-wrapper');
        } else {
            showEl('shap-ia-unavailable');
        }

        // Clusters
        if (data.clusters_narrative) {
            document.getElementById('clusters-ia-text').textContent = data.clusters_narrative;
            showEl('clusters-ia-wrapper');
        }

        // Riesgo
        if (data.riesgo_narrative) {
            document.getElementById('riesgo-ia-text').textContent = data.riesgo_narrative;
            showEl('riesgo-ia-wrapper');
        }

        // Oportunidad (B1)
        if (data.oportunidad_narrative) {
            document.getElementById('oportunidad-ia-text').textContent = data.oportunidad_narrative;
            showEl('oportunidad-ia-wrapper');
        }

        // Palancas (narrativa IA dentro de la sección de datos)
        if (data.palancas_narrative) {
            document.getElementById('palancas-ia-text').textContent = data.palancas_narrative;
            showEl('palancas-ia-wrapper');
        }

        // Panel completo colapsable
        if (data.analisis_md) {
            document.getElementById('ia-model-badge').textContent = data.modelo_ia;
            document.getElementById('ia-full-meta').textContent = metaText;
            document.getElementById('ia-full-text').textContent = data.analisis_md;
            document.getElementById('ia-full-panel-row').style.display = '';
        }

    } catch (e) {
        console.warn('loadIaAnalisis error:', e);
        hideEl('shap-ia-loading');
        showEl('shap-ia-unavailable');
    }
}

// ---------------------------------------------------------------------------
// 6. Palancas Educativas nacionales
// ---------------------------------------------------------------------------
async function loadPalancasNacional() {
    try {
        const res  = await fetch(ML_URLS.palancasNacional);
        const data = await res.json();
        if (data.error) return;

        const { stats, distribucion, top_colegios } = data;

        // KPIs
        document.getElementById('palancas-kpi-colegios').textContent =
            (stats.n_colegios || 0).toLocaleString();
        document.getElementById('palancas-n-colegios').textContent =
            (stats.n_colegios || 0).toLocaleString();
        document.getElementById('palancas-kpi-delta-prom').textContent =
            '+' + (stats.delta_promedio || 0).toFixed(1) + ' pts';
        document.getElementById('palancas-kpi-delta-max').textContent =
            '+' + (stats.delta_max_total || 0).toFixed(1) + ' pts';
        if (distribucion && distribucion.length > 0) {
            document.getElementById('palancas-kpi-top-palanca').textContent =
                distribucion[0].feature_label;
        }

        // Gráfico de distribución (bar horizontal)
        if (distribucion && distribucion.length > 0) {
            const labels = distribucion.map(d => d.feature_label);
            const values = distribucion.map(d => d.n_colegios);
            const deltas = distribucion.map(d => d.delta_promedio);
            new ApexCharts(document.getElementById('chart-palancas-dist'), {
                series: [{ name: 'Colegios', data: values }],
                chart: { type: 'bar', height: 260, toolbar: { show: false } },
                plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '60%' } },
                colors: ['#2a9d8f'],
                dataLabels: {
                    enabled: true,
                    formatter: (v, opts) => {
                        const d = deltas[opts.dataPointIndex];
                        return v.toLocaleString() + '  (+' + d.toFixed(1) + ' pts)';
                    },
                    style: { fontSize: '10px', colors: ['#fff'] },
                },
                xaxis: { categories: labels, labels: { style: { fontSize: '10px' } } },
                yaxis: { labels: { style: { fontSize: '10px' } } },
                tooltip: {
                    y: { formatter: (v, opts) => {
                        const d = deltas[opts.dataPointIndex];
                        return v.toLocaleString() + ' colegios · delta prom +' + d.toFixed(1) + ' pts';
                    }},
                },
                grid: { borderColor: '#f0f0f0' },
            }).render();
        }

        // Tabla top colegios
        if (top_colegios && top_colegios.length > 0) {
            document.getElementById('palancas-top-tbody').innerHTML =
                top_colegios.map((c, i) => {
                    const sectorBadge = c.sector === 'OFICIAL'
                        ? '<span class="badge bg-primary-subtle text-primary" style="font-size:9px;">Of.</span>'
                        : '<span class="badge bg-warning-subtle text-warning" style="font-size:9px;">Priv.</span>';
                    return `<tr>
                        <td class="small text-muted">${i + 1}</td>
                        <td class="small">${sectorBadge} ${c.nombre}</td>
                        <td class="small text-muted">${c.departamento}</td>
                        <td class="small text-end">${c.puntaje_actual.toFixed(0)}</td>
                        <td class="small text-end fw-bold text-success">+${c.delta_total.toFixed(1)}</td>
                    </tr>`;
                }).join('');
        }

    } catch (e) {
        console.warn('loadPalancasNacional error:', e);
        const tbody = document.getElementById('palancas-top-tbody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted small py-2">Sin datos</td></tr>';
    }
}

// ---------------------------------------------------------------------------
// 7. Generar análisis IA bajo demanda (staff only)
// ---------------------------------------------------------------------------
function generateIaAnalysis(forzar = false) {
    const btn = document.getElementById('btn-generate-ia');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML =
            '<span class="spinner-border spinner-border-sm me-1" role="status"></span>' +
            'Generando (~1–2 min)…';
    }

    const csrfToken = document.cookie
        .split(';')
        .map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))
        ?.split('=')[1] || '';

    const body = new FormData();
    body.append('ano', '2024');
    if (forzar) body.append('forzar', '1');

    fetch('/icfes/api/ml/generate-ia/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
        body,
    })
    .then(r => r.json())
    .then(d => {
        if (d.ok) {
            if (btn) {
                btn.innerHTML = '<i class="bx bx-check me-1"></i>Generado · recargando…';
                btn.classList.replace('btn-warning', 'btn-success');
            }
            setTimeout(() => {
                hideEl('shap-ia-unavailable');
                showEl('shap-ia-loading');
                loadIaAnalisis();
            }, 800);
        } else {
            alert('Error: ' + d.error);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bx bx-brain me-1"></i>Generar análisis IA ahora';
            }
        }
    })
    .catch(err => {
        alert('Error de conexión: ' + err.message);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bx bx-brain me-1"></i>Generar análisis IA ahora';
        }
    });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function showEl(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('d-none');
}
function hideEl(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('d-none');
}
