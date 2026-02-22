// --- Carga de datos departamentales ---
fetch('/icfes/data/')
  .then(resp => resp.json())
  .then(data => {
    const ctx = document.getElementById('graficoDepto');
    const labels = data.map(d => d.depto);
    const values = data.map(d => d.promedio_global);
    const total = data.reduce((a, b) => a + b.total_estudiantes, 0);
    const promedio = (data.reduce((a, b) => a + b.promedio_global, 0) / data.length).toFixed(1);

    document.getElementById('total_estudiantes').textContent = total.toLocaleString();
    document.getElementById('promedio_nacional').textContent = promedio;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Promedio Global',
          data: values,
          backgroundColor: 'rgba(54, 162, 235, 0.6)',
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'top' },
          title: { display: true, text: 'Promedio Global por Departamento' }
        }
      }
    });
  });

// --- Carga de resumen anual (storytelling ejecutivo) ---
fetch('/icfes/api/story/serie-anual/')
  .then(response => response.json())
  .then(data => {
    // Tabla resumen enriquecida
    const tbody = document.querySelector('#tabla-resumen tbody');
    if (tbody) {
      tbody.innerHTML = '';
      data.forEach(row => {
        const riesgoPct = row.total_colegios_riesgo
          ? ((row.colegios_alto_riesgo / row.total_colegios_riesgo) * 100)
          : 0;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.ano}</td>
            <td>${row.total_estudiantes ? row.total_estudiantes.toLocaleString() : '0'}</td>
            <td>${row.promedio_nacional ? row.promedio_nacional.toFixed(1) : '0.0'}</td>
            <td>${row.brecha_sector_publico_privado ? row.brecha_sector_publico_privado.toFixed(1) : '0.0'}</td>
            <td>${row.desviacion_estandar ? row.desviacion_estandar.toFixed(2) : '0.00'}</td>
            <td>${row.colegios_alto_riesgo ? row.colegios_alto_riesgo.toLocaleString() : '0'}</td>
            <td>${riesgoPct.toFixed(1)}%</td>
          `;
        tbody.appendChild(tr);
      });
    }

    // Gráfico de evolución
    const ctxEvol = document.getElementById('graficoEvolucion').getContext('2d');
    if (ctxEvol) {
      new Chart(ctxEvol, {
        type: 'line',
        data: {
          labels: data.map(d => d.ano),
          datasets: [
            {
              label: 'Promedio Nacional',
              data: data.map(d => d.promedio_nacional),
              borderColor: 'rgba(75, 192, 192, 1)',
              fill: false,
              tension: 0.3
            },
            {
              label: 'Matemáticas',
              data: data.map(d => d.promedio_matematicas),
              borderColor: 'rgba(54, 162, 235, 1)',
              fill: false,
              tension: 0.3
            },
            {
              label: 'Lectura Crítica',
              data: data.map(d => d.promedio_lectura),
              borderColor: 'rgba(255, 99, 132, 1)',
              fill: false,
              tension: 0.3
            }
          ]
        },
        options: {
          responsive: true,
          plugins: { legend: { labels: { color: '#000' } } },
          scales: {
            x: { ticks: { color: '#000' } },
            y: { ticks: { color: '#000' } }
          }
        }
      });
    }
  })
  .catch(error => {
    console.error('Error cargando resumen:', error);
  });


// ==========================================
// PANORAMA DE RIESGO (Data Science P2)
// ==========================================

fetch('/icfes/api/panorama-riesgo/')
  .then(resp => resp.json())
  .then(data => {
    if (!data.disponible) return;

    const section = document.getElementById('panorama-riesgo-section');
    section.style.display = '';

    // Risk level cards
    const cardsContainer = document.getElementById('riesgo-cards');
    const colorMap = {
      'Alto': { bg: 'danger', icon: 'bx-error-circle' },
      'Medio': { bg: 'warning', icon: 'bx-error' },
      'Bajo': { bg: 'success', icon: 'bx-check-circle' }
    };

    data.distribucion.forEach(d => {
      const cfg = colorMap[d.nivel_riesgo] || { bg: 'secondary', icon: 'bx-question-mark' };
      const col = document.createElement('div');
      col.className = 'col-md-4';
      col.innerHTML = `
        <div class="card mini-stats-wid border-start border-${cfg.bg} border-3">
          <div class="card-body">
            <div class="d-flex">
              <div class="flex-grow-1">
                <p class="text-muted fw-medium mb-1">Riesgo ${d.nivel_riesgo}</p>
                <h4 class="mb-0">${d.total_colegios.toLocaleString()}</h4>
                <small class="text-muted">${d.porcentaje}% del total</small>
              </div>
              <div class="flex-shrink-0 align-self-center">
                <div class="avatar-sm">
                  <span class="avatar-title rounded-circle bg-${cfg.bg}">
                    <i class="bx ${cfg.icon} text-white"></i>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>`;
      cardsContainer.appendChild(col);
    });

    // Doughnut chart
    const ctxRiesgo = document.getElementById('graficoRiesgoDistribucion');
    if (ctxRiesgo) {
      new Chart(ctxRiesgo, {
        type: 'doughnut',
        data: {
          labels: data.distribucion.map(d => `Riesgo ${d.nivel_riesgo}`),
          datasets: [{
            data: data.distribucion.map(d => d.total_colegios),
            backgroundColor: ['#dc3545', '#ffc107', '#28a745'],
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          plugins: {
            legend: { position: 'bottom' },
            title: {
              display: true,
              text: `Distribucion de Riesgo (${data.total_colegios_analizados.toLocaleString()} colegios)`
            }
          }
        }
      });
    }

    // Top risk table
    const tbody = document.querySelector('#tabla-top-riesgo tbody');
    if (tbody && data.top_riesgo) {
      data.top_riesgo.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><small>${r.nombre_colegio}</small></td>
          <td><small>${r.departamento}</small></td>
          <td><small>${r.sector}</small></td>
          <td>${r.puntaje_actual}</td>
          <td><span class="badge bg-danger">${(r.prob_declive * 100).toFixed(1)}%</span></td>`;
        tbody.appendChild(tr);
      });
    }
  })
  .catch(err => console.log('Panorama riesgo not available:', err.message));


// ==========================================
// LOGICA DE BUSQUEDA DE COLEGIO
// ==========================================

document.addEventListener('DOMContentLoaded', function () {
  const searchInput = document.getElementById('search-input');
  const searchBtn = document.getElementById('btn-search-school');
  const resultsList = document.getElementById('search-results-list');
  const resultContainer = document.getElementById('school-result-container');

  // Debounce simple
  let timeout = null;

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(timeout);
      const query = this.value;

      if (query.length < 3) {
        resultsList.style.display = 'none';
        return;
      }

      timeout = setTimeout(() => {
        fetch(`/icfes/api/search/colegios/?q=${encodeURIComponent(query)}&limit=5`)
          .then(r => r.json())
          .then(data => {
            resultsList.innerHTML = '';
            if (data.length > 0) {
              resultsList.style.display = 'block';
              data.forEach(item => {
                const li = document.createElement('li');
                li.className = 'list-group-item list-group-item-action cursor-pointer';
                li.innerHTML = `<strong>${item.nombre_colegio}</strong> <small class="text-muted">(${item.municipio})</small>`;
                li.onclick = () => selectSchool(item.colegio_sk);
                resultsList.appendChild(li);
              });
            } else {
              resultsList.style.display = 'none';
            }
          });
      }, 300);
    });
  }

  if (searchBtn) {
    searchBtn.addEventListener('click', () => {
      // Accion manual de busqueda
    });
  }

  function selectSchool(sk) {
    resultsList.style.display = 'none';
    searchInput.value = '';

    // Cargar datos del colegio
    fetch(`/icfes/api/colegio/${sk}/resumen/`)
      .then(r => r.json())
      .then(data => {
        if (data.error) { alert(data.error); return; }
        renderSchoolCard(data);
      });
  }

  // Helper: human-readable feature names
  function formatFeatureName(feat) {
    const names = {
      'cambio_ranking_nacional': 'Cambio en ranking',
      'ranking_nacional': 'Posicion en ranking',
      'avg_punt_global': 'Puntaje global',
      'cambio_porcentual_global': 'Cambio % global',
      'cambio_absoluto_global': 'Cambio absoluto',
      'volatilidad_global': 'Volatilidad historica',
      'tendencia_global': 'Tendencia historica',
      'brecha_nacional_global': 'Brecha vs nacional',
      'fd_potencial_mejora': 'Potencial de mejora',
      'dispersion_materias': 'Dispersion entre materias',
      'fd_brecha_pct_mat': 'Brecha en matematicas',
      'fd_brecha_pct_lec': 'Brecha en lectura',
    };
    return names[feat] || feat.replace(/_/g, ' ');
  }

  function renderSchoolCard(data) {
    const info = data.info_basica;
    const ultimo = data.ultimo_ano;
    const cluster = data.cluster;
    const riesgo = data.riesgo;

    // Header
    document.getElementById('res-nombre-colegio').textContent = info.nombre_colegio;
    document.getElementById('res-codigo-dane').textContent = info.codigo_dane || 'N/A';
    document.getElementById('res-sector').textContent = info.sector;
    document.getElementById('res-ubicacion').textContent = `${info.municipio}, ${info.departamento}`;

    // Stats
    if (ultimo) {
      document.getElementById('res-avg-global').textContent = ultimo.avg_punt_global ? ultimo.avg_punt_global.toFixed(1) : '--';
      document.getElementById('res-ranking').textContent = ultimo.ranking_nacional || '--';
      document.getElementById('res-estudiantes').textContent = ultimo.total_estudiantes || '--';
    }

    // Cluster Info
    if (cluster && cluster.cluster_name) {
      document.getElementById('res-cluster').textContent = cluster.cluster_name;
      document.getElementById('res-cluster-desc').textContent = 'Grupo Cluster';
    } else {
      document.getElementById('res-cluster').textContent = 'No Clasificado';
      document.getElementById('res-cluster-desc').textContent = '--';
    }

    // Risk Info (P2)
    const riesgoRow = document.getElementById('res-riesgo-row');
    if (riesgo && riesgo.nivel_riesgo) {
      riesgoRow.style.display = '';

      // Badge color
      const badge = document.getElementById('res-riesgo-badge');
      const riskColors = { 'Alto': 'bg-danger', 'Medio': 'bg-warning text-dark', 'Bajo': 'bg-success' };
      badge.className = `badge rounded-pill fs-6 px-3 py-2 ${riskColors[riesgo.nivel_riesgo] || 'bg-secondary'}`;
      badge.textContent = riesgo.nivel_riesgo;

      // Card border color
      const card = document.getElementById('res-riesgo-card');
      card.className = 'card';
      const borderColors = { 'Alto': 'border-danger', 'Medio': 'border-warning', 'Bajo': 'border-success' };
      card.classList.add('border', borderColors[riesgo.nivel_riesgo] || '');

      // Probability
      document.getElementById('res-riesgo-prob').textContent = `${(riesgo.prob_declive * 100).toFixed(1)}%`;

      // Factors
      const factoresEl = document.getElementById('res-riesgo-factores');
      factoresEl.innerHTML = '';
      if (riesgo.factores_principales && riesgo.factores_principales.length > 0) {
        riesgo.factores_principales.forEach(f => {
          const li = document.createElement('li');
          li.innerHTML = `<small><i class="bx bx-right-arrow-alt me-1"></i>${formatFeatureName(f.feature)}</small>`;
          factoresEl.appendChild(li);
        });
      } else {
        factoresEl.innerHTML = '<li class="text-muted"><small>Sin factores disponibles</small></li>';
      }
    } else {
      riesgoRow.style.display = 'none';
    }

    // Link detalle completo
    const btnLink = document.getElementById('btn-ver-detalle-completo');
    btnLink.href = `/icfes/colegio/?sk=${info.colegio_sk}`;

    // Mostrar
    resultContainer.style.display = 'block';
  }

  // Cerrar sugerencias al hacer click fuera
  document.addEventListener('click', function (e) {
    if (e.target !== searchInput && e.target !== resultsList) {
      resultsList.style.display = 'none';
    }
  });

  // ==========================================
  // EXPORT FUNCTIONALITY
  // ==========================================

  let currentSchoolSK = null;
  let currentSearchQuery = '';

  // Update export buttons when school is selected
  function updateExportButtons(schoolSK, searchQuery = '') {
    currentSchoolSK = schoolSK;
    currentSearchQuery = searchQuery;

    // Show CSV export button (Basic plan)
    const btnCSV = document.getElementById('btn-export-search-csv');
    if (btnCSV && searchQuery) {
      btnCSV.style.display = 'inline-block';
      btnCSV.href = `/icfes/export/schools/csv/?query=${encodeURIComponent(searchQuery)}&ano=2024`;
    }

    // Show PDF export button (Premium plan)
    const btnPDF = document.getElementById('btn-export-school-pdf');
    if (btnPDF && schoolSK) {
      btnPDF.style.display = 'inline-block';
      btnPDF.href = `/icfes/export/school/${schoolSK}/pdf/`;
    }
  }

  // Update renderSchoolCard to enable export buttons
  const originalRenderSchoolCard = renderSchoolCard;
  renderSchoolCard = function (data) {
    originalRenderSchoolCard(data);

    // Enable export buttons
    if (data.info_basica && data.info_basica.colegio_sk) {
      updateExportButtons(data.info_basica.colegio_sk, searchInput.value);
    }
  };

  // Update search input to show CSV export when typing
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      const query = this.value;
      if (query.length >= 3) {
        updateExportButtons(currentSchoolSK, query);
      } else {
        // Hide CSV button if query too short
        const btnCSV = document.getElementById('btn-export-search-csv');
        if (btnCSV) btnCSV.style.display = 'none';
      }
    });
  }
});
