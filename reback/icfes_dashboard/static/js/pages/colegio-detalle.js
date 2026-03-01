/**
 * Script para la página de detalle de colegio.
 * Maneja la carga de datos, gráficos y la funcionalidad de IA.
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Obtener el SK del colegio de la URL
    const urlParams = new URLSearchParams(window.location.search);
    const colegioSk = urlParams.get('sk');

    if (!colegioSk) {
        alert("No se especificó un colegio. Redirigiendo al inicio.");
        window.location.href = '/icfes/';
        return;
    }

    // 2. Cargar Resumen (Info básica, Histórico, Cluster)
    loadSchoolSummary(colegioSk);

    // 3. Cargar Colegios Similares
    loadSimilarSchools(colegioSk);

    // 4. Cargar Perfil de Inglés
    loadInglesProfile(colegioSk);

    // 5. Cargar Evolución de Niveles
    loadNivelesHistorico(colegioSk);

    // 6. Configurar botón de IA
    const btnAI = document.getElementById('btn-generate-ai');
    if (btnAI) {
        btnAI.addEventListener('click', () => loadAIRecommendations(colegioSk));
    }
});

/**
 * Carga el resumen general del colegio
 */
function loadSchoolSummary(sk) {
    fetch(`/icfes/api/colegio/${sk}/resumen/`)
        .then(response => {
            if (!response.ok) throw new Error('Colegio no encontrado');
            return response.json();
        })
        .then(data => {
            // -- Info Básica --
            const info = data.info_basica;
            document.getElementById('school-name').textContent = info.nombre_colegio;
            document.getElementById('school-location').textContent = `${info.municipio}, ${info.departamento} | ${info.sector}`;

            // -- Último Año --
            const ultimo = data.ultimo_ano;
            if (ultimo) {
                document.getElementById('school-score').textContent = ultimo.avg_punt_global.toFixed(1);
                document.getElementById('school-rank').textContent = `${ultimo.ranking_nacional} / ${ultimo.ranking_municipal || 'N/A'}`;
                document.getElementById('total-students').textContent = ultimo.total_estudiantes;
                document.getElementById('trend-classification').textContent = ultimo.clasificacion_tendencia || 'N/A';
            }

            // -- Z-Score --
            const zscore = data.z_score;
            if (zscore && zscore.z_score_global !== undefined) {
                const zVal = zscore.z_score_global.toFixed(2);
                const zElem = document.getElementById('z-score');
                zElem.textContent = zVal;
                // Color coding based on Z-Score
                if (zVal > 1) zElem.classList.add('text-success');
                else if (zVal < -1) zElem.classList.add('text-danger');
                else zElem.classList.add('text-warning');
            }

            // -- Cluster Info --
            const cluster = data.cluster;
            if (cluster && cluster.cluster_name) {
                document.getElementById('cluster-name').textContent = cluster.cluster_name;
                document.getElementById('cluster-desc').textContent = `Grupo: ${cluster.cluster_id}`;
            } else {
                document.getElementById('cluster-name').textContent = "No clasificado";
            }

            // -- Potencial Educativo Global (ML) --
            const pot = data.potencial;
            const potEl = document.getElementById('potencial-card');
            if (pot && pot.clasificacion && potEl) {
                const colorMap = {
                    'Excepcional':        '#198754',
                    'Por encima':         '#20c997',
                    'Esperado':           '#6c757d',
                    'Bajo el Potencial':  '#fd7e14',
                    'En Riesgo Contextual': '#dc3545',
                };
                const color = colorMap[pot.clasificacion] || '#6c757d';
                const exceso = pot.exceso !== null ? (pot.exceso > 0 ? '+' + pot.exceso.toFixed(1) : pot.exceso.toFixed(1)) : 'N/D';
                const pct  = pot.percentil_exceso !== null ? pot.percentil_exceso.toFixed(0) + '%' : 'N/D';
                const rkn  = pot.ranking_exceso_nacional || 'N/D';
                const rkd  = pot.ranking_exceso_depto || 'N/D';

                potEl.innerHTML = `
                    <div class="text-center mb-3">
                        <span class="badge fs-6 px-3 py-2" style="background:${color};">${pot.clasificacion}</span>
                    </div>
                    <div class="row text-center g-2 mb-2">
                        <div class="col-6">
                            <div class="p-2 rounded" style="background:#f8f9fa;">
                                <div class="fw-bold" style="color:${color};font-size:1.2rem;">${exceso}</div>
                                <div class="text-muted" style="font-size:11px;">Exceso vs esperado</div>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="p-2 rounded" style="background:#f8f9fa;">
                                <div class="fw-bold" style="font-size:1.2rem;">${pct}</div>
                                <div class="text-muted" style="font-size:11px;">Percentil nacional</div>
                            </div>
                        </div>
                    </div>
                    <div class="small text-muted text-center">
                        Ranking nacional: <strong>#${rkn}</strong> &nbsp;|&nbsp; Depto: <strong>#${rkd}</strong>
                    </div>`;
                document.getElementById('potencial-card-wrapper').style.display = '';
            }

            // -- Análisis Materias --
            const analisis = data.analisis;
            if (analisis) {
                // Parse strings if they look like lists or get raw fields
                // Assuming json response
            }

            // -- Charts --
            // Necesitamos datos historicos para el chart
            loadHistoricalChart(sk);
        })
        .catch(err => {
            console.error(err);
            alert("Error cargando datos del colegio.");
        });
}

/**
 * Carga el gráfico histórico
 */
function loadHistoricalChart(sk) {
    fetch(`/icfes/api/colegio/${sk}/historico/`)
        .then(r => r.json())
        .then(data => {
            // Data viene ordenada por ano DESC desde la API, la invertimos para el gráfico
            const dataAsc = [...data].reverse();
            const anos = dataAsc.map(d => d.ano);
            const scores = dataAsc.map(d => d.avg_punt_global);
            const deptScores = dataAsc.map(d => d.promedio_departamental_global);

            var options = {
                chart: {
                    height: 350,
                    type: 'line',
                    zoom: { enabled: false },
                    toolbar: { show: false }
                },
                colors: ['#556ee6', '#34c38f'],
                dataLabels: { enabled: false },
                stroke: { width: [3, 3], curve: 'straight' },
                series: [{
                    name: 'Puntaje Colegio',
                    data: scores
                }, {
                    name: 'Promedio Dept.',
                    data: deptScores
                }],
                grid: {
                    row: { colors: ['transparent', 'transparent'], opacity: 0.2 },
                    borderColor: '#f1f1f1'
                },
                xaxis: { categories: anos },
                legend: { position: 'top' }
            };

            var chart = new ApexCharts(document.querySelector("#chart-historico"), options);
            chart.render();
        });
}

/**
 * Carga colegios similares
 */
function loadSimilarSchools(sk) {
    fetch(`/icfes/api/colegio/${sk}/similares/?limit=5`)
        .then(r => r.json())
        .then(data => {
            const tbody = document.getElementById('similar-schools-list');
            tbody.innerHTML = '';

            if (data.error || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" class="text-center">No se encontraron similares</td></tr>';
                return;
            }

            data.forEach(school => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>
                        <h5 class="font-size-14 mb-1"><a href="?sk=${school.colegio_sk}" class="text-dark">${school.nombre_colegio}</a></h5>
                        <p class="text-muted mb-0 font-size-12">${school.municipio}</p>
                    </td>
                    <td>
                        <h5 class="font-size-14 mb-0">${school.avg_punt_global.toFixed(1)}</h5>
                    </td>
                    <td>
                         <a href="?sk=${school.colegio_sk}" class="btn btn-primary btn-sm btn-rounded waves-effect waves-light">
                            Ver
                        </a>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        });
}

/**
 * Carga Perfil de Bilingüismo (Inglés)
 */
function loadInglesProfile(sk) {
    fetch(`/icfes/api/colegio/${sk}/ingles/`)
        .then(r => {
            if (!r.ok) throw new Error('Ingles no encontrado');
            return r.json();
        })
        .then(data => {
            if (data.error) {
                console.error("Ingles data missing:", data.error);
                return;
            }
            document.getElementById('resumen-promedio-ingles').textContent = data.avg_historico.toFixed(1);
            document.getElementById('resumen-avg-ingles-ultimo').textContent = data.avg_ultimo.toFixed(1);

            const mcer = data.mcer;
            if (mcer && mcer.total > 0) {
                const pB1 = (mcer.b1 / mcer.total) * 100;
                const pA2 = (mcer.a2 / mcer.total) * 100;
                const pA1 = (mcer.a1 / mcer.total) * 100;
                const pPre = (mcer.pre_a1 / mcer.total) * 100;

                document.getElementById('bar-b1').style.width = pB1 + '%';
                document.getElementById('bar-b1').textContent = pB1.toFixed(1) + '%';

                document.getElementById('bar-a2').style.width = pA2 + '%';
                document.getElementById('bar-a2').textContent = pA2.toFixed(1) + '%';

                document.getElementById('bar-a1').style.width = pA1 + '%';
                document.getElementById('bar-a1').textContent = pA1.toFixed(1) + '%';

                document.getElementById('bar-pre-a1').style.width = pPre + '%';
                document.getElementById('bar-pre-a1').textContent = pPre.toFixed(1) + '%';

                // Chart will only render properly if there is some data
                var sum = pB1 + pA2 + pA1 + pPre;
                if (sum > 0) {
                    var options = {
                        series: [pB1, pA2, pA1, pPre],
                        labels: ['B1 / B+', 'A2', 'A1', 'Pre-A1'],
                        colors: ['#198754', '#0dcaf0', '#ffc107', '#dc3545'],
                        chart: { type: 'donut', height: 200 },
                        legend: { show: false },
                        tooltip: {
                            y: { formatter: function (val) { return val.toFixed(1) + '%'; } }
                        },
                        dataLabels: { enabled: false }
                    };
                    var chart = new ApexCharts(document.querySelector("#chart-mcer-colegio"), options);
                    chart.render();
                } else {
                    document.querySelector("#chart-mcer-colegio").innerHTML = '<div class="text-center text-muted mt-5">No hay niveles MCER disponibles</div>';
                }
            }
        })
        .catch(err => {
            console.error("Error loading Ingles:", err);
            // Hide or handle gracefully if not found
        });
}

// ──────────────────────────────────────────────────────────────
// Evolución de Niveles de Desempeño
// ──────────────────────────────────────────────────────────────
let _cdNivelesData = null;
let _cdNivelesChart = null;
let _cdCurrentMat  = 'mat';

function loadNivelesHistorico(sk) {
    fetch(`/icfes/api/colegio/${sk}/niveles-historico/`)
        .then(r => r.json())
        .then(data => {
            _cdNivelesData = Array.isArray(data) ? data : [];
            // No renderizar aquí: el tab está oculto y ApexCharts
            // calcula ancho 0 en contenedores hidden → gráfico invisible.
            // Se renderiza al mostrar el tab (shown.bs.tab).
        })
        .catch(err => console.error('Error loading niveles:', err));

    // Renderizar cuando el tab se activa por primera vez (Bootstrap event)
    const tabLink = document.querySelector('a[href="#niveles-desempeno"]');
    if (tabLink) {
        tabLink.addEventListener('shown.bs.tab', function () {
            if (_cdNivelesData) renderCdNivelesChart(_cdCurrentMat);
        });
    }

    // Selector de materia
    document.querySelectorAll('#cd-niveles-btns button').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('#cd-niveles-btns button').forEach(b => {
                b.classList.remove('btn-primary');
                b.classList.add('btn-outline-secondary');
            });
            this.classList.remove('btn-outline-secondary');
            this.classList.add('btn-primary');
            _cdCurrentMat = this.dataset.mat;
            renderCdNivelesChart(_cdCurrentMat);
        });
    });
}

function renderCdNivelesChart(mat) {
    const el = document.getElementById('cd-chart-niveles');
    if (!el) return;
    if (!_cdNivelesData || _cdNivelesData.length === 0) {
        el.innerHTML = '<div class="text-center text-muted py-5">Sin datos disponibles</div>';
        return;
    }

    const cfg = {
        mat: { labels: ['Insuficiente', 'Mínimo', 'Satisfactorio', 'Avanzado'],    keys: ['mat_pct1', 'mat_pct2', 'mat_pct3', 'mat_pct4'] },
        lc:  { labels: ['Insuficiente', 'Mínimo', 'Satisfactorio', 'Avanzado'],    keys: ['lc_pct1',  'lc_pct2',  'lc_pct3',  'lc_pct4'] },
        cn:  { labels: ['Insuficiente', 'Mínimo', 'Satisfactorio', 'Avanzado'],    keys: ['cn_pct1',  'cn_pct2',  'cn_pct3',  'cn_pct4'] },
        sc:  { labels: ['Insuficiente', 'Mínimo', 'Satisfactorio', 'Avanzado'],    keys: ['sc_pct1',  'sc_pct2',  'sc_pct3',  'sc_pct4'] },
        ing: { labels: ['Pre-A1', 'A1', 'A2', 'B1+'],                             keys: ['ing_pct_pre_a1', 'ing_pct_a1', 'ing_pct_a2', 'ing_pct_b1'] },
    };

    const { labels, keys } = cfg[mat];
    const anos = _cdNivelesData.map(d => d.ano);
    const colors = ['#f1416c', '#ffc700', '#17c1e8', '#50cd89'];

    const series = labels.map((lbl, i) => ({
        name: lbl,
        data: _cdNivelesData.map(d => d[keys[i]] || 0)
    }));

    if (_cdNivelesChart) { _cdNivelesChart.destroy(); }

    _cdNivelesChart = new ApexCharts(el, {
        chart: { type: 'bar', height: 320, stacked: true, stackType: '100%', toolbar: { show: false } },
        series,
        xaxis: { categories: anos },
        colors,
        dataLabels: {
            enabled: true,
            formatter: val => val > 6 ? val.toFixed(0) + '%' : '',
            style: { fontSize: '11px', colors: ['#fff'] }
        },
        plotOptions: { bar: { horizontal: false, columnWidth: '60%' } },
        legend: { position: 'top', horizontalAlign: 'left' },
        yaxis: { labels: { formatter: val => val.toFixed(0) + '%' } },
        tooltip: { y: { formatter: val => val.toFixed(1) + '%' } }
    });
    _cdNivelesChart.render();
}

/**
 * Carga recomendaciones de IA
 */
function loadAIRecommendations(sk) {
    const container = document.getElementById('ai-content');
    const loading = document.getElementById('ai-loading');
    const btn = document.getElementById('btn-generate-ai');

    container.style.display = 'none';
    loading.style.display = 'block';
    btn.disabled = true;

    fetch(`/icfes/api/colegio/${sk}/ai-recommendations/`)
        .then(r => r.json())
        .then(data => {
            loading.style.display = 'none';
            container.style.display = 'block';

            if (data.error) {
                container.innerHTML = `<div class="alert alert-warning">${data.message || data.error}</div>`;
                return;
            }

            // Render JSON response nicely
            let html = `
                <div class="alert alert-success bg-soft-success text-success border-0" role="alert">
                    <h5 class="font-size-16 mb-2">Evaluación General</h5>
                    <p class="mb-0">${data.evaluacion_general}</p>
                </div>
                
                <div class="row mt-4">
                    <div class="col-md-6">
                        <h5 class="font-size-15 mb-3">Fortalezas</h5>
                        <ul class="list-group list-group-flush">
                            ${data.fortalezas.map(f => `<li class="list-group-item"><i class="mdi mdi-check-circle text-success me-2"></i>${f}</li>`).join('')}
                        </ul>
                    </div>
                    <div class="col-md-6">
                        <h5 class="font-size-15 mb-3">Oportunidades de Mejora</h5>
                        <ul class="list-group list-group-flush">
                             ${data.debilidades.map(d => `<li class="list-group-item"><i class="mdi mdi-alert-circle text-warning me-2"></i>${d}</li>`).join('')}
                        </ul>
                    </div>
                </div>

                <div class="mt-4">
                     <h5 class="font-size-15 mb-3">Plan de Acción (5 Puntos)</h5>
                     <div class="vstack gap-2">
                        ${data.estrategias_5_puntos.map((e, i) => `
                            <div class="bg-light p-3 rounded">
                                <span class="fw-bold text-primary me-2">${i + 1}.</span> ${e}
                            </div>
                        `).join('')}
                     </div>
                </div>
            `;

            container.innerHTML = html;
        })
        .catch(err => {
            loading.style.display = 'none';
            btn.disabled = false;
            console.error(err);
            alert("Error generando recomendaciones.");
        });
}
