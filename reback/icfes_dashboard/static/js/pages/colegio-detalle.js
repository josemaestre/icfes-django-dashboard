/**
 * Script para la página de detalle de colegio.
 * Maneja la carga de datos, gráficos y la funcionalidad de IA.
 */

document.addEventListener('DOMContentLoaded', function() {
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

    // 4. Configurar botón de IA
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
            // Data viene ordenada por ano ASC
            const anos = data.map(d => d.ano);
            const scores = data.map(d => d.avg_punt_global);
            const deptScores = data.map(d => d.promedio_departamental_global);

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
                                <span class="fw-bold text-primary me-2">${i+1}.</span> ${e}
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
