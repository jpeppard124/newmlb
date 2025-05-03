// charts.js - Chart configurations for the MLB Betting Engine

/**
 * Create a performance chart showing ROI trends
 * @param {string} elementId - Canvas element ID
 * @param {Array} dates - Array of date strings
 * @param {Array} dailyRoi - Array of daily ROI values
 * @param {Array} cumulativeRoi - Array of cumulative ROI values
 * @param {number} days - Number of days in the data
 */
function createRoiChart(elementId, dates, dailyRoi, cumulativeRoi, days) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    // Create gradient for the cumulative ROI area
    const gradientFill = ctx.createLinearGradient(0, 0, 0, 400);
    gradientFill.addColorStop(0, 'rgba(54, 162, 235, 0.3)');
    gradientFill.addColorStop(1, 'rgba(54, 162, 235, 0.0)');
    
    const roiChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Daily ROI',
                    data: dailyRoi,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderWidth: 2,
                    pointRadius: 3,
                    tension: 0.4
                },
                {
                    label: 'Cumulative ROI',
                    data: cumulativeRoi,
                    borderColor: 'rgba(54, 162, 235, 1)',
                    backgroundColor: gradientFill,
                    borderWidth: 3,
                    pointRadius: 2,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: `ROI Performance (Last ${days} Days)`,
                    color: '#ffffff',
                    font: {
                        size: 16
                    }
                },
                legend: {
                    labels: {
                        color: '#ffffff'
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += context.parsed.y.toFixed(2) + '%';
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: {
                        color: '#cccccc',
                        callback: function(value) {
                            return value + '%';
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                x: {
                    ticks: {
                        color: '#cccccc'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            }
        }
    });
    
    return roiChart;
}

/**
 * Create a profit chart showing daily and cumulative profit
 * @param {string} elementId - Canvas element ID
 * @param {Array} dates - Array of date strings
 * @param {Array} dailyProfit - Array of daily profit values
 * @param {Array} cumulativeProfit - Array of cumulative profit values
 * @param {number} days - Number of days in the data
 */
function createProfitChart(elementId, dates, dailyProfit, cumulativeProfit, days) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    const profitChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Daily Profit (Units)',
                    data: dailyProfit,
                    backgroundColor: function(context) {
                        const value = context.dataset.data[context.dataIndex];
                        return value >= 0 ? 'rgba(40, 167, 69, 0.7)' : 'rgba(220, 53, 69, 0.7)';
                    },
                    borderColor: function(context) {
                        const value = context.dataset.data[context.dataIndex];
                        return value >= 0 ? 'rgba(40, 167, 69, 1)' : 'rgba(220, 53, 69, 1)';
                    },
                    borderWidth: 1
                },
                {
                    label: 'Cumulative Profit (Units)',
                    data: cumulativeProfit,
                    type: 'line',
                    borderColor: 'rgba(255, 193, 7, 1)',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 3,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: `Profit Tracking (Last ${days} Days)`,
                    color: '#ffffff',
                    font: {
                        size: 16
                    }
                },
                legend: {
                    labels: {
                        color: '#ffffff'
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += context.parsed.y.toFixed(2);
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: {
                        color: '#cccccc'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    title: {
                        display: true,
                        text: 'Daily Profit',
                        color: '#cccccc'
                    }
                },
                y1: {
                    position: 'right',
                    ticks: {
                        color: '#cccccc'
                    },
                    grid: {
                        drawOnChartArea: false
                    },
                    title: {
                        display: true,
                        text: 'Cumulative Profit',
                        color: '#cccccc'
                    }
                },
                x: {
                    ticks: {
                        color: '#cccccc'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            }
        }
    });
    
    return profitChart;
}

/**
 * Create a pie chart showing bet distribution
 * @param {string} elementId - Canvas element ID
 * @param {Array} labels - Array of bet type labels
 * @param {Array} data - Array of bet counts
 */
function createBetDistributionChart(elementId, labels, data) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    const betDistributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(54, 162, 235, 0.7)',
                    'rgba(255, 206, 86, 0.7)',
                    'rgba(255, 99, 132, 0.7)'
                ],
                borderColor: [
                    'rgba(75, 192, 192, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(255, 99, 132, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Bet Type Distribution',
                    color: '#ffffff',
                    font: {
                        size: 16
                    }
                },
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#ffffff'
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw;
                            const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((value / total) * 100);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            },
            cutout: '50%'
        }
    });
    
    return betDistributionChart;
}

/**
 * Create a win rate comparison chart
 * @param {string} elementId - Canvas element ID
 * @param {Array} betTypes - Array of bet type labels
 * @param {Array} winRates - Array of win rate percentages
 */
function createWinRateChart(elementId, betTypes, winRates) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    const winRateChart = new Chart(ctx, {
        type: 'horizontalBar',
        data: {
            labels: betTypes,
            datasets: [{
                label: 'Win Rate',
                data: winRates,
                backgroundColor: 'rgba(40, 167, 69, 0.7)',
                borderColor: 'rgba(40, 167, 69, 1)',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Win Rate by Bet Type',
                    color: '#ffffff',
                    font: {
                        size: 16
                    }
                },
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Win Rate: ${context.raw.toFixed(1)}%`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        color: '#cccccc',
                        callback: function(value) {
                            return value + '%';
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    min: 0,
                    max: 100
                },
                y: {
                    ticks: {
                        color: '#cccccc'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            }
        }
    });
    
    return winRateChart;
}

/**
 * Create a confidence correlation chart
 * Shows how prediction confidence correlates with accuracy
 * @param {string} elementId - Canvas element ID
 * @param {Array} confidenceLevels - Array of confidence level labels
 * @param {Array} accuracyRates - Array of accuracy percentages
 */
function createConfidenceCorrelationChart(elementId, confidenceLevels, accuracyRates) {
    const ctx = document.getElementById(elementId).getContext('2d');
    
    const confidenceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: confidenceLevels,
            datasets: [{
                label: 'Prediction Accuracy',
                data: accuracyRates,
                borderColor: 'rgba(54, 162, 235, 1)',
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Confidence vs. Accuracy',
                    color: '#ffffff',
                    font: {
                        size: 16
                    }
                },
                legend: {
                    labels: {
                        color: '#ffffff'
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Accuracy: ${context.raw.toFixed(1)}%`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: {
                        color: '#cccccc',
                        callback: function(value) {
                            return value + '%';
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    title: {
                        display: true,
                        text: 'Accuracy',
                        color: '#cccccc'
                    },
                    min: 0,
                    max: 100
                },
                x: {
                    ticks: {
                        color: '#cccccc'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    },
                    title: {
                        display: true,
                        text: 'Confidence Level',
                        color: '#cccccc'
                    }
                }
            }
        }
    });
    
    return confidenceChart;
}

/**
 * Helper function to format dates for chart display
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date string (MM/DD)
 */
function formatChartDate(dateString) {
    const date = new Date(dateString);
    return `${date.getMonth() + 1}/${date.getDate()}`;
}

/**
 * Helper function to create an array of dates for the last N days
 * @param {number} days - Number of days
 * @returns {Array} Array of date strings
 */
function getLastNDays(days) {
    const dates = [];
    const today = new Date();
    
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(today.getDate() - i);
        dates.push(formatChartDate(date));
    }
    
    return dates;
}
