// static/app.js

let pollingInterval;

async function runSimulation() {
    const constellation = document.getElementById('constellation').value;
    const btn = document.getElementById('runBtn');
    const statusLabel = document.getElementById('status');
    
    // 1. Lock the button so users don't spam it
    btn.disabled = true;
    statusLabel.innerText = "Starting engine...";
    statusLabel.style.color = "orange";
    
    // 2. Tell the server to start the background job
    await fetch(`/api/run?constellation=${constellation}`);
    
    // 3. Start polling the server every 2 seconds to check the status
    pollingInterval = setInterval(checkStatus, 2000);
}

async function checkStatus() {
    const response = await fetch('/api/status');
    const result = await response.json();
    
    const statusLabel = document.getElementById('status');
    const btn = document.getElementById('runBtn');
    
    // Update the text on the screen
    statusLabel.innerText = result.message;
    
    // If Python finishes the math...
    if (result.status === "success") {
        clearInterval(pollingInterval);
        statusLabel.style.color = "green";
        btn.disabled = false;
        
        // Ask Python to reset its state for the next run
        result.status = "idle";
        
        loadChartData(); // Refresh the chart with the new CSV data!
    } 
    // If Python crashes...
    else if (result.status === "error") {
        clearInterval(pollingInterval);
        statusLabel.style.color = "red";
        btn.disabled = false;
    }
}

async function loadChartData() {
    const response = await fetch('/api/data');
    const result = await response.json();
    
    if(result.timeline) {
        const data = result.timeline;
        
        const times = data.map(row => row.time_utc);
        const availability = data.map(row => row.availability_pct);
        
        const trace = {
            x: times,
            y: availability,
            type: 'scatter',
            mode: 'lines+markers',
            line: {color: '#e67e22', width: 3, shape: 'hv'},
            marker: {size: 6, color: '#d35400'},
            name: 'Service Availability (%)'
        };
        
        const layout = {
            title: '5G Service Availability Over TUL Campus (60 Minutes)',
            xaxis: { title: 'Time (UTC)', tickangle: -45 },
            yaxis: { title: 'Coverage Availability (%)', range: [-5, 105] },
            margin: { b: 100 }
        };
        
        Plotly.newPlot('chart', [trace], layout);
    }
}

// Load initial data on page load
loadChartData();