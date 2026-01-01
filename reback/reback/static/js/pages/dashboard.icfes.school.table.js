
// ============================================================================
// PERFORMANCE TABLE AND AI RECOMMENDATIONS
// ============================================================================

// Store historical data for AI
let schoolHistoricalData = [];

// Render performance table with historical data by year
function renderPerformanceTable(historicalData) {
    schoolHistoricalData = historicalData; // Store for AI

    const tbody = document.querySelector('#schoolPerformanceTable tbody');
    if (!tbody || !historicalData || historicalData.length === 0) return;

    tbody.innerHTML = '';

    // Sort by year descending (newest first)
    const sortedData = [...historicalData].sort((a, b) => parseInt(b.ano) - parseInt(a.ano));

    sortedData.forEach((yearData, index) => {
        const cambio = yearData.cambio_porcentual_global || 0;
        const tendencia = cambio > 0 ?
            '<i class="bx bx-trending-up text-success"></i>' :
            cambio < 0 ?
                '<i class="bx bx-trending-down text-danger"></i>' :
                '<i class="bx bx-minus text-muted"></i>';

        // Calculate change vs previous year
        let vsAnterior = '';
        if (index < sortedData.length - 1) {
            const previousYear = sortedData[index + 1];
            const diff = (yearData.avg_punt_global || 0) - (previousYear.avg_punt_global || 0);
            if (diff > 0) {
                vsAnterior = `<span class="badge bg-success-subtle text-success">
                    <i class="bx bx-up-arrow-alt"></i> +${diff.toFixed(2)}
                </span>`;
            } else if (diff < 0) {
                vsAnterior = `<span class="badge bg-danger-subtle text-danger">
                    <i class="bx bx-down-arrow-alt"></i> ${diff.toFixed(2)}
                </span>`;
            } else {
                vsAnterior = '<span class="badge bg-secondary-subtle text-secondary">Sin cambio</span>';
            }
        } else {
            vsAnterior = '<span class="text-muted">-</span>';
        }

        const row = `
            <tr>
                <td><strong>${yearData.ano}</strong></td>
                <td class="text-end">${(yearData.avg_punt_global || 0).toFixed(2)}</td>
                <td class="text-end">${(yearData.avg_punt_matematicas || 0).toFixed(2)}</td>
                <td class="text-end">${(yearData.avg_punt_lectura_critica || 0).toFixed(2)}</td>
                <td class="text-end">${(yearData.avg_punt_c_naturales || 0).toFixed(2)}</td>
                <td class="text-end">${(yearData.avg_punt_sociales_ciudadanas || 0).toFixed(2)}</td>
                <td class="text-end">${(yearData.avg_punt_ingles || 0).toFixed(2)}</td>
                <td class="text-center"><span class="badge bg-primary-subtle text-primary">#${yearData.ranking_nacional || 'N/A'}</span></td>
                <td class="text-center">${vsAnterior}</td>
                <td class="text-center">${tendencia}</td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

// AI Recommendations button handler
document.addEventListener('DOMContentLoaded', function () {
    document.body.addEventListener('click', function (e) {
        if (e.target && (e.target.id === 'generateAIBtn' || e.target.closest('#generateAIBtn'))) {
            e.preventDefault();
            generateAIRecommendations();
        }
    });
});

// Generate AI recommendations
async function generateAIRecommendations() {
    if (!currentSchoolSk) return;

    const btn = document.getElementById('generateAIBtn');
    const container = document.getElementById('aiRecommendations');

    if (!btn || !container) return;

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Generando...';

    try {
        const response = await fetch(`/icfes/api/colegio/${currentSchoolSk}/ai-recommendations/`);
        const data = await response.json();

        if (response.status === 503) {
            container.innerHTML = `
                <div class="alert alert-warning">
                    <i class="bx bx-info-circle me-2"></i>
                    La API de IA no está configurada. Por favor, configura tu clave API de Anthropic Claude in settings.py
                </div>
            `;
            return;
        }

        if (!response.ok) {
            throw new Error(data.error || 'Error al generar recomendaciones');
        }

        renderAIRecommendations(data);
    } catch (error) {
        console.error('Error generating AI recommendations:', error);
        container.innerHTML = `
            <div class="alert alert-danger">
                <i class="bx bx-error me-2"></i>
                Error: ${error.message || 'Error al generar recomendaciones. Por favor, intenta de nuevo.'}
            </div>
        `;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bx bx-brain"></i> Generar Análisis';
    }
}

// Render AI recommendations
function renderAIRecommendations(data) {
    const container = document.getElementById('aiRecommendations');
    if (!container) return;

    container.innerHTML = `
        <div class="mb-4">
            <h6><i class="bx bx-file-blank me-1"></i> Evaluación General</h6>
            <p>${data.evaluacion_general}</p>
        </div>
        
        <div class="row mb-4">
            <div class="col-md-6">
                <h6 class="text-success"><i class="bx bx-check-circle me-1"></i> Fortalezas</h6>
                <ul>
                    ${data.fortalezas.map(f => `<li>${f}</li>`).join('')}
                </ul>
            </div>
            <div class="col-md-6">
                <h6 class="text-danger"><i class="bx bx-x-circle me-1"></i> Debilidades</h6>
                <ul>
                    ${data.debilidades.map(d => `<li>${d}</li>`).join('')}
                </ul>
            </div>
        </div>
        
        <div class="mb-4">
            <h6><i class="bx bx-bulb me-1"></i> Estrategias para Aumentar 5 Puntos</h6>
            <ol>
                ${data.estrategias_5_puntos.map(e => `<li>${e}</li>`).join('')}
            </ol>
        </div>
        
        <div class="mb-4">
            <h6><i class="bx bx-book-open me-1"></i> Recomendaciones por Materia</h6>
            ${Object.entries(data.recomendaciones_materias).map(([materia, rec]) => `
                <div class="mb-2">
                    <strong>${materia}:</strong> ${rec}
                </div>
            `).join('')}
        </div>
        
        <div class="alert alert-info">
            <h6><i class="bx bx-map me-1"></i> Plan de Acción Prioritario</h6>
            <p class="mb-0">${data.plan_accion}</p>
        </div>
    `;
}
