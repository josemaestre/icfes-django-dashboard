
// New function to update comparison context section
function updateComparisonContext(data) {
    // Update Brechas (Gaps)
    updateBrechaDisplay('brechaMunicipal', 'brechaMunicipalBar', data.brecha_municipal_global);
    updateBrechaDisplay('brechaDepartamental', 'brechaDepartamentalBar', data.brecha_departamental_global);
    updateBrechaDisplay('brechaNacional', 'brechaNacionalBar', data.brecha_nacional_global);

    // Update Percentiles
    updatePercentilDisplay('percentilMunicipal', 'percentilMunicipalBar', data.percentil_municipal);
    updatePercentilDisplay('percentilDepartamental', 'percentilDepartamentalBar', data.percentil_departamental);
    updatePercentilDisplay('percentilNacional', 'percentilNacionalBar', data.percentil_nacional);

    // Update Classifications
    updateClasificacionDisplay('clasificacionMunicipal', data.clasificacion_vs_municipal);
    updateClasificacionDisplay('clasificacionDepartamental', data.clasificacion_vs_departamental);
    updateClasificacionDisplay('clasificacionNacional', data.clasificacion_vs_nacional);
}

// Helper function to update brecha display
function updateBrechaDisplay(badgeId, barId, value) {
    const badge = document.getElementById(badgeId);
    const bar = document.getElementById(barId);

    if (!badge || !bar) return;

    const formattedValue = value >= 0 ? `+${value.toFixed(2)}` : value.toFixed(2);
    badge.textContent = formattedValue;

    // Color based on value
    if (value >= 10) {
        badge.className = 'badge bg-success';
        bar.className = 'progress-bar bg-success';
    } else if (value >= 0) {
        badge.className = 'badge bg-info';
        bar.className = 'progress-bar bg-info';
    } else if (value >= -10) {
        badge.className = 'badge bg-warning';
        bar.className = 'progress-bar bg-warning';
    } else {
        badge.className = 'badge bg-danger';
        bar.className = 'progress-bar bg-danger';
    }

    // Bar width (scale from -30 to +30 to 0-100%)
    const percentage = Math.min(100, Math.max(0, ((value + 30) / 60) * 100));
    bar.style.width = percentage + '%';
}

// Helper function to update percentil display
function updatePercentilDisplay(spanId, barId, value) {
    const span = document.getElementById(spanId);
    const bar = document.getElementById(barId);

    if (!span || !bar) return;

    const percentile = Math.round(value);
    span.textContent = percentile + '%';
    bar.style.width = percentile + '%';

    // Color based on percentile
    if (percentile >= 75) {
        bar.className = 'progress-bar bg-success';
    } else if (percentile >= 50) {
        bar.className = 'progress-bar bg-info';
    } else if (percentile >= 25) {
        bar.className = 'progress-bar bg-warning';
    } else {
        bar.className = 'progress-bar bg-danger';
    }
}

// Helper function to update clasificacion display
function updateClasificacionDisplay(divId, value) {
    const div = document.getElementById(divId);

    if (!div) return;

    div.textContent = value;

    // Color based on classification
    if (value.includes('Muy Superior')) {
        div.className = 'alert alert-success mb-0 py-2';
    } else if (value.includes('Superior')) {
        div.className = 'alert alert-info mb-0 py-2';
    } else if (value.includes('Similar')) {
        div.className = 'alert alert-secondary mb-0 py-2';
    } else if (value.includes('Inferior')) {
        div.className = 'alert alert-warning mb-0 py-2';
    } else if (value.includes('Muy Inferior')) {
        div.className = 'alert alert-danger mb-0 py-2';
    }
}
