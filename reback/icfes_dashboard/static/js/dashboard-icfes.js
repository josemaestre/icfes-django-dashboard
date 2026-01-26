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

// --- Carga de resumen anual ---
// --- Carga de resumen anual ---
fetch('/icfes/resumen/')
  .then(response => response.json())
  .then(data => {
    // Tabla resumen - usando los campos correctos del endpoint
    const tbody = document.querySelector('#tabla-resumen tbody');
    if (tbody) { // Check existence (might be hidden in other tabs but DOM exists)
      data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.ano}</td>
            <td>${row.total_estudiantes ? row.total_estudiantes.toLocaleString() : '0'}</td>
            <td>${row.promedio_nacional ? row.promedio_nacional.toFixed(1) : '0.0'}</td>
            <td>N/A</td>
            <td>N/A</td>
            <td>N/A</td>
            <td>N/A</td>
          `;
        tbody.appendChild(tr);
      });
    }

    // Gráfico de evolución - usando campos disponibles
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
// LÓGICA DE BÚSQUEDA DE COLEGIO
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
      // Acción manual de búsqueda (puede tomar el primer resultado)
      // Por simplicidad, dejamos que el usuario seleccione de la lista o si escribe exacto
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

  function renderSchoolCard(data) {
    const info = data.info_basica;
    const ultimo = data.ultimo_ano;
    const cluster = data.cluster;

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

    // Cluster Info (LA PARTE SOLICITADA)
    if (cluster && cluster.cluster_name) {
      document.getElementById('res-cluster').textContent = cluster.cluster_name;
      document.getElementById('res-cluster-desc').textContent = `Grupo Cluster`;
    } else {
      document.getElementById('res-cluster').textContent = 'No Clasificado';
      document.getElementById('res-cluster-desc').textContent = '--';
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
});
