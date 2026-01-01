
// ============================================================================
// STRATEGIC INSIGHTS FUNCTIONALITY - FIXED VERSION
// ============================================================================

let currentSchoolData = null;
let historicalData = [];

console.log('Strategic Insights JS loaded');

// Update slider value display
document.body.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'improvementSlider') {
        const valueEl = document.getElementById('improvementValue');
        if (valueEl) {
            valueEl.textContent = e.target.value;
        }
    }
});

// Simulate improvement button - FIXED
document.body.addEventListener('click', function (e) {
    // Check if clicked element or its parent is the simulate button
    const target = e.target;
    const isSimulateBtn = target.id === 'simulateBtn' || target.closest('#simulateBtn');

    if (isSimulateBtn) {
        e.preventDefault();
        console.log('Simulate button clicked!');
        simulateImprovement();
    }
});

// Generate achievement badges
function generateAchievementBadges(data) {
    const container = document.getElementById('achievementBadges');
    if (!container) {
        console.warn('Achievement badges container not found');
        return;
    }

    container.innerHTML = '';
    const badges = [];

    // Top percentile badges
    if (data.percentil_nacional >= 90) {
        badges.push({ text: '🏆 Top 10% Nacional', class: 'bg-warning text-dark' });
    } else if (data.percentil_nacional >= 75) {
        badges.push({ text: '⭐ Top 25% Nacional', class: 'bg-info' });
    }

    if (data.percentil_municipal >= 90) {
        badges.push({ text: '🥇 Líder Municipal', class: 'bg-success' });
    }

    // Performance badges
    if (data.brecha_nacional_global >= 20) {
        badges.push({ text: '🚀 Excelencia Nacional', class: 'bg-primary' });
    } else if (data.brecha_nacional_global >= 10) {
        badges.push({ text: '📈 Sobre el Promedio', class: 'bg-info' });
    }

    // Subject-specific badges
    const subjects = ['lectura', 'matematicas', 'c_naturales', 'sociales', 'ingles'];
    const subjectNames = {
        'lectura': 'Lectura',
        'matematicas': 'Matemáticas',
        'c_naturales': 'C. Naturales',
        'sociales': 'Sociales',
        'ingles': 'Inglés'
    };

    subjects.forEach(subject => {
        const brecha = data[`brecha_nacional_${subject}`];
        if (brecha && brecha >= 15) {
            badges.push({
                text: `💡 Fortaleza en ${subjectNames[subject]}`,
                class: 'bg-success'
            });
        }
    });

    // Improvement trend (if historical data available)
    if (historicalData.length >= 2) {
        const recent = historicalData[historicalData.length - 1];
        const previous = historicalData[historicalData.length - 2];
        const improvement = recent.avg_punt_global - previous.avg_punt_global;

        if (improvement >= 5) {
            badges.push({ text: '📊 Mejora Sostenida', class: 'bg-primary' });
        }
    }

    // Render badges
    if (badges.length === 0) {
        container.innerHTML = '<span class="text-muted">Sigue trabajando para desbloquear logros 💪</span>';
    } else {
        badges.forEach(badge => {
            const span = document.createElement('span');
            span.className = `badge ${badge.class} fs-6 px-3 py-2`;
            span.textContent = badge.text;
            container.appendChild(span);
        });
    }

    console.log(`Generated ${badges.length} achievement badges`);
}

// Generate heatmap
function generateHeatmap(historical) {
    if (!historical || historical.length === 0) {
        console.warn('No historical data for heatmap');
        return;
    }

    // Get last 5 years
    const last5Years = historical.slice(-5);

    // Update year headers
    last5Years.forEach((data, idx) => {
        const header = document.getElementById(`heatYear${idx + 1}`);
        if (header) header.textContent = data.ano;
    });

    // Subjects to display
    const subjects = [
        { key: 'matematicas', name: 'Matemáticas' },
        { key: 'lectura_critica', name: 'Lectura Crítica' },
        { key: 'c_naturales', name: 'C. Naturales' },
        { key: 'sociales_ciudadanas', name: 'Sociales' },
        { key: 'ingles', name: 'Inglés' }
    ];

    const tbody = document.getElementById('heatmapBody');
    if (!tbody) {
        console.warn('Heatmap tbody not found');
        return;
    }

    tbody.innerHTML = '';

    subjects.forEach(subject => {
        const row = document.createElement('tr');

        // Subject name
        const nameCell = document.createElement('td');
        nameCell.innerHTML = `<strong>${subject.name}</strong>`;
        row.appendChild(nameCell);

        // Scores for each year
        const scores = [];
        last5Years.forEach(yearData => {
            const score = yearData[`avg_punt_${subject.key}`] || 0;
            scores.push(score);

            const cell = document.createElement('td');
            cell.className = 'text-center';
            cell.textContent = score.toFixed(1);
            cell.style.backgroundColor = getHeatmapColor(score);
            cell.style.color = score < 50 ? '#fff' : '#000';
            cell.style.fontWeight = 'bold';
            row.appendChild(cell);
        });

        // Trend indicator
        const trendCell = document.createElement('td');
        trendCell.className = 'text-center';
        const trend = scores[scores.length - 1] - scores[0];
        if (trend > 2) {
            trendCell.innerHTML = '<i class="bx bx-trending-up text-success fs-4"></i>';
        } else if (trend < -2) {
            trendCell.innerHTML = '<i class="bx bx-trending-down text-danger fs-4"></i>';
        } else {
            trendCell.innerHTML = '<i class="bx bx-minus text-secondary fs-4"></i>';
        }
        row.appendChild(trendCell);

        tbody.appendChild(row);
    });

    console.log(`Generated heatmap for ${subjects.length} subjects`);
}

// Get heatmap color based on score
function getHeatmapColor(score) {
    if (score >= 60) return '#28a745'; // Green
    if (score >= 40) return '#ffc107'; // Yellow
    return '#dc3545'; // Red
}

// Simulate improvement
function simulateImprovement() {
    console.log('simulateImprovement() called', currentSchoolData);

    if (!currentSchoolData) {
        alert('Por favor, selecciona un colegio primero');
        return;
    }

    const subjectEl = document.getElementById('simulatorSubject');
    const sliderEl = document.getElementById('improvementSlider');

    if (!subjectEl || !sliderEl) {
        console.error('Simulator controls not found');
        alert('Error: Controles del simulador no encontrados');
        return;
    }

    const subject = subjectEl.value;
    const improvement = parseInt(sliderEl.value);

    console.log(`Simulating ${improvement} points improvement in ${subject}`);

    // Calculate current global score
    const currentGlobal = currentSchoolData.colegio_global || 250;

    // Estimate new global score (improvement in one subject affects global by ~20%)
    const projectedGlobal = currentGlobal + (improvement * 0.2);

    // Estimate ranking improvement (rough calculation)
    const currentRanking = currentSchoolData.ranking_nacional || 5000;
    const estimatedRankingImprovement = Math.floor(improvement * 50); // ~50 positions per point
    const newRanking = Math.max(1, currentRanking - estimatedRankingImprovement);

    // Estimate new percentile
    const currentPercentil = currentSchoolData.percentil_nacional || 50;
    const newPercentil = Math.min(100, currentPercentil + (improvement * 0.5));

    // Update UI
    const resultDiv = document.getElementById('simulationResult');
    const detailsDiv = document.getElementById('simulationDetails');

    if (resultDiv) resultDiv.style.display = 'none';
    if (detailsDiv) detailsDiv.style.display = 'block';

    // Update values safely
    const updates = {
        'simCurrentScore': currentGlobal.toFixed(2),
        'simProjectedScore': projectedGlobal.toFixed(2),
        'simRankingChange': `↑ ${estimatedRankingImprovement} posiciones (${currentRanking} → ${newRanking})`,
        'simPercentilValue': newPercentil.toFixed(1) + '%'
    };

    Object.keys(updates).forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = updates[id];
        } else {
            console.warn(`Element ${id} not found`);
        }
    });

    const percentilBar = document.getElementById('simPercentilBar');
    if (percentilBar) {
        percentilBar.style.width = newPercentil + '%';
    }

    console.log('Simulation complete!');
}

// Export functions to be called from main school.js
window.updateStrategicInsights = function (schoolData, historical) {
    console.log('updateStrategicInsights() called', schoolData, historical);

    currentSchoolData = schoolData;
    historicalData = historical;

    generateAchievementBadges(schoolData);
    generateHeatmap(historical);
};

console.log('Strategic Insights functions exported to window');
