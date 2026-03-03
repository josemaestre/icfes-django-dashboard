/**
 * Dashboard Social — Contexto Socioeconómico ICFES
 * NBI (pobreza) · Conectividad · Presidentes · Generaciones
 */
(function () {
    'use strict';

    // ── Paleta de colores ─────────────────────────────────────────────────
    const COLORS = {
        danger:  '#f1556c',
        warning: '#f7b731',
        info:    '#4fc6e1',
        success: '#1abc9c',
        primary: '#6559cc',
        dark:    '#343a40',
        muted:   '#adb5bd',
    };

    const NBI_COLORS = [COLORS.success, COLORS.warning, COLORS.danger, '#6f42c1'];

    // ── Helpers ───────────────────────────────────────────────────────────
    function apexDefaults(extra) {
        return Object.assign({
            chart: { toolbar: { show: false }, fontFamily: 'inherit' },
            dataLabels: { enabled: false },
            grid: { borderColor: '#f1f1f1' },
            tooltip: { theme: 'light' },
        }, extra);
    }

    // ══════════════════════════════════════════════════════════════════════
    // 0. KPIs del hero
    // ══════════════════════════════════════════════════════════════════════
    fetch('/icfes/api/social/kpis/')
        .then(r => r.json())
        .then(d => {
            document.getElementById('kpi-mun-nbi').textContent  = (d.municipios_con_nbi  || '--').toLocaleString();
            document.getElementById('kpi-nbi-prom').textContent = (d.nbi_nacional_prom   || '--') + '%';
            document.getElementById('kpi-mun-inet').textContent = (d.municipios_con_internet || '--').toLocaleString();
            document.getElementById('kpi-brecha').textContent   = (d.brecha_priv_pub_2024|| '--') + ' pts';
        })
        .catch(() => {});

    // ══════════════════════════════════════════════════════════════════════
    // 1a. Bar chart: 4 categorías NBI vs puntaje (2024)
    // ══════════════════════════════════════════════════════════════════════
    fetch('/icfes/api/social/nbi-brechas/')
        .then(r => r.json())
        .then(rows => {
            // Separar 2010 y 2024
            const data2024 = rows.filter(r => r.anio === 2024).sort((a, b) => a.orden - b.orden);
            const data2010 = rows.filter(r => r.anio === 2010).sort((a, b) => a.orden - b.orden);

            const cats = data2024.map(r => r.cat_nbi);

            // Bar chart horizontal
            new ApexCharts(document.getElementById('chart-nbi-bars'), apexDefaults({
                chart: { type: 'bar', height: 260, toolbar: { show: false }, fontFamily: 'inherit' },
                plotOptions: { bar: { horizontal: true, borderRadius: 4, dataLabels: { position: 'top' } } },
                dataLabels: { enabled: true, formatter: v => v + ' pts', offsetX: 30, style: { colors: [COLORS.dark], fontSize: '12px' } },
                series: [{ name: 'Puntaje 2024', data: data2024.map(r => r.puntaje_prom) }],
                xaxis: { categories: cats, min: 180, max: 280 },
                colors: NBI_COLORS,
                fill: { type: 'solid' },
                legend: { show: false },
                tooltip: { y: { formatter: v => v + ' pts prom.' } },
            })).render();

            // Tabla de evolución 2010 vs 2024
            const tbody = document.getElementById('tbody-nbi-evolucion');
            if (!tbody) return;
            const rows2010map = {};
            data2010.forEach(r => rows2010map[r.cat_nbi] = r);
            tbody.innerHTML = data2024.map(r => {
                const p10 = rows2010map[r.cat_nbi] ? rows2010map[r.cat_nbi].puntaje_prom : null;
                const delta = p10 !== null ? (r.puntaje_prom - p10).toFixed(1) : '--';
                const cls   = parseFloat(delta) >= 0 ? 'text-success' : 'text-danger';
                const arrow = parseFloat(delta) >= 0 ? '▲' : '▼';
                return `<tr>
                    <td class="ps-3 fw-medium">${r.cat_nbi}</td>
                    <td class="text-center">${p10 !== null ? p10 : '--'}</td>
                    <td class="text-center">${r.puntaje_prom}</td>
                    <td class="text-center ${cls} fw-bold">${arrow} ${delta}</td>
                    <td class="text-center text-muted">${(r.n_municipios || '--').toLocaleString()}</td>
                </tr>`;
            }).join('');
        })
        .catch(() => {});

    // ══════════════════════════════════════════════════════════════════════
    // 1b. Scatter: municipios NBI vs puntaje + regresión lineal
    // ══════════════════════════════════════════════════════════════════════
    fetch('/icfes/api/social/scatter-municipios/')
        .then(r => r.json())
        .then(rows => {
            const pts = rows.map(r => ({
                x: r.nbi,
                y: r.puntaje,
                label: r.municipio + ' (' + r.departamento + ')',
                internet: r.pct_internet,
            }));

            // ── Regresión lineal (mínimos cuadrados) ──────────────────
            const n    = pts.length;
            const sumX  = pts.reduce((s, p) => s + p.x,       0);
            const sumY  = pts.reduce((s, p) => s + p.y,       0);
            const sumXY = pts.reduce((s, p) => s + p.x * p.y, 0);
            const sumX2 = pts.reduce((s, p) => s + p.x * p.x, 0);
            const slope     = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
            const intercept = (sumY - slope * sumX) / n;

            // R²
            const yMean  = sumY / n;
            const ssTot  = pts.reduce((s, p) => s + (p.y - yMean) ** 2,                  0);
            const ssRes  = pts.reduce((s, p) => s + (p.y - (intercept + slope * p.x)) ** 2, 0);
            const r2     = (1 - ssRes / ssTot).toFixed(2);

            // Caída por cada 10 pts de NBI
            const caida10 = Math.abs(slope * 10).toFixed(1);

            const minX = Math.min(...pts.map(p => p.x));
            const maxX = Math.max(...pts.map(p => p.x));
            const trendLine = [
                [minX, +(intercept + slope * minX).toFixed(1)],
                [maxX, +(intercept + slope * maxX).toFixed(1)],
            ];

            new ApexCharts(document.getElementById('chart-scatter'), {
                chart: { type: 'line', height: 280, toolbar: { show: false }, fontFamily: 'inherit',
                         zoom: { type: 'xy', enabled: true } },
                series: [
                    { name: 'Municipio',        type: 'scatter', data: pts.map(p => [p.x, p.y]) },
                    { name: `Tendencia (r²=${r2})`, type: 'line', data: trendLine },
                ],
                xaxis: { type: 'numeric', title: { text: 'NBI % pobreza' }, min: 0, max: 100, tickAmount: 10 },
                yaxis: { title: { text: 'Puntaje ICFES 2024' }, min: 160, max: 320 },
                colors: [COLORS.primary, COLORS.danger],
                stroke: { width: [0, 2], dashArray: [0, 6], curve: 'straight' },
                markers: { size: [4, 0], strokeWidth: 0, fillOpacity: 0.6 },
                legend: { position: 'top' },
                dataLabels: { enabled: false },
                grid: { borderColor: '#f1f1f1' },
                annotations: {
                    points: [{
                        x: 50, y: +(intercept + slope * 50).toFixed(0),
                        marker: { size: 0 },
                        label: {
                            text: `−${caida10} pts cada 10% NBI`,
                            borderColor: COLORS.danger,
                            style: { color: '#fff', background: COLORS.danger, fontSize: '10px',
                                     padding: { left: 5, right: 5, top: 3, bottom: 3 } },
                            offsetY: -12,
                        },
                    }],
                },
                tooltip: {
                    custom: ({ seriesIndex, dataPointIndex }) => {
                        if (seriesIndex === 1) return '';
                        const p = pts[dataPointIndex];
                        return `<div class="p-2 small">
                            <strong>${p.label}</strong><br>
                            NBI: ${p.x}% · Puntaje: ${p.y}<br>
                            Internet: ${p.internet}%
                        </div>`;
                    },
                },
            }).render();
        })
        .catch(() => {});

    // ══════════════════════════════════════════════════════════════════════
    // 2. Tabla de colegios héroes
    // ══════════════════════════════════════════════════════════════════════
    function loadHeroes(nbiMin) {
        document.getElementById('tbody-heroes').innerHTML =
            '<tr><td colspan="9" class="text-center text-muted py-3"><div class="spinner-border spinner-border-sm me-2"></div>Cargando...</td></tr>';
        fetch('/icfes/api/social/colegios-heroes/?nbi_min=' + nbiMin)
            .then(r => r.json())
            .then(rows => {
                document.getElementById('tbody-heroes').innerHTML = rows.map((r, i) => {
                    const badgeClass = r.sector && r.sector.toUpperCase().includes('OFICIAL') && !r.sector.toUpperCase().includes('NO')
                        ? 'badge bg-primary-subtle text-primary'
                        : 'badge bg-warning-subtle text-warning';
                    const nbiColor = r.pct_nbi >= 60 ? 'text-danger fw-bold' : r.pct_nbi >= 50 ? 'text-warning fw-bold' : '';
                    return `<tr>
                        <td class="ps-3 text-muted">${i + 1}</td>
                        <td class="fw-medium">${r.nombre_colegio}</td>
                        <td>${r.municipio}</td>
                        <td class="text-muted">${r.departamento}</td>
                        <td class="text-center ${nbiColor}">${r.pct_nbi}%</td>
                        <td class="text-center fw-bold text-primary">${r.puntaje}</td>
                        <td class="text-center">#${(r.ranking_nacional || '--').toLocaleString()}</td>
                        <td class="text-center"><span class="${badgeClass}">${r.sector}</span></td>
                        <td class="text-center text-muted">${(r.total_estudiantes || '--').toLocaleString()}</td>
                    </tr>`;
                }).join('') || '<tr><td colspan="9" class="text-center text-muted py-3">Sin resultados</td></tr>';
            })
            .catch(() => {
                document.getElementById('tbody-heroes').innerHTML =
                    '<tr><td colspan="9" class="text-center text-danger py-3">Error cargando datos</td></tr>';
            });
    }

    loadHeroes(40);
    document.getElementById('filter-nbi-heroes').addEventListener('change', function () {
        loadHeroes(this.value);
    });

    // ══════════════════════════════════════════════════════════════════════
    // 3. Conectividad vs materias
    // ══════════════════════════════════════════════════════════════════════
    fetch('/icfes/api/social/conectividad-materias/')
        .then(r => r.json())
        .then(d => {
            const corrs = d.correlaciones || [];
            const tiers = d.tiers || [];

            // Bar chart horizontal: correlaciones
            new ApexCharts(document.getElementById('chart-correlacion-materias'), apexDefaults({
                chart: { type: 'bar', height: 260, toolbar: { show: false }, fontFamily: 'inherit' },
                plotOptions: { bar: { horizontal: true, borderRadius: 4, dataLabels: { position: 'top' } } },
                dataLabels: { enabled: true, formatter: v => v, offsetX: 30, style: { colors: [COLORS.dark], fontSize: '12px' } },
                series: [{ name: 'Correlación Pearson', data: corrs.map(r => r.correlacion) }],
                xaxis: { categories: corrs.map(r => r.materia), min: 0, max: 0.25 },
                colors: [COLORS.info],
                tooltip: { y: { formatter: v => 'r = ' + v } },
                legend: { show: false },
            })).render();

            // Bar chart: tiers conectividad
            new ApexCharts(document.getElementById('chart-conectividad-tiers'), apexDefaults({
                chart: { type: 'bar', height: 260, toolbar: { show: false }, fontFamily: 'inherit' },
                plotOptions: { bar: { borderRadius: 4, columnWidth: '50%', dataLabels: { position: 'top' } } },
                dataLabels: { enabled: true, formatter: v => v + ' pts', style: { colors: [COLORS.dark], fontSize: '12px' }, offsetY: -20 },
                series: [{ name: 'Puntaje promedio', data: tiers.map(r => r.puntaje) }],
                xaxis: { categories: tiers.map(r => r.nivel) },
                yaxis: { min: 210, max: 265 },
                colors: [COLORS.info],
                legend: { show: false },
            })).render();
        })
        .catch(() => {});

    // ══════════════════════════════════════════════════════════════════════
    // 4. Serie histórica con anotaciones presidenciales
    // ══════════════════════════════════════════════════════════════════════
    fetch('/icfes/api/social/serie-historica-contexto/')
        .then(r => r.json())
        .then(rows => {
            const PRES_COLORS = {
                'Ernesto Samper':      '#dbeafe',
                'Andrés Pastrana':     '#fef9c3',
                'Álvaro Uribe Vélez':  '#fee2e2',
                'Juan Manuel Santos':  '#dcfce7',
                'Iván Duque Márquez':  '#ede9fe',
                'Gustavo Petro':       '#ffedd5',
            };
            const PRES_SHORT = {
                'Ernesto Samper':      'Samper',
                'Andrés Pastrana':     'Pastrana',
                'Álvaro Uribe Vélez':  'Uribe',
                'Juan Manuel Santos':  'Santos',
                'Iván Duque Márquez':  'Duque',
                'Gustavo Petro':       'Petro',
            };

            // Excluir pre-2000: escala diferente (formato ICFES anterior, no comparable)
            const dispRows = rows.filter(r => r.anio >= 2000);

            const anios   = dispRows.map(r => r.anio);
            const global_ = dispRows.map(r => r.prom_global);
            const ingles  = dispRows.map(r => r.prom_ingles);

            // ── Bandas de períodos presidenciales ─────────────────────
            const bandAnnotations = [];
            let curPres = null, presStart = null;
            dispRows.forEach((r, i) => {
                if (r.presidente !== curPres) {
                    if (curPres !== null) {
                        bandAnnotations.push({
                            x: presStart,
                            x2: rows[i - 1].anio,
                            fillColor: PRES_COLORS[curPres] || '#f1f5f9',
                            opacity: 0.55,
                            label: {
                                text: PRES_SHORT[curPres] || curPres,
                                position: 'top',
                                orientation: 'horizontal',
                                offsetY: 18,
                                style: {
                                    fontSize: '10px', fontWeight: 700,
                                    background: PRES_COLORS[curPres] || '#f1f5f9',
                                    color: '#374151',
                                    padding: { left: 4, right: 4, top: 2, bottom: 2 },
                                },
                            },
                        });
                    }
                    curPres = r.presidente;
                    presStart = r.anio;
                }
            });
            // Cerrar último período
            if (curPres) {
                bandAnnotations.push({
                    x: presStart,
                    x2: dispRows[dispRows.length - 1].anio,
                    fillColor: PRES_COLORS[curPres] || '#f1f5f9',
                    opacity: 0.55,
                    label: {
                        text: PRES_SHORT[curPres] || curPres,
                        position: 'top',
                        orientation: 'horizontal',
                        offsetY: 18,
                        style: {
                            fontSize: '10px', fontWeight: 700,
                            background: PRES_COLORS[curPres] || '#f1f5f9',
                            color: '#374151',
                            padding: { left: 4, right: 4, top: 2, bottom: 2 },
                        },
                    },
                });
            }

            // ── Líneas de eventos clave ────────────────────────────────
            const lineAnnotations = [];
            dispRows.forEach(r => {
                if (r.covid) lineAnnotations.push({
                    x: r.anio,
                    borderColor: COLORS.danger,
                    borderWidth: 2,
                    strokeDashArray: 5,
                    label: {
                        text: 'COVID-19',
                        position: 'bottom',
                        offsetY: -45,
                        borderColor: COLORS.danger,
                        style: { color: '#fff', background: COLORS.danger, fontSize: '10px',
                                 padding: { left: 4, right: 4, top: 2, bottom: 2 } },
                    },
                });
                if (r.paro) lineAnnotations.push({
                    x: r.anio,
                    borderColor: COLORS.warning,
                    borderWidth: 2,
                    strokeDashArray: 5,
                    label: {
                        text: 'Paro Nal.',
                        position: 'bottom',
                        offsetY: -10,
                        borderColor: COLORS.warning,
                        style: { color: '#fff', background: COLORS.warning, fontSize: '10px',
                                 padding: { left: 4, right: 4, top: 2, bottom: 2 } },
                    },
                });
                if (r.anio === 2016) lineAnnotations.push({
                    x: r.anio,
                    borderColor: COLORS.success,
                    borderWidth: 2,
                    strokeDashArray: 5,
                    label: {
                        text: 'Acuerdo de Paz',
                        position: 'bottom',
                        offsetY: -80,
                        borderColor: COLORS.success,
                        style: { color: '#fff', background: COLORS.success, fontSize: '10px',
                                 padding: { left: 4, right: 4, top: 2, bottom: 2 } },
                    },
                });
                if (r.anio === 2000) lineAnnotations.push({
                    x: r.anio,
                    borderColor: COLORS.muted,
                    borderWidth: 1,
                    strokeDashArray: 3,
                    label: {
                        text: 'Nuevo formato ICFES',
                        position: 'top',
                        offsetY: -5,
                        borderColor: COLORS.muted,
                        style: { color: '#fff', background: COLORS.muted, fontSize: '9px',
                                 padding: { left: 3, right: 3, top: 2, bottom: 2 } },
                    },
                });
                if (r.anio === 2010) lineAnnotations.push({
                    x: r.anio,
                    borderColor: COLORS.muted,
                    borderWidth: 1,
                    strokeDashArray: 3,
                    label: {
                        text: 'Saber 11',
                        position: 'top',
                        borderColor: COLORS.muted,
                        style: { color: '#fff', background: COLORS.muted, fontSize: '9px',
                                 padding: { left: 3, right: 3, top: 2, bottom: 2 } },
                    },
                });
            });

            new ApexCharts(document.getElementById('chart-serie-historica'), {
                chart: { type: 'line', height: 420, toolbar: { show: true }, fontFamily: 'inherit', zoom: { enabled: false } },
                series: [
                    { name: 'Puntaje Global', data: global_ },
                    { name: 'Inglés', data: ingles },
                ],
                xaxis: { categories: anios, title: { text: 'Año ICFES' }, tickAmount: 14 },
                yaxis: [
                    {
                        seriesName: 'Puntaje Global',
                        title: { text: 'Puntaje global' },
                        min: 140, max: 280,
                    },
                    {
                        seriesName: 'Inglés',
                        opposite: true,
                        title: { text: 'Inglés (0–100)' },
                        min: 30, max: 80,
                    },
                ],
                colors: [COLORS.primary, COLORS.info],
                stroke: { width: [3, 2], curve: 'smooth', dashArray: [0, 5] },
                markers: { size: 3 },
                annotations: { xaxis: [...bandAnnotations, ...lineAnnotations] },
                legend: { position: 'top' },
                dataLabels: { enabled: false },
                grid: { borderColor: '#e5e7eb' },
                tooltip: {
                    shared: true,
                    x: {
                        formatter: v => {
                            const year = parseInt(v);
                            const row = dispRows.find(r => r.anio === year);
                            return row ? `${year} — ${row.presidente}` : String(v);
                        },
                    },
                    y: {
                        formatter: (v, { seriesIndex }) =>
                            seriesIndex === 1
                                ? v + ' pts prom. (escala Inglés)'
                                : v + ' pts prom.',
                    },
                },
            }).render();
        })
        .catch(err => console.error('[Social] serie-historica error:', err));

    // ══════════════════════════════════════════════════════════════════════
    // 4b. Brecha privado/público por gobierno
    // ══════════════════════════════════════════════════════════════════════
    fetch('/icfes/api/social/brecha-sector-gobierno/')
        .then(r => r.json())
        .then(rows => {
            const gobiernos = rows.map(r => r.gobierno);

            // Brecha horizontal bar
            new ApexCharts(document.getElementById('chart-brecha-gobierno'), apexDefaults({
                chart: { type: 'bar', height: 260, toolbar: { show: false }, fontFamily: 'inherit' },
                plotOptions: { bar: { horizontal: true, borderRadius: 4, dataLabels: { position: 'top' } } },
                dataLabels: { enabled: true, formatter: v => '+' + v + ' pts', offsetX: 40, style: { colors: [COLORS.dark], fontSize: '12px' } },
                series: [{ name: 'Brecha privado vs público', data: rows.map(r => r.brecha) }],
                xaxis: { categories: gobiernos, min: 0, max: 40 },
                colors: rows.map(r => r.brecha >= 30 ? COLORS.danger : r.brecha >= 20 ? COLORS.warning : COLORS.success),
                legend: { show: false },
                tooltip: { y: { formatter: v => v + ' puntos favor privado' } },
            })).render();

            // Grouped bar: oficial vs privado
            new ApexCharts(document.getElementById('chart-sector-gobierno'), apexDefaults({
                chart: { type: 'bar', height: 260, toolbar: { show: false }, fontFamily: 'inherit' },
                plotOptions: { bar: { borderRadius: 3, columnWidth: '60%', grouped: true } },
                series: [
                    { name: 'Oficial', data: rows.map(r => r.oficial) },
                    { name: 'Privado', data: rows.map(r => r.privado) },
                ],
                xaxis: { categories: gobiernos },
                yaxis: { min: 200, max: 290 },
                colors: [COLORS.primary, COLORS.warning],
                legend: { position: 'top' },
                dataLabels: { enabled: false },
            })).render();
        })
        .catch(() => {});

    // ══════════════════════════════════════════════════════════════════════
    // 5. Eras tecnológicas + postconflicto
    // ══════════════════════════════════════════════════════════════════════
    fetch('/icfes/api/social/era-tecnologica/')
        .then(r => r.json())
        .then(d => {
            const eras = d.eras || [];
            const post = d.postconflicto || [];

            if (!eras.length) return;

            // Eras chart: 3 series grouped bar — Inglés y Mat en escala 0-100 comparable
            // Global en eje Y secundario (escala propia 150-270)
            new ApexCharts(document.getElementById('chart-eras'), {
                chart: { type: 'line', height: 280, toolbar: { show: false }, fontFamily: 'inherit' },
                plotOptions: { bar: { borderRadius: 4, columnWidth: '45%' } },
                series: [
                    { name: 'Inglés', type: 'column', data: eras.map(r => r.prom_ingles) },
                    { name: 'Matemáticas', type: 'column', data: eras.map(r => r.prom_mat) },
                    { name: 'Puntaje Global', type: 'line', data: eras.map(r => r.prom_global) },
                ],
                xaxis: { categories: eras.map(r => r.era) },
                yaxis: [
                    {
                        title: { text: 'Puntaje por materia' },
                        min: 0, max: 60,
                        labels: { formatter: v => v.toFixed(0) },
                    },
                    { show: false },   // columnas comparten primer eje
                    {
                        opposite: true,
                        title: { text: 'Puntaje global' },
                        min: 140, max: 270,
                        labels: { formatter: v => v.toFixed(0) },
                    },
                ],
                colors: [COLORS.info, COLORS.success, COLORS.primary],
                stroke: { width: [0, 0, 3], curve: 'smooth' },
                markers: { size: [0, 0, 5] },
                fill: { opacity: [1, 1, 1] },
                legend: { position: 'top' },
                dataLabels: { enabled: false },
                tooltip: {
                    shared: true,
                    custom: ({ dataPointIndex }) => {
                        const r = eras[dataPointIndex];
                        return `<div class="p-2 small">
                            <strong>${r.era}</strong><br>
                            Global: <strong>${r.prom_global}</strong> pts<br>
                            Inglés: <strong>${r.prom_ingles}</strong> pts<br>
                            Matemáticas: <strong>${r.prom_mat}</strong> pts
                        </div>`;
                    },
                },
                grid: { borderColor: '#f1f1f1' },
            }).render();

            // Bar chart horizontal: postconflicto (cambio) con colores por barra
            if (post.length > 0) {
                new ApexCharts(document.getElementById('chart-postconflicto'), {
                    chart: { type: 'bar', height: 280, toolbar: { show: false }, fontFamily: 'inherit' },
                    plotOptions: { bar: { horizontal: true, borderRadius: 4, distributed: true } },
                    dataLabels: {
                        enabled: true,
                        formatter: v => (v >= 0 ? '+' : '') + v + ' pts',
                        style: { colors: ['#343a40'], fontSize: '11px' },
                    },
                    series: [{ name: 'Cambio post-2016', data: post.map(r => r.cambio) }],
                    xaxis: {
                        categories: post.map(r => r.dpto),
                        title: { text: 'Puntos de cambio (2017+ vs 2010-2016)' },
                    },
                    colors: post.map(r => r.cambio >= 0 ? COLORS.success : COLORS.danger),
                    legend: { show: false },
                    grid: { borderColor: '#f1f1f1' },
                    tooltip: {
                        custom: ({ dataPointIndex }) => {
                            const r = post[dataPointIndex];
                            return `<div class="p-2 small">
                                <strong>${r.dpto}</strong><br>
                                Antes 2016: ${r.antes_2016} pts<br>
                                Después 2016: ${r.despues_2016} pts<br>
                                Cambio: <strong>${r.cambio >= 0 ? '+' : ''}${r.cambio} pts</strong>
                            </div>`;
                        },
                    },
                }).render();
            }
        })
        .catch(err => console.error('[Social] era-tecnologica error:', err));

    // ══════════════════════════════════════════════════════════════════════
    // 6. Estrato socioeconómico — snapshot 2024 + evolución E1 vs E6
    // ══════════════════════════════════════════════════════════════════════
    fetch('/icfes/api/social/estrato/')
        .then(r => r.json())
        .then(d => {
            const snap = (d.snapshot  || []).filter(r => r.orden <= 6).sort((a, b) => a.orden - b.orden);
            const evol = d.evolucion || [];

            if (!snap.length) return;

            // ── KPIs ──────────────────────────────────────────────────
            const e1 = snap.find(r => r.orden === 1);
            const e6 = snap.find(r => r.orden === 6);
            const s0 = snap.find(r => r.orden === 0);  // Sin Estrato

            if (e1 && e6) {
                document.getElementById('kpi-est-brecha-global').textContent =
                    (e6.global - e1.global).toFixed(1) + ' pts';
                document.getElementById('kpi-est-brecha-ingles').textContent =
                    (e6.ingles - e1.ingles).toFixed(1) + ' pts';
            }
            if (s0) document.getElementById('kpi-est-sin-estrato').textContent = s0.global + ' pts';
            if (e1) document.getElementById('kpi-est-n-e1').textContent =
                (e1.n_estudiantes || 0).toLocaleString();

            // ── Barras horizontales E1-E6 (coloreadas por estrato) ───
            const ESTRATO_COLORS = ['#f1556c', '#f7b731', '#f7b731', '#4fc6e1', '#1abc9c', '#1abc9c'];
            const labels = snap.map(r => r.estrato);

            new ApexCharts(document.getElementById('chart-estrato-bars'), {
                chart: { type: 'bar', height: 290, toolbar: { show: false }, fontFamily: 'inherit' },
                plotOptions: { bar: { horizontal: true, borderRadius: 4, distributed: true } },
                series: [{ name: 'Puntaje global', data: snap.map(r => r.global) }],
                xaxis: { categories: labels, min: 210, max: 285 },
                colors: ESTRATO_COLORS,
                dataLabels: {
                    enabled: true,
                    formatter: v => v + ' pts',
                    offsetX: 32,
                    style: { fontSize: '11px', colors: ['#374151'] },
                },
                legend: { show: false },
                grid: { borderColor: '#f1f1f1' },
                tooltip: {
                    custom: ({ dataPointIndex }) => {
                        const r = snap[dataPointIndex];
                        return `<div class="p-2 small">
                            <strong>${r.estrato}</strong><br>
                            Global: ${r.global} pts<br>
                            Inglés: ${r.ingles} pts<br>
                            Matemáticas: ${r.mat} pts<br>
                            Estudiantes: ${(r.n_estudiantes || 0).toLocaleString()}
                        </div>`;
                    },
                },
            }).render();

            // ── Evolución E1 vs E6 (área sombreada = brecha) ────────
            const e1rows = evol.filter(r => r.estrato === 'Estrato 1').sort((a, b) => a.anio - b.anio);
            const e6rows = evol.filter(r => r.estrato === 'Estrato 6').sort((a, b) => a.anio - b.anio);
            const aniosEvol = e1rows.map(r => r.anio);

            new ApexCharts(document.getElementById('chart-estrato-evolucion'), {
                chart: { type: 'area', height: 290, toolbar: { show: false }, fontFamily: 'inherit' },
                series: [
                    { name: 'Estrato 6', data: e6rows.map(r => r.global) },
                    { name: 'Estrato 1', data: e1rows.map(r => r.global) },
                ],
                xaxis: { categories: aniosEvol, title: { text: 'Año' }, tickAmount: 9 },
                yaxis: { title: { text: 'Puntaje global promedio' }, min: 230, max: 290 },
                colors: [COLORS.success, COLORS.danger],
                stroke: { width: [3, 3], curve: 'smooth' },
                fill: {
                    type: 'gradient',
                    gradient: { shadeIntensity: 1, opacityFrom: 0.3, opacityTo: 0.05, stops: [0, 100] },
                },
                markers: { size: 4 },
                legend: { position: 'top' },
                dataLabels: { enabled: false },
                grid: { borderColor: '#f1f1f1' },
                tooltip: {
                    shared: true,
                    x: { formatter: v => 'Año ' + v },
                    y: { formatter: v => v + ' pts' },
                },
                annotations: {
                    yaxis: [{
                        y: e6rows.at(-1)?.global || 270,
                        y2: e1rows.at(-1)?.global || 245,
                        fillColor: '#fee2e2',
                        opacity: 0.2,
                        label: { text: 'Brecha 2024', borderColor: COLORS.danger,
                                 style: { color: '#fff', background: COLORS.danger, fontSize: '10px' } },
                    }],
                },
            }).render();
        })
        .catch(err => console.error('[Social] estrato error:', err));

    // ══════════════════════════════════════════════════════════════════════
    // 7. Mapa coroplético — departamentos Colombia
    // ══════════════════════════════════════════════════════════════════════
    if (typeof L === 'undefined') {
        console.warn('[Social] Leaflet no cargado — mapa no disponible');
    } else {
        // Escala de color para puntaje (190=rojo → 280=verde)
        function colorPuntaje(v) {
            if (v == null) return '#d1d5db';
            if (v >= 265) return '#059669';
            if (v >= 255) return '#10b981';
            if (v >= 248) return '#34d399';
            if (v >= 240) return '#f7b731';
            if (v >= 230) return '#ff9f43';
            if (v >= 218) return '#f1556c';
            return '#b91c1c';
        }

        // Escala de color para NBI (0=verde → 70=rojo)
        function colorNBI(v) {
            if (v == null) return '#d1d5db';
            if (v <= 8)  return '#059669';
            if (v <= 15) return '#10b981';
            if (v <= 22) return '#34d399';
            if (v <= 30) return '#f7b731';
            if (v <= 40) return '#ff9f43';
            if (v <= 55) return '#f1556c';
            return '#b91c1c';
        }

        // Escala para inglés (38=rojo → 60=verde)
        function colorIngles(v) {
            if (v == null) return '#d1d5db';
            if (v >= 57) return '#059669';
            if (v >= 53) return '#10b981';
            if (v >= 50) return '#34d399';
            if (v >= 47) return '#f7b731';
            if (v >= 44) return '#ff9f43';
            if (v >= 41) return '#f1556c';
            return '#b91c1c';
        }

        let mapaMode = 'puntaje';
        let geojsonLayer = null;
        let dptoData = {};

        const map = L.map('mapa-colombia', {
            center: [4.5, -74.0],
            zoom: 5,
            zoomControl: true,
            attributionControl: false,
        });

        // Tile base minimalista
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap, CartoDB',
            subdomains: 'abcd', maxZoom: 10,
        }).addTo(map);

        function getColorFor(dpto, mode) {
            const d = dptoData[dpto];
            if (!d) return '#d1d5db';
            if (mode === 'nbi')    return colorNBI(d.nbi);
            if (mode === 'ingles') return colorIngles(d.ingles);
            return colorPuntaje(d.puntaje);
        }

        function styleFeature(feature) {
            const cod = feature.properties.DPTO;
            return {
                fillColor:   getColorFor(cod, mapaMode),
                fillOpacity: 0.8,
                color:       '#ffffff',
                weight:      1.5,
            };
        }

        function buildPopup(cod) {
            const d = dptoData[cod];
            if (!d) return `<strong>${cod}</strong><br>Sin datos`;
            const nbiTxt = d.nbi != null ? d.nbi + '%' : 'N/D';
            return `<div style="min-width:170px;font-size:13px;">
                <strong>${d.departamento}</strong><br>
                <hr style="margin:4px 0;">
                🏆 Ranking: <strong>#${d.ranking}</strong> de 33<br>
                📊 Puntaje: <strong>${d.puntaje}</strong> pts<br>
                🌐 Inglés: <strong>${d.ingles}</strong> pts<br>
                📐 Matemáticas: <strong>${d.matematicas}</strong> pts<br>
                🏚 NBI: <strong>${nbiTxt}</strong><br>
                🏫 Municipios: ${d.n_municipios}<br>
                👩‍🎓 Estudiantes: ${(d.total_est || 0).toLocaleString()}
            </div>`;
        }

        function onEachFeature(feature, layer) {
            const cod = feature.properties.DPTO;
            layer.bindPopup(buildPopup(cod), { maxWidth: 220 });
            layer.on('mouseover', function () {
                this.setStyle({ weight: 3, color: '#374151', fillOpacity: 0.95 });
                this.openPopup();
            });
            layer.on('mouseout', function () {
                geojsonLayer.resetStyle(this);
                this.closePopup();
            });
        }

        function updateLeyenda(mode) {
            const el = document.getElementById('mapa-leyenda');
            if (!el) return;
            const steps =
                mode === 'nbi'    ? [['≤8%','#059669'],['≤15%','#10b981'],['≤22%','#34d399'],['≤30%','#f7b731'],['≤40%','#ff9f43'],['≤55%','#f1556c'],['>55%','#b91c1c']] :
                mode === 'ingles' ? [['≥57','#059669'],['≥53','#10b981'],['≥50','#34d399'],['≥47','#f7b731'],['≥44','#ff9f43'],['≥41','#f1556c'],['<41','#b91c1c']] :
                                    [['≥265','#059669'],['≥255','#10b981'],['≥248','#34d399'],['≥240','#f7b731'],['≥230','#ff9f43'],['≥218','#f1556c'],['<218','#b91c1c']];
            el.innerHTML = steps.map(([lbl, col]) =>
                `<span class="d-flex align-items-center gap-1">
                    <span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:${col};"></span>
                    ${lbl}
                </span>`
            ).join('') + `<span class="text-muted ms-2">— ${mode === 'nbi' ? 'NBI %' : 'pts promedio'}</span>`;
        }

        // Cargar datos + GeoJSON en paralelo
        const mapaEl    = document.getElementById('mapa-colombia');
        const geojsonUrl = mapaEl.dataset.geojsonUrl;
        Promise.all([
            fetch('/icfes/api/social/mapa-departamentos/').then(r => r.json()),
            fetch(geojsonUrl).then(r => r.json()),
        ]).then(([rows, geojson]) => {
            // Construir lookup por cod_dpto
            rows.forEach(r => { dptoData[r.cod_dpto] = r; });

            geojsonLayer = L.geoJSON(geojson, {
                style:         styleFeature,
                onEachFeature: onEachFeature,
            }).addTo(map);

            map.fitBounds(geojsonLayer.getBounds(), { padding: [10, 10] });
            updateLeyenda('puntaje');
        }).catch(err => console.error('[Social] mapa error:', err));

        // Toggle de modo
        document.getElementById('mapa-toggle').addEventListener('click', function (e) {
            const btn = e.target.closest('[data-mode]');
            if (!btn || !geojsonLayer) return;
            mapaMode = btn.dataset.mode;
            // Actualizar botones
            this.querySelectorAll('button').forEach(b => {
                b.className = b === btn
                    ? 'btn btn-primary active'
                    : 'btn btn-outline-' + (b.dataset.mode === 'nbi' ? 'danger' : b.dataset.mode === 'ingles' ? 'info' : 'primary');
            });
            geojsonLayer.setStyle(styleFeature);
            updateLeyenda(mapaMode);
        });
    }

})();
