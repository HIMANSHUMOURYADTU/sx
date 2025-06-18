document.addEventListener('DOMContentLoaded', () => {
    // --- CONFIG & DOM ELEMENTS ---
    const API_URL = "http://127.0.0.1:8000"; // IMPORTANT: Change if your backend is elsewhere

    // Views
    const uploadSection = document.getElementById('upload-section');
    const dashboardSection = document.getElementById('dashboard-section');

    // Upload Form
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');
    const dateFormatInput = document.getElementById('date-format-input');
    const uploadButton = document.getElementById('upload-button');
    const uploadButtonText = uploadButton.querySelector('.button-text');
    const uploadButtonSpinner = uploadButton.querySelector('.spinner');
    const fileDropZone = document.getElementById('file-drop-zone');
    const fileDropZoneContent = document.getElementById('file-drop-zone-content');
    const fileNameDisplay = document.getElementById('file-name-display');

    // Dashboard
    const resetButton = document.getElementById('reset-button');
    const fileNameHeader = document.getElementById('file-name-header');
    const columnList = document.getElementById('column-list');
    const suggestionsList = document.getElementById('suggestions-list');
    const chartPlaceholder = document.getElementById('chart-placeholder');
    const chartLoader = document.getElementById('chart-loader');
    const chartDisplay = document.getElementById('chart-display');

    // Toast
    const toast = document.getElementById('toast');

    let currentFile = null;

    // --- ICONS ---
    const ICONS = {
        numeric: '<i data-lucide="hash" style="color: #60a5fa;"></i>',
        categorical: '<i data-lucide="bar-chart-3" style="color: #c084fc;"></i>',
        datetime: '<i data-lucide="calendar" style="color: #4ade80;"></i>',
        line: '<i data-lucide="line-chart"></i>',
        bar: '<i data-lucide="bar-chart"></i>',
        scatter: '<i data-lucide="scatter-chart"></i>',
        histogram: '<i data-lucide="area-chart"></i>',
        box: '<i data-lucide="box"></i>',
        pie: '<i data-lucide="pie-chart"></i>',
        heatmap: '<i data-lucide="table-properties"></i>',
    };

    // --- EVENT LISTENERS ---

    uploadForm.addEventListener('submit', handleUpload);
    resetButton.addEventListener('click', handleReset);
    fileInput.addEventListener('change', handleFileSelect);

    // Drag and Drop listeners
    fileDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileDropZone.classList.add('dragover');
    });
    fileDropZone.addEventListener('dragleave', () => {
        fileDropZone.classList.remove('dragover');
    });
    fileDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        fileDropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelect();
        }
    });


    // --- CORE FUNCTIONS ---

    function handleFileSelect() {
        if (fileInput.files.length > 0) {
            currentFile = fileInput.files[0];
            fileNameDisplay.textContent = currentFile.name;
            fileDropZoneContent.classList.add('hidden');
            fileNameDisplay.classList.remove('hidden');
        }
    }

    async function handleUpload(e) {
        e.preventDefault();
        if (!currentFile) {
            showToast("Please select a file first.", "error");
            return;
        }

        setLoadingState(true);

        const formData = new FormData();
        formData.append('file', currentFile);
        formData.append('date_format', dateFormatInput.value.trim());

        try {
            const response = await fetch(`${API_URL}/upload`, {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "An unknown error occurred.");
            }
            
            showToast(`Successfully analyzed ${data.filename}`, 'success');
            setupDashboard(data.filename, data.columns);
            fetchAndRenderSuggestions();

        } catch (error) {
            showToast(error.message, 'error');
            setLoadingState(false);
        }
    }

    function setupDashboard(filename, columns) {
        // Switch views
        uploadSection.classList.add('hidden');
        dashboardSection.classList.remove('hidden');
        resetButton.classList.remove('hidden');
        
        // Populate data
        fileNameHeader.textContent = filename;
        renderColumnAnalysis(columns);
        
        setLoadingState(false);
    }
    
    function renderColumnAnalysis(columns) {
        columnList.innerHTML = ''; // Clear previous
        for (const [name, info] of Object.entries(columns)) {
            const item = document.createElement('div');
            item.className = 'column-item';
            item.innerHTML = `
                <div class="column-item-header">
                    <span class="name">${ICONS[info.type]} ${name}</span>
                    <span class="badge ${info.cardinality}">${info.cardinality}</span>
                </div>
                <div class="column-item-details">
                    <span>${info.unique_count} unique</span>
                    <span>${info.missing_percentage}% missing</span>
                </div>
            `;
            columnList.appendChild(item);
        }
        lucide.createIcons(); // Re-render icons
    }

    async function fetchAndRenderSuggestions() {
        suggestionsList.innerHTML = '';
        try {
            const response = await fetch(`${API_URL}/suggest`);
            const suggestions = await response.json();

            if (suggestions.length === 0) {
                suggestionsList.innerHTML = '<p class="form-hint">No suggestions could be generated.</p>';
                return;
            }

            suggestions.forEach(config => {
                const item = document.createElement('div');
                item.className = 'suggestion-item';
                item.innerHTML = `${ICONS[config.chart_type] || ICONS.bar} <span>${config.title}</span>`;
                item.addEventListener('click', () => {
                    // Highlight active item
                    document.querySelectorAll('.suggestion-item.active').forEach(el => el.classList.remove('active'));
                    item.classList.add('active');
                    handleGenerateChart(config);
                });
                suggestionsList.appendChild(item);
            });
            lucide.createIcons();
        } catch (error) {
            showToast("Could not fetch suggestions.", "error");
        }
    }

    async function handleGenerateChart(config) {
        chartPlaceholder.classList.add('hidden');
        chartDisplay.innerHTML = ''; // Clear previous chart
        chartLoader.classList.remove('hidden');

        try {
            const response = await fetch(`${API_URL}/generate-chart`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const chartJsonString = await response.json();
             if (!response.ok) {
                throw new Error(chartJsonString.detail || "Chart generation failed.");
            }

            const chartData = JSON.parse(chartJsonString);

            Plotly.newPlot(chartDisplay, chartData.data, chartData.layout, { responsive: true });

        } catch (error) {
            showToast(error.message, "error");
            chartPlaceholder.classList.remove('hidden');
        } finally {
            chartLoader.classList.add('hidden');
        }
    }

    function handleReset() {
        // Reset state
        currentFile = null;
        
        // Reset UI
        uploadSection.classList.remove('hidden');
        dashboardSection.classList.add('hidden');
        resetButton.classList.add('hidden');

        uploadForm.reset();
        fileDropZoneContent.classList.remove('hidden');
        fileNameDisplay.classList.add('hidden');
        fileNameDisplay.textContent = '';
        
        columnList.innerHTML = '';
        suggestionsList.innerHTML = '';
        chartDisplay.innerHTML = '';
        chartPlaceholder.classList.remove('hidden');
    }

    // --- UTILITY FUNCTIONS ---

    function setLoadingState(isLoading) {
        uploadButton.disabled = isLoading;
        if (isLoading) {
            uploadButtonText.classList.add('hidden');
            uploadButtonSpinner.classList.remove('hidden');
        } else {
            uploadButtonText.classList.remove('hidden');
            uploadButtonSpinner.classList.add('hidden');
        }
    }

    function showToast(message, type = "info") {
        toast.textContent = message;
        toast.className = `show ${type}`; // 'success' or 'error'
        setTimeout(() => {
            toast.className = toast.className.replace("show", "");
        }, 3000);
    }

    // Initial call to render icons like the upload cloud
    lucide.createIcons();
});