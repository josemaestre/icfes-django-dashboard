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
fetch('/icfes/resumen/')
  .then(response => response.json())
  .then(data => {
    // Tabla resumen
    const tbody = document.querySelector('#tabla-resumen tbody');
    data.forEach(row => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${row.ano}</td>
        <td>${row.total_alumnos.toLocaleString()}</td>
        <td>${row.promedio_ajustado.toFixed(1)}</td>
        <td>${row.pct_aprobado ? row.pct_aprobado.toFixed(1) : "0.0"}%</td>

        <td>${row.pct_no_aprobado ? row.pct_no_aprobado.toFixed(1) : "0.0"}%</td>
        <td>${row.pct_beca ? row.pct_beca.toFixed(1) : "0.0"}%</td>
        <td>${row.pct_sobresaliente ? row.pct_sobresaliente.toFixed(1) : "0.0"}%</td>

      `;
      tbody.appendChild(tr);
    });

    // Gráfico de evolución
    const ctxEvol = document.getElementById('graficoEvolucion').getContext('2d');
    new Chart(ctxEvol, {
      type: 'line',
      data: {
        labels: data.map(d => d.ano),
        datasets: [
          {
            label: 'Promedio Global',
            data: data.map(d => d.promedio_ajustado),
            borderColor: 'rgba(75, 192, 192, 1)',
            fill: false,
            tension: 0.3
          },
          {
            label: '% Aprobado',
            data: data.map(d => d.pct_aprobado),
            borderColor: 'rgba(54, 162, 235, 1)',
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
  });
