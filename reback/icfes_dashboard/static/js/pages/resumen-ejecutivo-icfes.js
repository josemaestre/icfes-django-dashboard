(function () {
  let trendChart = null;
  let refreshSeq = 0;

  function getAno() {
    const el = document.getElementById('story-ano');
    return el ? parseInt(el.value, 10) : 2024;
  }

  function getDepto() {
    const el = document.getElementById('story-depto');
    return el ? el.value : '';
  }

  function fmtNum(value, digits = 1) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '--';
    return Number(value).toFixed(digits);
  }

  function withBust(url) {
    return url + (url.includes('?') ? '&' : '?') + `_ts=${Date.now()}`;
  }

  function setActiveFilterLabel() {
    const ano = getAno();
    const depto = getDepto();
    const el = document.getElementById('story-active-filter');
    if (!el) return;
    el.textContent = `Filtro: ${ano} · ${depto || 'Todo Colombia'}`;
  }

  function loadResumen(seq) {
    const ano = getAno();
    const depto = getDepto();
    fetch(withBust(`/icfes/api/story/resumen/?ano=${ano}${depto ? `&departamento=${encodeURIComponent(depto)}` : ''}`), { cache: 'no-store' })
      .then((r) => r.json())
      .then((d) => {
        if (seq !== refreshSeq) return;
        document.getElementById('kpi-promedio').textContent = fmtNum(d.promedio_nacional, 1);
        document.getElementById('kpi-brecha').textContent = fmtNum(d.brecha_sector_publico_privado, 1);
        document.getElementById('kpi-riesgo').textContent = d.colegios_alto_riesgo
          ? Number(d.colegios_alto_riesgo).toLocaleString()
          : '0';
        document.getElementById('kpi-estudiantes').textContent = d.total_estudiantes
          ? Number(d.total_estudiantes).toLocaleString()
          : '0';
      })
      .catch(() => {
        if (seq !== refreshSeq) return;
        document.getElementById('kpi-promedio').textContent = '--';
      });
  }

  function loadSerieAnual(seq) {
    const depto = getDepto();
    fetch(withBust(`/icfes/api/story/serie-anual/${depto ? `?departamento=${encodeURIComponent(depto)}` : ''}`), { cache: 'no-store' })
      .then((r) => r.json())
      .then((rows) => {
        if (seq !== refreshSeq) return;
        const serie = [...rows].sort((a, b) => Number(a.ano) - Number(b.ano));
        const labels = serie.map((r) => r.ano);
        const promedio = serie.map((r) => r.promedio_nacional || null);
        const brecha = serie.map((r) => r.brecha_sector_publico_privado || null);

        const ctx = document.getElementById('story-trend-chart').getContext('2d');
        if (trendChart) trendChart.destroy();
        if (!labels.length) {
          ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
          return;
        }
        trendChart = new Chart(ctx, {
          type: 'line',
          data: {
            labels: labels,
            datasets: [
              {
                label: 'Promedio Nacional',
                data: promedio,
                borderColor: '#2563eb',
                backgroundColor: '#2563eb20',
                yAxisID: 'y',
                tension: 0.3,
              },
              {
                label: 'Brecha Sector',
                data: brecha,
                borderColor: '#dc2626',
                backgroundColor: '#dc262620',
                yAxisID: 'y2',
                tension: 0.3,
              }
            ]
          },
          options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            scales: {
              y: { position: 'left', title: { display: true, text: 'Puntaje' } },
              y2: { position: 'right', grid: { display: false }, title: { display: true, text: 'Brecha (pts)' } },
            }
          }
        });
      })
      .catch(() => {
        if (seq !== refreshSeq) return;
        const ctx = document.getElementById('story-trend-chart').getContext('2d');
        if (trendChart) trendChart.destroy();
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
      });
  }

  function loadBrechas(seq) {
    const ano = getAno();
    const depto = getDepto();
    fetch(withBust(`/icfes/api/story/brechas/?ano=${ano}${depto ? `&departamento=${encodeURIComponent(depto)}` : ''}`), { cache: 'no-store' })
      .then((r) => r.json())
      .then((d) => {
        if (seq !== refreshSeq) return;
        const list = document.getElementById('story-brechas-list');
        const items = (d.brechas || []).map((b) => {
          const val = fmtNum(b.brecha_absoluta_puntos, 1);
          return `<div class="mb-2"><strong>${b.tipo_brecha}:</strong> ${val} pts <span class="text-muted">(${b.tendencia_brecha || 'N/A'})</span></div>`;
        }).join('');
        const conv = d.convergencia_regional || {};
        const convHtml = conv.estado_convergencia
          ? `<hr><div><strong>Convergencia regional:</strong> ${conv.estado_convergencia}</div><div><strong>Brecha líder-rezagada:</strong> ${fmtNum(conv.brecha_lider_rezagado, 1)} pts</div>`
          : '';
        list.innerHTML = items + convHtml;
      })
      .catch(() => {
        if (seq !== refreshSeq) return;
        document.getElementById('story-brechas-list').textContent = 'No fue posible cargar brechas.';
      });
  }

  function loadPriorizacion(seq) {
    const ano = getAno();
    const depto = getDepto();
    const url = `/icfes/api/story/priorizacion/?ano=${ano}&limit=30${depto ? `&departamento=${encodeURIComponent(depto)}` : ''}`;
    const tbody = document.querySelector('#story-prioridad-table tbody');
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">Cargando...</td></tr>';

    fetch(withBust(url), { cache: 'no-store' })
      .then((r) => r.json())
      .then((d) => {
        if (seq !== refreshSeq) return;
        tbody.innerHTML = '';
        const items = d.items || [];
        if (!items.length) {
          tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">Sin datos para este filtro</td></tr>';
          return;
        }
        items.forEach((it) => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${it.codigo_dane || ''}</td>
            <td>${it.nombre_colegio || ''}</td>
            <td>${it.departamento || ''}</td>
            <td>${it.municipio || ''}</td>
            <td>${fmtNum(it.avg_punt_global_actual, 1)}</td>
            <td>${fmtNum((it.prob_declive || 0) * 100, 1)}%</td>
            <td>${fmtNum(it.gap_municipio_promedio, 1)}</td>
            <td><span class="badge" style="background:#0f172a;color:#ffffff;">${fmtNum(it.priority_score, 3)}</span></td>
          `;
          tbody.appendChild(tr);
        });
      })
      .catch(() => {
        if (seq !== refreshSeq) return;
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Error cargando priorización</td></tr>';
      });
  }

  function refreshAll() {
    refreshSeq += 1;
    const seq = refreshSeq;
    setActiveFilterLabel();
    loadResumen(seq);
    loadSerieAnual(seq);
    loadBrechas(seq);
    loadPriorizacion(seq);
  }

  const applyBtn = document.getElementById('story-apply');
  const anoEl = document.getElementById('story-ano');
  const deptoEl = document.getElementById('story-depto');
  if (applyBtn) {
    applyBtn.addEventListener('click', refreshAll);
    if (anoEl) anoEl.addEventListener('change', refreshAll);
    if (deptoEl) deptoEl.addEventListener('change', refreshAll);
    refreshAll();
  }
})();
