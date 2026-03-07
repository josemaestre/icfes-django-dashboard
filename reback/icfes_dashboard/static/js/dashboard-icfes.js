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
        console.group(`[Dashboard] Colegio: ${data.info_basica?.nombre_colegio || sk}`);
        console.log('ultimo_ano keys:', Object.keys(data.ultimo_ano || {}));
        console.log('potencial:', data.potencial);
        console.log('calidad:', data.calidad);
        console.log('prediccion_ingles:', data.prediccion_ingles);
        console.log('prioridad_ingles:', data.prioridad_ingles);
        console.log('riesgo:', data.riesgo);
        console.log('cluster:', data.cluster);
        console.groupEnd();
        renderSchoolCard(data);
      })
      .catch(err => console.error('[Dashboard] Error cargando resumen:', err));
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
      document.getElementById('res-cluster-desc').textContent = cluster.cluster_id ? `Grupo ${cluster.cluster_id}` : 'Grupo';
    } else {
      document.getElementById('res-cluster').textContent = 'No Clasificado';
      document.getElementById('res-cluster-desc').textContent = '--';
    }

    // Z-Score badge en el header
    const zscore = data.z_score;
    const zbadge = document.getElementById('res-zscore-badge');
    if (zscore && zscore.z_score_global != null && zbadge) {
      const z = +zscore.z_score_global;
      let cls, label;
      if      (z >  1.5) { cls = 'bg-success';            label = `Z ${z.toFixed(2)} · Excepcional`; }
      else if (z >  0.5) { cls = 'bg-primary';             label = `Z ${z.toFixed(2)} · Superior`; }
      else if (z > -0.5) { cls = 'bg-secondary';           label = `Z ${z.toFixed(2)} · Promedio`; }
      else if (z > -1.5) { cls = 'bg-warning text-dark';   label = `Z ${z.toFixed(2)} · Por mejorar`; }
      else               { cls = 'bg-danger';              label = `Z ${z.toFixed(2)} · Crítico`; }
      zbadge.className = `badge ${cls}`;
      zbadge.textContent = label;
      zbadge.style.display = '';
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

    // ML Análisis (potencial, predicción inglés, prioridad)
    renderML(data.potencial, data.prediccion_ingles, data.prioridad_ingles);

    // Puntajes por materia
    renderMaterias(ultimo);

    // Indicadores de calidad (tendencia, avanzado, inglés B1+)
    renderCalidad(ultimo, data.calidad);

    // Link detalle completo
    const btnLink = document.getElementById('btn-ver-detalle-completo');
    btnLink.href = `/icfes/colegio/?sk=${info.colegio_sk}`;

    // Mostrar (el contenedor debe ser visible ANTES de renderizar ApexCharts)
    resultContainer.style.display = 'block';

    // Cargar gráfico de niveles (container ya visible = ancho correcto)
    loadDashboardNiveles(info.colegio_sk);
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

// ──────────────────────────────────────────────────────────────
// ML Análisis (Potencial Educativo, Predicción Inglés, Prioridad)
// ──────────────────────────────────────────────────────────────
function renderML(potencial, prediccionIngles, prioridadIngles) {
  const row = document.getElementById('res-ml-row');
  if (!row) return;

  let hasData = false;

  // --- Potencial Educativo (Global ML) ---
  if (potencial && potencial.clasificacion) {
    hasData = true;
    console.log('[ML] potencial ✓', potencial.clasificacion, '| exceso:', potencial.exceso, '| pct:', potencial.percentil_exceso);
    const clsMap = {
      'Supera potencial':         { cls: 'border-success text-success', bg: 'bg-success-subtle' },
      'En línea con potencial':   { cls: 'border-primary text-primary', bg: 'bg-primary-subtle' },
      'Por debajo del potencial': { cls: 'border-danger text-danger',   bg: 'bg-danger-subtle'  },
    };
    const cfg = clsMap[potencial.clasificacion] || { cls: 'border-secondary text-secondary', bg: '' };
    const card = document.getElementById('res-ml-potencial-card');
    if (card) card.className = `p-3 rounded-3 border h-100 ${cfg.bg}`;

    const labelEl = document.getElementById('res-ml-potencial-label');
    if (labelEl) { labelEl.textContent = potencial.clasificacion; labelEl.className = `mb-1 fw-bold ${cfg.cls.split(' ')[1]}`; }

    const exceso = potencial.exceso;
    const excesoEl = document.getElementById('res-ml-potencial-exceso');
    if (excesoEl && exceso != null) {
      const sign = exceso >= 0 ? '+' : '';
      excesoEl.innerHTML = `<span class="${exceso >= 0 ? 'text-success' : 'text-danger'}">${sign}${exceso.toFixed(1)} pts</span> vs puntaje esperado`;
    }

    const pctEl = document.getElementById('res-ml-potencial-pct');
    if (pctEl && potencial.percentil_exceso != null) {
      pctEl.textContent = `Percentil ${potencial.percentil_exceso.toFixed(0)} nacional de exceso`;
    }
  } else {
    console.warn('[ML] potencial ✗ sin datos (tabla fct_potencial_educativo puede no estar en prod)', potencial);
  }

  // --- Predicción Inglés ---
  if (prediccionIngles && prediccionIngles.ano_prediccion) {
    hasData = true;
    console.log('[ML] prediccion_ingles ✓', prediccionIngles.tendencia, '| cambio:', prediccionIngles.cambio_predicho);
    const anoEl = document.getElementById('res-ml-prediccion-ano');
    if (anoEl) anoEl.textContent = prediccionIngles.ano_prediccion;

    const cambio = prediccionIngles.cambio_predicho;
    const cambioEl = document.getElementById('res-ml-prediccion-cambio');
    if (cambioEl && cambio != null) {
      const sign = cambio >= 0 ? '+' : '';
      const cls  = cambio >= 0 ? 'text-success' : 'text-danger';
      cambioEl.innerHTML = `<span class="${cls}">${sign}${cambio.toFixed(1)} pts</span>`;
    }

    const tendMap = { 'Mejora': 'text-success', 'Estable': 'text-secondary', 'Declive': 'text-danger' };
    const tendEl = document.getElementById('res-ml-prediccion-tendencia');
    if (tendEl && prediccionIngles.tendencia) {
      const cls = tendMap[prediccionIngles.tendencia] || 'text-secondary';
      tendEl.innerHTML = `Tendencia: <span class="${cls} fw-medium">${prediccionIngles.tendencia}</span>`;
    }

    const actualEl = document.getElementById('res-ml-prediccion-actual');
    if (actualEl && prediccionIngles.avg_ingles_actual != null) {
      actualEl.textContent = `Actual: ${prediccionIngles.avg_ingles_actual.toFixed(1)} pts → predicho: ${prediccionIngles.avg_ingles_predicho?.toFixed(1)} pts`;
    }

    const card = document.getElementById('res-ml-prediccion-card');
    if (card && cambio != null) {
      card.className = `p-3 rounded-3 border h-100 ${cambio >= 0 ? 'bg-success-subtle' : 'bg-danger-subtle'}`;
    }
  } else {
    console.warn('[ML] prediccion_ingles ✗ sin datos (tabla fct_prediccion_ingles puede no estar en prod)', prediccionIngles);
  }

  // --- Prioridad de Intervención en Inglés ---
  if (prioridadIngles && prioridadIngles.nivel_prioridad) {
    hasData = true;
    console.log('[ML] prioridad_ingles ✓', prioridadIngles.nivel_prioridad, '| score:', prioridadIngles.score_prioridad);
    const nivelMap = {
      'Crítico': { badge: 'bg-danger',            bg: 'bg-danger-subtle'  },
      'Urgente': { badge: 'bg-warning text-dark', bg: 'bg-warning-subtle' },
      'Atención': { badge: 'bg-info',             bg: 'bg-info-subtle'    },
      'Estable':  { badge: 'bg-success',          bg: 'bg-success-subtle' },
    };
    const cfg = nivelMap[prioridadIngles.nivel_prioridad] || { badge: 'bg-secondary', bg: '' };

    const card = document.getElementById('res-ml-prioridad-card');
    if (card) card.className = `p-3 rounded-3 border h-100 ${cfg.bg}`;

    const badgeEl = document.getElementById('res-ml-prioridad-badge');
    if (badgeEl) badgeEl.innerHTML = `<span class="badge rounded-pill fs-6 px-3 ${cfg.badge}">${prioridadIngles.nivel_prioridad}</span>`;

    const dimsEl = document.getElementById('res-ml-prioridad-dims');
    if (dimsEl) {
      const dims = [];
      if (prioridadIngles.dim_brecha_potencial != null) dims.push(`Brecha potencial: ${prioridadIngles.dim_brecha_potencial.toFixed(2)}`);
      if (prioridadIngles.dim_declive_3y != null)       dims.push(`Declive 3 años: ${prioridadIngles.dim_declive_3y.toFixed(2)}`);
      dimsEl.innerHTML = dims.map(d => `<span class="text-muted">${d}</span>`).join('<br>');
    }
  } else {
    console.warn('[ML] prioridad_ingles ✗ sin datos (tabla fct_prioridad_ingles puede no estar en prod)', prioridadIngles);
  }

  console.log('[ML] renderML → hasData:', hasData, '| row visible:', hasData);
  row.style.display = hasData ? '' : 'none';
}

// ──────────────────────────────────────────────────────────────
// Puntaje por Materia
// ──────────────────────────────────────────────────────────────
function renderMaterias(ultimo) {
  const row = document.getElementById('res-materias-row');
  const container = document.getElementById('res-materias-cards');
  if (!row || !container || !ultimo) return;

  const materias = [
    { key: 'avg_punt_matematicas',         label: 'Matemáticas',   icon: 'bx-math',          umbral_alto: 55, umbral_bajo: 43 },
    { key: 'avg_punt_lectura_critica',     label: 'Lectura',       icon: 'bx-book-reader',   umbral_alto: 55, umbral_bajo: 43 },
    { key: 'avg_punt_c_naturales',         label: 'C. Naturales',  icon: 'bx-leaf',          umbral_alto: 55, umbral_bajo: 43 },
    { key: 'avg_punt_sociales_ciudadanas', label: 'Soc. Ciudadanas', icon: 'bx-world',       umbral_alto: 55, umbral_bajo: 43 },
    { key: 'avg_punt_ingles',              label: 'Inglés',        icon: 'bx-globe',         umbral_alto: 55, umbral_bajo: 43 },
  ];

  // Verificar si hay datos de materias
  const hasMaterias = materias.some(m => ultimo[m.key] != null);
  if (!hasMaterias) {
    console.warn('[Materias] ✗ sin puntajes por materia en ultimo_ano', Object.keys(ultimo));
    row.style.display = 'none'; return;
  }

  container.innerHTML = '';
  console.log('[Materias] ✓ renderizando', materias.map(m => `${m.label}:${ultimo[m.key]?.toFixed(1)}`).join(' | '));
  materias.forEach(m => {
    const val = ultimo[m.key];
    if (val == null) return;
    const score = parseFloat(val).toFixed(1);
    const numScore = parseFloat(score);

    let colorClass = 'bg-primary';
    let vsLabel = '';
    if (numScore >= m.umbral_alto) { colorClass = 'bg-success'; vsLabel = '<span class="badge bg-success-subtle text-success ms-1" style="font-size:0.6rem;">▲ Alto</span>'; }
    else if (numScore <= m.umbral_bajo) { colorClass = 'bg-danger'; vsLabel = '<span class="badge bg-danger-subtle text-danger ms-1" style="font-size:0.6rem;">▼ Bajo</span>'; }
    else { vsLabel = '<span class="badge bg-secondary-subtle text-secondary ms-1" style="font-size:0.6rem;">≈ Medio</span>'; }

    const col = document.createElement('div');
    col.className = 'col';
    col.style.minWidth = '140px';
    col.innerHTML = `
      <div class="card mini-stats-wid mb-0 h-100">
        <div class="card-body py-2 px-3">
          <div class="d-flex align-items-center">
            <div class="flex-grow-1">
              <p class="text-muted mb-1" style="font-size:0.72rem;">${m.label}</p>
              <h5 class="mb-0">${score} ${vsLabel}</h5>
            </div>
            <div class="ms-2">
              <div class="avatar-sm rounded-circle ${colorClass}" style="width:36px;height:36px;">
                <span class="avatar-title rounded-circle ${colorClass}" style="width:36px;height:36px;font-size:1rem;">
                  <i class="bx ${m.icon} text-white"></i>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>`;
    container.appendChild(col);
  });

  row.style.display = '';
}

// ──────────────────────────────────────────────────────────────
// Indicadores de Calidad (Tendencia, % Avanzado, Inglés B1+)
// ──────────────────────────────────────────────────────────────
function renderCalidad(ultimo, calidad) {
  const row = document.getElementById('res-calidad-row');
  if (!row) return;

  let hasData = false;

  // --- Tendencia ---
  if (ultimo && ultimo.clasificacion_tendencia) {
    hasData = true;
    console.log('[Calidad] tendencia ✓', ultimo.clasificacion_tendencia, '| cambio:', ultimo.cambio_absoluto_global);
    const tendencia = ultimo.clasificacion_tendencia;
    const cambio = ultimo.cambio_absoluto_global;

    const tendMap = {
      'Mejorando':  { cls: 'bg-success', icon: 'bx-trending-up',   label: 'Mejorando' },
      'Estable':    { cls: 'bg-secondary', icon: 'bx-minus',        label: 'Estable' },
      'Declinando': { cls: 'bg-danger',  icon: 'bx-trending-down',  label: 'Declinando' },
    };
    const cfg = tendMap[tendencia] || { cls: 'bg-secondary', icon: 'bx-minus', label: tendencia };

    const labelEl = document.getElementById('res-calidad-tendencia-label');
    const cambioEl = document.getElementById('res-calidad-tendencia-cambio');
    const iconEl   = document.getElementById('res-calidad-tendencia-icon');
    const wrapEl   = document.getElementById('res-calidad-tendencia-icon-wrap');

    if (labelEl) labelEl.textContent = cfg.label;
    if (cambioEl && cambio != null) {
      const sign = cambio >= 0 ? '+' : '';
      cambioEl.textContent = `${sign}${parseFloat(cambio).toFixed(1)} pts vs año anterior`;
    }
    if (iconEl)  iconEl.className = `avatar-title rounded-circle ${cfg.cls}`;
    if (wrapEl)  wrapEl.className = `avatar-sm rounded-circle mini-stat-icon`;
    if (iconEl)  iconEl.innerHTML = `<i class="bx ${cfg.icon} text-white"></i>`;
  }

  if (!ultimo?.clasificacion_tendencia) console.warn('[Calidad] tendencia ✗', ultimo?.clasificacion_tendencia);

  // --- % Avanzado Integral ---
  if (calidad && calidad.pct_avanzado_integral != null) {
    hasData = true;
    console.log('[Calidad] avanzado ✓', calidad.pct_avanzado_integral + '%');
    const pct = parseFloat(calidad.pct_avanzado_integral);
    const el = document.getElementById('res-calidad-avanzado');
    if (el) el.textContent = `${pct.toFixed(1)}%`;
  }

  if (calidad?.pct_avanzado_integral == null) console.warn('[Calidad] avanzado ✗', calidad);

  // --- Inglés B1+ ---
  if (calidad && calidad.ing_pct_b1 != null) {
    hasData = true;
    console.log('[Calidad] inglés B1+ ✓', calidad.ing_pct_b1 + '%');
    const pct = parseFloat(calidad.ing_pct_b1);
    const el    = document.getElementById('res-calidad-ingles');
    const icon  = document.getElementById('res-calidad-ingles-icon');

    if (el) el.textContent = `${pct.toFixed(1)}%`;
    if (icon) {
      let cls = 'bg-danger';
      if (pct >= 15) cls = 'bg-success';
      else if (pct >= 5) cls = 'bg-warning';
      icon.className = `avatar-title rounded-circle ${cls}`;
      icon.innerHTML = '<i class="bx bx-globe text-white"></i>';
    }
  }

  if (calidad?.ing_pct_b1 == null) console.warn('[Calidad] inglés B1+ ✗', calidad);
  console.log('[Calidad] renderCalidad → hasData:', hasData);
  row.style.display = hasData ? '' : 'none';
}

// ──────────────────────────────────────────────────────────────
// Evolución de Niveles — Búsqueda de Colegio (dashboard principal)
// ──────────────────────────────────────────────────────────────
let _dashNivelesChart = null;
let _dashNivelesMat   = 'mat';

function loadDashboardNiveles(sk) {
  const row = document.getElementById('res-niveles-row');
  if (row) row.style.display = 'none';

  fetch(`/icfes/api/colegio/${sk}/niveles-historico/`)
    .then(r => r.json())
    .then(data => {
      if (!Array.isArray(data) || !data.length) {
        console.warn('[Niveles] ✗ sin datos históricos de niveles para sk:', sk, data);
        return;
      }
      console.log('[Niveles] ✓', data.length, 'años disponibles:', data.map(d => d.ano).join(', '));
      if (row) row.style.display = '';

      // Forzar materia activa al primer botón
      _dashNivelesMat = 'mat';
      document.querySelectorAll('#dash-niveles-btns button').forEach(b => {
        b.classList.toggle('btn-primary',         b.dataset.mat === 'mat');
        b.classList.toggle('btn-outline-secondary', b.dataset.mat !== 'mat');
      });

      // Pequeño delay para que el navegador repinte antes de medir dimensiones
      setTimeout(() => renderDashNivelesChart(data, _dashNivelesMat), 50);

      // Clonar botones para limpiar listeners de búsquedas anteriores
      document.querySelectorAll('#dash-niveles-btns button').forEach(btn => {
        const clone = btn.cloneNode(true);
        btn.parentNode.replaceChild(clone, btn);
      });
      document.querySelectorAll('#dash-niveles-btns button').forEach(btn => {
        btn.addEventListener('click', function () {
          document.querySelectorAll('#dash-niveles-btns button').forEach(b => {
            b.classList.remove('btn-primary');
            b.classList.add('btn-outline-secondary');
          });
          this.classList.remove('btn-outline-secondary');
          this.classList.add('btn-primary');
          _dashNivelesMat = this.dataset.mat;
          renderDashNivelesChart(data, _dashNivelesMat);
        });
      });
    })
    .catch(err => console.error('[Niveles] ✗ Error cargando:', err));
}

function renderDashNivelesChart(data, mat) {
  const el = document.getElementById('dash-chart-niveles');
  if (!el) return;

  const cfg = {
    mat: { labels: ['Insuficiente', 'Mínimo', 'Satisfactorio', 'Avanzado'], keys: ['mat_pct1', 'mat_pct2', 'mat_pct3', 'mat_pct4'] },
    lc:  { labels: ['Insuficiente', 'Mínimo', 'Satisfactorio', 'Avanzado'], keys: ['lc_pct1',  'lc_pct2',  'lc_pct3',  'lc_pct4'] },
    cn:  { labels: ['Insuficiente', 'Mínimo', 'Satisfactorio', 'Avanzado'], keys: ['cn_pct1',  'cn_pct2',  'cn_pct3',  'cn_pct4'] },
    sc:  { labels: ['Insuficiente', 'Mínimo', 'Satisfactorio', 'Avanzado'], keys: ['sc_pct1',  'sc_pct2',  'sc_pct3',  'sc_pct4'] },
    ing: { labels: ['Pre-A1', 'A1', 'A2', 'B1+'],                          keys: ['ing_pct_pre_a1', 'ing_pct_a1', 'ing_pct_a2', 'ing_pct_b1'] },
  };
  const { labels, keys } = cfg[mat] || cfg.mat;
  const anos   = data.map(d => d.ano);
  const colors = ['#f1416c', '#ffc700', '#17c1e8', '#50cd89'];
  const series = labels.map((name, i) => ({
    name,
    data: data.map(d => d[keys[i]] || 0),
  }));

  if (_dashNivelesChart) { _dashNivelesChart.destroy(); _dashNivelesChart = null; }

  _dashNivelesChart = new ApexCharts(el, {
    chart: { type: 'bar', height: 280, stacked: true, stackType: '100%', toolbar: { show: false } },
    series,
    xaxis: { categories: anos },
    colors,
    dataLabels: {
      enabled: true,
      formatter: v => v > 6 ? v.toFixed(0) + '%' : '',
      style: { fontSize: '10px', colors: ['#fff'] },
    },
    plotOptions: { bar: { horizontal: false, columnWidth: '60%' } },
    legend: { position: 'top', horizontalAlign: 'left' },
    yaxis: { labels: { formatter: v => v.toFixed(0) + '%' } },
    tooltip: { y: { formatter: v => v.toFixed(1) + '%' } },
  });
  _dashNivelesChart.render();
}
