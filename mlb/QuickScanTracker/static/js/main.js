// main.js - Main JavaScript for MLB Betting Engine

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Handle API action buttons
    setupAPIButtons();
    
    // Set up refresh timers for data that needs to be periodically updated
    setupRefreshTimers();
});

/**
 * Set up click handlers for API action buttons
 */
function setupAPIButtons() {
    // Update Odds button
    const updateOddsBtn = document.getElementById('update-odds-btn');
    if (updateOddsBtn) {
        updateOddsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            updateOdds();
        });
    }
    
    // Update Weather button
    const updateWeatherBtn = document.getElementById('update-weather-btn');
    if (updateWeatherBtn) {
        updateWeatherBtn.addEventListener('click', function(e) {
            e.preventDefault();
            updateWeather();
        });
    }
    
    // Generate Predictions button
    const generatePredictionsBtn = document.getElementById('generate-predictions-btn');
    if (generatePredictionsBtn) {
        generatePredictionsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            generatePredictions();
        });
    }
}

/**
 * Set up refresh timers for data that needs to be periodically updated
 */
function setupRefreshTimers() {
    // Example: Refresh the page every 15 minutes on the predictions page
    if (window.location.pathname.includes('/predictions')) {
        setTimeout(function() {
            window.location.reload();
        }, 15 * 60 * 1000); // 15 minutes
    }
}

/**
 * Update betting odds via API
 */
function updateOdds() {
    const btn = document.getElementById('update-odds-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Updating...';
    }
    
    fetch('/api/update_odds', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showAlert('Odds updated successfully', 'success');
        } else {
            showAlert('Error: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Error updating odds', 'danger');
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync-alt"></i> Update Odds';
        }
    });
}

/**
 * Update weather forecasts via API
 */
function updateWeather() {
    const btn = document.getElementById('update-weather-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Updating...';
    }
    
    fetch('/api/update_weather', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showAlert('Weather forecasts updated successfully', 'success');
        } else {
            showAlert('Error: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Error updating weather forecasts', 'danger');
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-cloud-sun"></i> Update Weather';
        }
    });
}

/**
 * Generate predictions for upcoming games via API
 */
function generatePredictions() {
    const btn = document.getElementById('generate-predictions-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...';
    }
    
    fetch('/api/generate_predictions', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showAlert(`${data.message}`, 'success');
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showAlert('Error: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('Error generating predictions', 'danger');
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-brain"></i> Generate Predictions';
        }
    });
}

/**
 * Display an alert message
 * @param {string} message - The message to display
 * @param {string} type - The alert type (success, danger, warning, info)
 */
function showAlert(message, type) {
    // Create alert container if it doesn't exist
    let alertContainer = document.getElementById('alert-container');
    if (!alertContainer) {
        alertContainer = document.createElement('div');
        alertContainer.id = 'alert-container';
        alertContainer.style.position = 'fixed';
        alertContainer.style.top = '20px';
        alertContainer.style.right = '20px';
        alertContainer.style.zIndex = '9999';
        document.body.appendChild(alertContainer);
    }
    
    // Create the alert element
    const alertEl = document.createElement('div');
    alertEl.className = `alert alert-${type} alert-dismissible fade show`;
    alertEl.role = 'alert';
    
    // Add alert content
    alertEl.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Add to container
    alertContainer.appendChild(alertEl);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alertEl);
        bsAlert.close();
    }, 5000);
}
