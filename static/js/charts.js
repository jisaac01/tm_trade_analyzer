/**
 * Monte Carlo Trade Sizing - Interactive Chart Visualizations
 * 
 * Creates three interactive charts:
 * 1. Comparison Graph: All thresholds (median only) for quick comparison
 * 2. Threshold Detail Graph: Full percentile bands for selected threshold
 * 3. Historical Replay Graph: Actual balance trajectory from replay
 */

// Global state
let selectedThreshold = null;
let comparisonChart = null;
let detailChart = null;
let replayChart = null;

// Color palette for thresholds
const COLORS = [
    '#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa',
    '#fb923c', '#2dd4bf', '#f472b6', '#38bdf8', '#4ade80'
];

/**
 * Initialize all charts when page loads
 */
function initializeCharts() {
    if (typeof chart_data === 'undefined' || !chart_data) {
        console.log('No chart data available');
        return;
    }
    
    const { monte_carlo, replay, trade_numbers } = chart_data;
    
    // Create comparison chart (all thresholds, median only)
    if (monte_carlo && Object.keys(monte_carlo).length > 0) {
        createComparisonChart(monte_carlo, trade_numbers);
        
        // Auto-select first threshold for detail view
        const firstThreshold = Object.keys(monte_carlo)[0];
        selectThreshold(firstThreshold);
    }
    
    // Create replay chart
    if (replay && Object.keys(replay).length > 0) {
        createReplayChart(replay, trade_numbers);
    }
}

/**
 * Create comparison chart showing all thresholds (median only)
 */
function createComparisonChart(monteCarloData, tradeNumbers) {
    const ctx = document.getElementById('comparisonChart');
    if (!ctx) return;
    
    const datasets = [];
    const thresholds = Object.keys(monteCarloData);
    
    thresholds.forEach((threshold, index) => {
        const data = monteCarloData[threshold];
        if (!data || !data.p50) return;
        
        datasets.push({
            label: threshold,
            data: data.p50,
            borderColor: COLORS[index % COLORS.length],
            backgroundColor: COLORS[index % COLORS.length] + '40',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 5,
            tension: 0.1,
            threshold: threshold  // Store threshold for click handling
        });
    });
    
    comparisonChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tradeNumbers,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Monte Carlo Comparison - Median Trajectories',
                    color: '#60a5fa',
                    font: { size: 16, weight: 'bold' }
                },
                legend: {
                    display: true,
                    labels: {
                        color: '#e5e7eb',
                        usePointStyle: true,
                        padding: 12
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.95)',
                    titleColor: '#60a5fa',
                    bodyColor: '#e5e7eb',
                    borderColor: '#374151',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            const value = context.parsed.y;
                            return context.dataset.label + ': $' + value.toLocaleString('en-US', {
                                minimumFractionDigits: 0,
                                maximumFractionDigits: 0
                            });
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Trade Number',
                        color: '#9ca3af'
                    },
                    ticks: { color: '#9ca3af' },
                    grid: { color: '#1f2937' }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Account Balance ($)',
                        color: '#9ca3af'
                    },
                    ticks: { 
                        color: '#9ca3af',
                        callback: function(value) {
                            return '$' + value.toLocaleString('en-US', { maximumFractionDigits: 0 });
                        }
                    },
                    grid: { color: '#1f2937' }
                }
            },
            onClick: function(event, elements) {
                if (elements.length > 0) {
                    const datasetIndex = elements[0].datasetIndex;
                    const threshold = datasets[datasetIndex].threshold;
                    selectThreshold(threshold);
                }
            }
        }
    });
}

/**
 * Create detail chart showing percentile bands for selected threshold
 */
function createDetailChart(thresholdData, tradeNumbers, thresholdLabel) {
    const ctx = document.getElementById('detailChart');
    if (!ctx) return;
    
    // Destroy existing chart
    if (detailChart) {
        detailChart.destroy();
    }
    
    const datasets = [
        // P5-P95 band (lightest)
        {
            label: '5th-95th Percentile',
            data: thresholdData.p95,
            borderColor: '#60a5fa40',
            backgroundColor: '#60a5fa20',
            borderWidth: 1,
            pointRadius: 0,
            fill: '+1',  // Fill to next dataset
            tension: 0.1,
            order: 5
        },
        {
            label: 'P5',
            data: thresholdData.p5,
            borderColor: '#60a5fa40',
            backgroundColor: '#60a5fa20',
            borderWidth: 1,
            pointRadius: 0,
            fill: false,
            tension: 0.1,
            order: 4
        },
        // P25-P75 band (darker)
        {
            label: '25th-75th Percentile',
            data: thresholdData.p75,
            borderColor: '#60a5fa60',
            backgroundColor: '#60a5fa40',
            borderWidth: 1,
            pointRadius: 0,
            fill: '+1',  // Fill to next dataset
            tension: 0.1,
            order: 3
        },
        {
            label: 'P25',
            data: thresholdData.p25,
            borderColor: '#60a5fa60',
            backgroundColor: '#60a5fa40',
            borderWidth: 1,
            pointRadius: 0,
            fill: false,
            tension: 0.1,
            order: 2
        },
        // P50 (median) - solid line on top
        {
            label: 'Median (P50)',
            data: thresholdData.p50,
            borderColor: '#60a5fa',
            backgroundColor: '#60a5fa',
            borderWidth: 3,
            pointRadius: 0,
            pointHoverRadius: 5,
            fill: false,
            tension: 0.1,
            order: 1
        }
    ];
    
    detailChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tradeNumbers,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                title: {
                    display: true,
                    text: `Threshold Detail - ${thresholdLabel} - Risk Distribution`,
                    color: '#60a5fa',
                    font: { size: 16, weight: 'bold' }
                },
                legend: {
                    display: true,
                    labels: {
                        color: '#e5e7eb',
                        usePointStyle: true,
                        padding: 12,
                        filter: function(item) {
                            // Only show meaningful labels
                            return !item.text.includes('P5') && !item.text.includes('P25');
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.95)',
                    titleColor: '#60a5fa',
                    bodyColor: '#e5e7eb',
                    borderColor: '#374151',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            const value = context.parsed.y;
                            return context.dataset.label + ': $' + value.toLocaleString('en-US', {
                                minimumFractionDigits: 0,
                                maximumFractionDigits: 0
                            });
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Trade Number',
                        color: '#9ca3af'
                    },
                    ticks: { color: '#9ca3af' },
                    grid: { color: '#1f2937' }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Account Balance ($)',
                        color: '#9ca3af'
                    },
                    ticks: { 
                        color: '#9ca3af',
                        callback: function(value) {
                            return '$' + value.toLocaleString('en-US', { maximumFractionDigits: 0 });
                        }
                    },
                    grid: { color: '#1f2937' }
                }
            }
        }
    });
}

/**
 * Create replay chart showing actual historical trajectories
 */
function createReplayChart(replayData, tradeNumbers) {
    const ctx = document.getElementById('replayChart');
    if (!ctx) return;
    
    const datasets = [];
    const scenarios = Object.keys(replayData);
    
    scenarios.forEach((scenarioId, index) => {
        const trajectory = replayData[scenarioId];
        if (!trajectory || trajectory.length === 0) return;
        
        datasets.push({
            label: scenarioId.replace('scenario_', 'Scenario '),
            data: trajectory,
            borderColor: '#34d399',
            backgroundColor: '#34d39940',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 5,
            tension: 0.1
        });
    });
    
    replayChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: tradeNumbers.slice(0, Math.max(...datasets.map(d => d.data.length))),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Historical Replay - Actual Performance',
                    color: '#60a5fa',
                    font: { size: 16, weight: 'bold' }
                },
                legend: {
                    display: scenarios.length > 1,
                    labels: {
                        color: '#e5e7eb',
                        usePointStyle: true,
                        padding: 12
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.95)',
                    titleColor: '#60a5fa',
                    bodyColor: '#e5e7eb',
                    borderColor: '#374151',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        title: function(context) {
                            return 'Trade ' + context[0].label;
                        },
                        label: function(context) {
                            const value = context.parsed.y;
                            return context.dataset.label + ': $' + value.toLocaleString('en-US', {
                                minimumFractionDigits: 0,
                                maximumFractionDigits: 0
                            });
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Trade Number',
                        color: '#9ca3af'
                    },
                    ticks: { color: '#9ca3af' },
                    grid: { color: '#1f2937' }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Account Balance ($)',
                        color: '#9ca3af'
                    },
                    ticks: { 
                        color: '#9ca3af',
                        callback: function(value) {
                            return '$' + value.toLocaleString('en-US', { maximumFractionDigits: 0 });
                        }
                    },
                    grid: { color: '#1f2937' }
                }
            }
        }
    });
}

/**
 * Select a threshold and update the detail chart
 */
function selectThreshold(threshold) {
    selectedThreshold = threshold;
    
    // Highlight selected threshold in comparison chart
    if (comparisonChart) {
        comparisonChart.data.datasets.forEach((dataset, index) => {
            if (dataset.threshold === threshold) {
                dataset.borderWidth = 4;
                dataset.borderColor = dataset.borderColor.replace('40', '');
            } else {
                dataset.borderWidth = 2;
                const baseColor = COLORS[index % COLORS.length];
                dataset.borderColor = baseColor;
            }
        });
        comparisonChart.update('none');  // Update without animation
    }
    
    // Update detail chart with selected threshold
    const thresholdData = chart_data.monte_carlo[threshold];
    if (thresholdData) {
        createDetailChart(thresholdData, chart_data.trade_numbers, threshold);
    }
}

// Initialize charts when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCharts);
} else {
    initializeCharts();
}
