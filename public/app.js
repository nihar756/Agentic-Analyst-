// App State
let state = {
    datasets: [],
    conversations: [],
    activeDatasetId: null,
    activeConversationId: null,
    loading: false
};

// DOM Elements
const datasetList = document.getElementById('dataset-list');
const conversationList = document.getElementById('conversation-list');
const csvUploadInput = document.getElementById('csv-upload');
const messagesLog = document.getElementById('messages-log');
const welcomeScreen = document.getElementById('welcome-screen');
const activeDatasetDisplay = document.getElementById('active-dataset-display');
const activeDatasetName = document.getElementById('active-dataset-name');
const activeConversationTitle = document.getElementById('active-conversation-title');
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const agentPipeline = document.getElementById('agent-pipeline');
const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
const sidebar = document.querySelector('.sidebar');
const datasetDropzone = document.getElementById('dataset-dropzone');
const convCsvUploadInput = document.getElementById('conv-csv-upload');
const existingDatasetSelect = document.getElementById('existing-dataset-select');
const linkExistingBtn = document.getElementById('link-existing-btn');

// Modal Elements
const imageModal = document.getElementById('image-modal');
const modalImg = document.getElementById('modal-img');
const modalCaption = document.getElementById('modal-caption');
const closeModal = document.querySelector('.close-modal');

// API URL (same host)
const API_BASE = '';

// Auth Checks & Session Handling
async function checkAuthAndPopulate() {
    try {
        const response = await fetch('/api/auth/status');
        const data = await response.json();
        
        if (!data.authenticated) {
            // Redirect to landing page
            window.location.href = '/';
            return false;
        }
        
        // Populate user details in workspace sidebar
        const user = data.user;
        const initials = user.name ? user.name.charAt(0).toUpperCase() : 'U';
        
        const avatarEl = document.getElementById('user-avatar-initials');
        const nameEl = document.getElementById('user-display-name');
        const emailEl = document.getElementById('user-display-email');
        const logoutEl = document.getElementById('logout-btn');
        
        if (avatarEl) avatarEl.innerText = initials;
        if (nameEl) nameEl.innerText = user.name || 'Analyst';
        if (emailEl) emailEl.innerText = user.email || '';
        
        if (logoutEl) {
            logoutEl.addEventListener('click', handleLogout);
        }
        
        return true;
    } catch (err) {
        console.error("Auth check error:", err);
        window.location.href = '/';
        return false;
    }
}

async function handleLogout() {
    try {
        const response = await fetch('/api/auth/logout', { method: 'POST' });
        if (response.ok) {
            window.location.href = '/';
        } else {
            alert('Logout failed. Please try again.');
        }
    } catch (err) {
        console.error('Logout error:', err);
        window.location.href = '/';
    }
}

// On Init
document.addEventListener('DOMContentLoaded', async () => {
    const authenticated = await checkAuthAndPopulate();
    if (authenticated) {
        loadDatasets();
        loadConversations();
        setupEventListeners();
    }
});

// Event Listeners
function setupEventListeners() {
    // Upload CSV
    csvUploadInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            uploadCSV(file);
        }
    });

    // Send query on button click
    sendBtn.addEventListener('click', () => {
        submitQuery();
    });

    // Send query on Enter key
    queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitQuery();
        }
    });

    // Start a new chat (blank by default)
    newChatBtn.addEventListener('click', () => {
        startNewChat(null);
    });

    // Toggle Left Sidebar
    toggleSidebarBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    // Upload CSV directly under active conversation
    convCsvUploadInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file && state.activeConversationId) {
            uploadCSVForConversation(state.activeConversationId, file);
        }
    });

    // Link existing dataset to active conversation
    linkExistingBtn.addEventListener('click', () => {
        const datasetId = existingDatasetSelect.value;
        if (datasetId && state.activeConversationId) {
            linkDatasetToConversation(state.activeConversationId, datasetId);
        } else {
            alert('Please select a dataset to link.');
        }
    });

    // Download mutated dataset
    const downloadDatasetBtn = document.getElementById('download-dataset-btn');
    if (downloadDatasetBtn) {
        downloadDatasetBtn.addEventListener('click', () => {
            if (!state.activeConversationId) return;
            window.open(`${API_BASE}/api/conversations/${state.activeConversationId}/download`, '_blank');
        });
    }

    // Dynamic height for textarea
    queryInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight - 4) + 'px';
    });

    // Welcome screen quick queries
    document.querySelectorAll('.quick-tips li').forEach(item => {
        item.addEventListener('click', () => {
            const query = item.innerText.replace(/^[^\w]*/, '').trim();
            queryInput.value = query;
            queryInput.focus();
            // trigger auto height
            queryInput.dispatchEvent(new Event('input'));
        });
    });

    // Image Zoom Modal close
    closeModal.addEventListener('click', () => {
        imageModal.style.display = 'none';
    });
    imageModal.addEventListener('click', (e) => {
        if (e.target === imageModal) {
            imageModal.style.display = 'none';
        }
    });

    // Setup Inspector Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            btn.classList.add('active');
            const tabId = btn.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// ------------------ API CALLS ------------------

// Load all datasets
async function loadDatasets() {
    try {
        const res = await fetch(`${API_BASE}/api/datasets`);
        const data = await res.json();
        state.datasets = data;
        renderDatasets();
    } catch (err) {
        console.error('Error loading datasets:', err);
    }
}

// Load all conversations
async function loadConversations() {
    try {
        const res = await fetch(`${API_BASE}/api/conversations`);
        const data = await res.json();
        state.conversations = data;
        renderConversations();
    } catch (err) {
        console.error('Error loading conversations:', err);
    }
}

// Upload CSV file
async function uploadCSV(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        showGlobalLoading(true, "Uploading CSV...");
        const res = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Upload failed");
        }
        
        const data = await res.json();
        await loadDatasets();
        
        // Auto select and start new chat
        selectDataset(data.id, data.filename);
        startNewChat(data.id);
    } catch (err) {
        alert('Upload Error: ' + err.message);
    } finally {
        showGlobalLoading(false);
    }
}

// Upload CSV file directly for a specific conversation
async function uploadCSVForConversation(convId, file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        showGlobalLoading(true, "Uploading CSV...");
        const res = await fetch(`${API_BASE}/api/conversations/${convId}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Upload failed");
        }
        
        const data = await res.json();
        await loadDatasets();
        await loadConversations();
        
        // Relink view
        selectConversation(convId, `Chat on ${data.filename}`, data.id);
    } catch (err) {
        alert('Upload Error: ' + err.message);
    } finally {
        showGlobalLoading(false);
    }
}

// Link an existing dataset to a conversation
async function linkDatasetToConversation(convId, datasetId) {
    try {
        showGlobalLoading(true, "Linking Dataset...");
        const res = await fetch(`${API_BASE}/api/conversations/${convId}/dataset/${datasetId}`, {
            method: 'PUT'
        });
        
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Link failed");
        }
        
        const dataset = state.datasets.find(d => d.id == datasetId);
        const name = dataset ? dataset.filename : "CSV";
        
        await loadConversations();
        selectConversation(convId, `Chat on ${name}`, datasetId);
    } catch (err) {
        alert('Link Error: ' + err.message);
    } finally {
        showGlobalLoading(false);
    }
}

// Start a new chat session for a dataset
async function startNewChat(datasetId) {
    const dataset = datasetId ? state.datasets.find(d => d.id === datasetId) : null;
    const title = dataset ? `Chat on ${dataset.filename}` : "New Analysis";
    
    try {
        const res = await fetch(`${API_BASE}/api/conversations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dataset_id: datasetId, title })
        });
        const data = await res.json();
        
        state.activeConversationId = data.id;
        await loadConversations();
        selectConversation(data.id, data.title, datasetId);
    } catch (err) {
        console.error('Error starting conversation:', err);
    }
}

// Delete Dataset
async function deleteDataset(id, e) {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this dataset? This will delete all associated conversations.')) {
        return;
    }
    
    try {
        const res = await fetch(`${API_BASE}/api/datasets/${id}`, {
            method: 'DELETE'
        });
        
        if (res.ok) {
            if (state.activeDatasetId === id) {
                state.activeDatasetId = null;
                state.activeConversationId = null;
                resetWorkspaceView();
            }
            loadDatasets();
            loadConversations();
        }
    } catch (err) {
        console.error('Error deleting dataset:', err);
    }
}

// Delete Conversation
async function deleteConversation(id, e) {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this conversation? This will delete all chat history and associated charts.')) {
        return;
    }
    
    try {
        const res = await fetch(`${API_BASE}/api/conversations/${id}`, {
            method: 'DELETE'
        });
        
        if (res.ok) {
            if (state.activeConversationId === id) {
                state.activeConversationId = null;
                resetWorkspaceView();
            }
            loadConversations();
        }
    } catch (err) {
        console.error('Error deleting conversation:', err);
    }
}

// Rename Dataset
async function renameDataset(id, oldName, e) {
    e.stopPropagation();
    const newName = prompt('Enter a new filename:', oldName);
    if (!newName || newName === oldName) return;
    
    try {
        const res = await fetch(`${API_BASE}/api/datasets/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: newName })
        });
        
        if (res.ok) {
            loadDatasets();
            if (state.activeDatasetId === id) {
                activeDatasetName.innerText = newName;
            }
        }
    } catch (err) {
        console.error('Error renaming dataset:', err);
    }
}

// Download Dataset
function downloadDataset(id, e) {
    e.stopPropagation();
    window.open(`${API_BASE}/api/datasets/${id}/download`, '_blank');
}

// Fetch and render messages for conversation
async function loadMessages(convId, datasetId) {
    try {
        const res = await fetch(`${API_BASE}/api/conversations/${convId}/messages`);
        const messages = await res.json();
        
        messagesLog.innerHTML = '';
        if (!datasetId) {
            welcomeScreen.style.display = 'none';
            messagesLog.style.display = 'none';
            return;
        }
        
        if (messages.length === 0) {
            welcomeScreen.style.display = 'flex';
            messagesLog.style.display = 'none';
        } else {
            welcomeScreen.style.display = 'none';
            messagesLog.style.display = 'flex';
            
            messages.forEach(m => {
                // Determine if message has table or chart payload stored. 
                // Since DB message content is simple text, let's parse charts and tables
                appendMessage(m.role, m.content, m.result, m.chart_path);
            });
            scrollToBottom();
        }
    } catch (err) {
        console.error('Error loading messages:', err);
    }
}

// Submit a Query
async function submitQuery() {
    const query = queryInput.value.trim();
    if (!query || state.loading || !state.activeConversationId) return;
    
    // Add user message to UI immediately
    appendMessage('user', query);
    queryInput.value = '';
    queryInput.style.height = 'auto'; // reset textarea height
    scrollToBottom();
    
    setControlsLoading(true);
    showPipelineStatus(true);
    
    try {
        // Run simulated pipeline transitions to give visual feedback of which Agent is running
        runSimulatedPipelineSteps();
        
        const res = await fetch(`${API_BASE}/api/conversations/${state.activeConversationId}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        
        if (!res.ok) {
            let errMsg = "Failed to execute query";
            try {
                const errData = await res.json();
                errMsg = errData.detail || errMsg;
            } catch(e) {}
            throw new Error(errMsg);
        }
        
        const data = await res.json();
        
        // Finish pipeline successfully
        completeAllPipelineSteps();
        
        // Append response message
        setTimeout(() => {
            showPipelineStatus(false);
            if (data.error) {
                appendMessage('assistant', `⚠️ **Error during execution:** ${data.error}`);
            } else {
                appendMessage('assistant', data.insights, data.result, data.chart_path);
                // Refresh active dataset preview in the inspector
                loadDatasetPreview(state.activeConversationId);
            }
            scrollToBottom();
        }, 800);
        
    } catch (err) {
        showPipelineStatus(false);
        const isNetwork = err.message === "Failed to execute query" && !err.message.includes("Failed to execute query:");
        const msg = isNetwork 
            ? "⚠️ **Network Error:** Could not contact server. Please make sure the backend server is running."
            : `⚠️ **Execution Error:** ${err.message}`;
        appendMessage('assistant', msg);
        scrollToBottom();
    } finally {
        setTimeout(() => {
            setControlsLoading(false);
        }, 800);
    }
}

// ------------------ UI RENDERING ------------------

function renderDatasets() {
    datasetList.innerHTML = '';
    if (state.datasets.length === 0) {
        datasetList.innerHTML = '<div class="empty-list-msg">No datasets uploaded</div>';
        return;
    }
    
    state.datasets.forEach(d => {
        const item = document.createElement('div');
        item.className = `dataset-item ${state.activeDatasetId === d.id ? 'active' : ''}`;
        item.innerHTML = `
            <div class="dataset-info">
                <i class="fa-solid fa-file-csv"></i>
                <div class="dataset-name" title="${d.filename}">${d.filename}</div>
            </div>
            <div class="dataset-actions">
                <button class="download-btn" title="Download CSV"><i class="fa-solid fa-download"></i></button>
                <button class="rename-btn" title="Rename"><i class="fa-solid fa-pen"></i></button>
                <button class="delete-btn" title="Delete"><i class="fa-solid fa-trash-can"></i></button>
            </div>
        `;
        
        // Click to select
        item.addEventListener('click', () => {
            selectDataset(d.id, d.filename);
        });
        
        // Action buttons
        item.querySelector('.download-btn').addEventListener('click', (e) => downloadDataset(d.id, e));
        item.querySelector('.rename-btn').addEventListener('click', (e) => renameDataset(d.id, d.filename, e));
        item.querySelector('.delete-btn').addEventListener('click', (e) => deleteDataset(d.id, e));
        
        datasetList.appendChild(item);
    });
}

function renderConversations() {
    conversationList.innerHTML = '';
    if (state.conversations.length === 0) {
        conversationList.innerHTML = '<div class="empty-list-msg">No conversations started</div>';
        return;
    }
    
    state.conversations.forEach(c => {
        const item = document.createElement('div');
        item.className = `conv-item ${state.activeConversationId === c.id ? 'active' : ''}`;
        item.innerHTML = `
            <div class="conv-info" style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; overflow: hidden;">
                <i class="fa-regular fa-comment" style="flex-shrink: 0;"></i>
                <span class="conv-title" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${c.title}">${c.title}</span>
            </div>
            <div class="conv-actions">
                <button class="delete-btn" title="Delete Chat"><i class="fa-solid fa-trash-can"></i></button>
            </div>
        `;
        
        // Click to select
        item.addEventListener('click', () => {
            selectConversation(c.id, c.title, c.dataset_id);
        });
        
        // Delete button click
        item.querySelector('.delete-btn').addEventListener('click', (e) => deleteConversation(c.id, e));
        
        conversationList.appendChild(item);
    });
}

function selectDataset(id, filename) {
    state.activeDatasetId = id;
    renderDatasets();
    
    activeDatasetDisplay.style.display = 'flex';
    activeDatasetName.innerText = filename;
    
    // Check if there is already a conversation active, if not suggest starting one
    if (!state.activeConversationId) {
        activeConversationTitle.innerText = "Click New Chat to begin analyzing";
    }
}

function selectConversation(id, title, datasetId) {
    state.activeConversationId = id;
    state.activeDatasetId = datasetId;
    
    const dataset = datasetId ? state.datasets.find(d => d.id === datasetId) : null;
    
    if (datasetId) {
        activeDatasetDisplay.style.display = 'flex';
        activeDatasetName.innerText = dataset ? dataset.filename : "CSV";
        activeConversationTitle.innerText = title;
        
        // Hide dropzone
        datasetDropzone.style.display = 'none';
        
        // Enable input fields
        queryInput.disabled = false;
        sendBtn.disabled = false;
        queryInput.focus();
    } else {
        activeDatasetDisplay.style.display = 'none';
        activeConversationTitle.innerText = title + " (No Dataset)";
        
        // Show dropzone
        datasetDropzone.style.display = 'flex';
        welcomeScreen.style.display = 'none';
        messagesLog.style.display = 'none';
        
        // Disable inputs
        queryInput.disabled = true;
        sendBtn.disabled = true;
        
        // Populate dropdown with existing datasets
        populateExistingDatasetSelect();
    }
    
    renderDatasets();
    renderConversations();
    
    loadMessages(id, datasetId);
    loadDatasetPreview(id);
}

function populateExistingDatasetSelect() {
    existingDatasetSelect.innerHTML = '<option value="">-- Select --</option>';
    state.datasets.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.id;
        opt.innerText = d.filename;
        existingDatasetSelect.appendChild(opt);
    });
}

function resetWorkspaceView() {
    activeDatasetDisplay.style.display = 'none';
    activeConversationTitle.innerText = "Select a dataset to begin";
    welcomeScreen.style.display = 'flex';
    datasetDropzone.style.display = 'none';
    messagesLog.style.display = 'none';
    queryInput.disabled = true;
    sendBtn.disabled = true;
    document.getElementById('inspector-panel').style.display = 'none';
    renderDatasets();
    renderConversations();
}

// Append message block to log
function appendMessage(role, text, result = null, chartPath = null) {
    welcomeScreen.style.display = 'none';
    messagesLog.style.display = 'flex';
    
    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    
    const avatar = role === 'user' ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-microchip"></i>';
    const sender = role === 'user' ? 'You' : 'AeroAnalyst AI';
    
    // Format text content (replace markdown-like bullet points or bold text)
    const formattedText = formatMarkdownText(text);
    
    msg.innerHTML = `
        <div class="msg-avatar">${avatar}</div>
        <div class="msg-bubble">
            <div class="msg-header">
                <span class="msg-sender">${sender}</span>
            </div>
            <div class="msg-content">${formattedText}</div>
            <div class="msg-attachments"></div>
        </div>
    `;
    
    const attachments = msg.querySelector('.msg-attachments');
    
    // Append Pandas table if result matches type dataframe
    if (result && (result.type === 'dataframe' || result.type === 'series')) {
        const tableHtml = createTableHTML(result);
        attachments.appendChild(tableHtml);
    } else if (result && result.type === 'scalar' && result.data !== 'None' && result.data !== '') {
        const scalarVal = document.createElement('div');
        scalarVal.className = 'table-wrapper';
        scalarVal.innerHTML = `<div style="padding: 12px; font-family: monospace; font-size: 0.9rem;">Result: ${result.data}</div>`;
        attachments.appendChild(scalarVal);
    }
    
    // Append Plot if chartPath exists
    if (chartPath) {
        let isJsonSpec = false;
        let spec = null;
        try {
            if (typeof chartPath === 'string' && (chartPath.trim().startsWith('{') || chartPath.trim().startsWith('['))) {
                spec = JSON.parse(chartPath);
                isJsonSpec = true;
            } else if (typeof chartPath === 'object' && chartPath !== null) {
                spec = chartPath;
                isJsonSpec = true;
            }
        } catch (e) {
            console.warn("Failed to parse chart spec, rendering as image:", e);
        }

        if (isJsonSpec && spec && spec.data) {
            const chartBlock = document.createElement('div');
            chartBlock.className = 'chart-wrapper interactive-chart';
            chartBlock.style.position = 'relative';
            chartBlock.style.width = '100%';
            chartBlock.style.height = '320px';
            chartBlock.style.background = '#ffffff';
            chartBlock.style.borderRadius = '12px';
            chartBlock.style.padding = '16px';
            chartBlock.style.border = '1px solid var(--border-color)';
            chartBlock.style.boxSizing = 'border-box';
            chartBlock.style.marginTop = '12px';

            const canvas = document.createElement('canvas');
            
            // Create download button
            const downloadBtn = document.createElement('button');
            downloadBtn.className = 'chart-download-btn';
            downloadBtn.title = 'Download Chart Image';
            downloadBtn.style.position = 'absolute';
            downloadBtn.style.top = '12px';
            downloadBtn.style.right = '12px';
            downloadBtn.style.background = 'rgba(255,255,255,0.9)';
            downloadBtn.style.border = '1px solid var(--border-color)';
            downloadBtn.style.color = '#475569';
            downloadBtn.style.cursor = 'pointer';
            downloadBtn.style.padding = '6px 10px';
            downloadBtn.style.borderRadius = '6px';
            downloadBtn.style.transition = 'all 0.15s ease';
            downloadBtn.style.zIndex = '10';
            downloadBtn.style.display = 'flex';
            downloadBtn.style.alignItems = 'center';
            downloadBtn.style.gap = '6px';
            downloadBtn.style.fontFamily = 'Plus Jakarta Sans';
            downloadBtn.style.fontSize = '0.75rem';
            downloadBtn.style.fontWeight = '600';
            downloadBtn.style.boxShadow = '0 2px 8px rgba(0,0,0,0.05)';
            downloadBtn.innerHTML = `<i class="fa-solid fa-download"></i> <span>Download</span>`;

            downloadBtn.addEventListener('mouseenter', () => {
                downloadBtn.style.background = 'var(--accent-gradient)';
                downloadBtn.style.color = '#ffffff';
                downloadBtn.style.borderColor = 'transparent';
            });
            downloadBtn.addEventListener('mouseleave', () => {
                downloadBtn.style.background = 'rgba(255,255,255,0.9)';
                downloadBtn.style.color = '#475569';
                downloadBtn.style.borderColor = 'var(--border-color)';
            });

            downloadBtn.addEventListener('click', () => {
                try {
                    const link = document.createElement('a');
                    link.download = `${spec.title || 'chart'}.png`;
                    
                    const tempCanvas = document.createElement('canvas');
                    tempCanvas.width = canvas.width;
                    tempCanvas.height = canvas.height;
                    const ctx = tempCanvas.getContext('2d');
                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
                    ctx.drawImage(canvas, 0, 0);
                    
                    link.href = tempCanvas.toDataURL('image/png');
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } catch (err) {
                    console.error("Failed to download chart image:", err);
                }
            });

            chartBlock.appendChild(downloadBtn);
            chartBlock.appendChild(canvas);
            attachments.appendChild(chartBlock);

            try {
                // Prepare Chart.js data
                const labels = spec.data.map(item => item[spec.x]);
                const values = spec.data.map(item => item[spec.y]);

                // Create nice colors
                const baseColor = 'rgba(16, 124, 65, 0.7)';
                const borderColor = 'rgba(16, 124, 65, 1)';
                
                let backgroundColors = baseColor;
                let borderColors = borderColor;
                if (['pie', 'doughnut', 'polarArea'].includes(spec.type)) {
                    backgroundColors = spec.data.map((_, i) => {
                        const hue = (i * (360 / Math.max(1, spec.data.length))) % 360;
                        return `hsla(${hue}, 65%, 45%, 0.7)`;
                    });
                    borderColors = spec.data.map((_, i) => {
                        const hue = (i * (360 / Math.max(1, spec.data.length))) % 360;
                        return `hsla(${hue}, 65%, 45%, 1)`;
                    });
                }

                new Chart(canvas, {
                    type: spec.type || 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: spec.y || 'Value',
                            data: values,
                            backgroundColor: backgroundColors,
                            borderColor: borderColors,
                            borderWidth: 1.5,
                            borderRadius: spec.type === 'bar' ? 6 : 0,
                            hoverBackgroundColor: 'rgba(16, 124, 65, 0.95)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: ['pie', 'doughnut', 'polarArea'].includes(spec.type),
                                position: 'bottom',
                                labels: {
                                    font: { family: 'Plus Jakarta Sans', size: 11 },
                                    color: '#475569'
                                }
                            },
                            title: {
                                display: !!spec.title,
                                text: spec.title,
                                font: { family: 'Space Grotesk', size: 14, weight: 'bold' },
                                color: '#0f172a',
                                padding: { bottom: 12 }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                                titleFont: { family: 'Plus Jakarta Sans', weight: 'bold' },
                                bodyFont: { family: 'Plus Jakarta Sans' },
                                padding: 10,
                                cornerRadius: 8
                            }
                        },
                        scales: ['pie', 'doughnut', 'polarArea', 'radar'].includes(spec.type) ? {} : {
                            x: {
                                grid: { display: false },
                                ticks: {
                                    font: { family: 'Plus Jakarta Sans', size: 10 },
                                    color: '#64748b'
                                }
                            },
                            y: {
                                grid: { color: 'rgba(0, 0, 0, 0.05)' },
                                ticks: {
                                    font: { family: 'Plus Jakarta Sans', size: 10 },
                                    color: '#64748b'
                                }
                            }
                        }
                    }
                });
            } catch (err) {
                console.error("Error creating Chart.js chart:", err);
                chartBlock.innerHTML = `<div style="color: #dc2626; padding: 16px;">Failed to render interactive chart: ${err.message}</div>`;
            }
        } else {
            const chartBlock = document.createElement('div');
            chartBlock.className = 'chart-wrapper';
            
            let imgSrc = '';
            if (chartPath.startsWith('data:')) {
                imgSrc = chartPath;
            } else {
                const cacheBuster = `?t=${new Date().getTime()}`;
                const relativeChartPath = chartPath.replace(/\\/g, '/');
                imgSrc = `/${relativeChartPath}${cacheBuster}`;
            }
            
            chartBlock.innerHTML = `
                <img src="${imgSrc}" alt="Data Visualization">
                <div class="chart-overlay"><i class="fa-solid fa-magnifying-glass-plus"></i> Click to Zoom</div>
            `;
            
            chartBlock.addEventListener('click', () => {
                zoomImage(imgSrc, text);
            });
            
            attachments.appendChild(chartBlock);
        }
    }
    
    messagesLog.appendChild(msg);
    scrollToBottom();
}

function zoomImage(src, caption) {
    imageModal.style.display = 'block';
    modalImg.src = src;
    modalCaption.innerHTML = formatMarkdownText(caption.substring(0, 100) + '...');
}

// Convert dataset json into HTML table
function createTableHTML(res) {
    const wrapper = document.createElement('div');
    wrapper.className = 'table-wrapper';
    
    if (res.type === 'dataframe') {
        let headers = res.columns.map(c => `<th>${c}</th>`).join('');
        let rows = res.data.map(row => {
            let cells = row.map(cell => `<td>${cell === null ? '<span style="color: var(--text-muted);">null</span>' : cell}</td>`).join('');
            return `<tr>${cells}</tr>`;
        }).join('');
        
        wrapper.innerHTML = `
            <table class="rendered-table">
                <thead><tr>${headers}</tr></thead>
                <tbody>${rows}</tbody>
            </table>
            <div class="table-summary">
                <span>Showing first ${res.data.length} rows</span>
                <span>Total records: ${res.total_rows}</span>
            </div>
        `;
    } else if (res.type === 'series') {
        let rows = res.index.map((key, i) => {
            return `<tr><th>${key}</th><td>${res.data[i]}</td></tr>`;
        }).join('');
        
        wrapper.innerHTML = `
            <table class="rendered-table">
                <thead><tr><th>Metric / Index</th><th>Value</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    }
    
    return wrapper;
}

// Simple regex Markdown parser
function formatMarkdownText(text) {
    if (!text) return '';
    let parsed = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code style="background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px; font-family: monospace; color: var(--text-primary);">$1</code>')
        .replace(/\n/g, '<br>');
    return parsed;
}

// ------------------ HELPERS ------------------

function showGlobalLoading(show, text = "Loading...") {
    // Basic blocker
    if (show) {
        newChatBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> ${text}`;
        newChatBtn.disabled = true;
    } else {
        newChatBtn.innerHTML = `<i class="fa-solid fa-plus"></i> New Chat`;
        newChatBtn.disabled = false;
    }
}

function setControlsLoading(loading) {
    state.loading = loading;
    queryInput.disabled = loading;
    sendBtn.disabled = loading;
    
    if (loading) {
        sendBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
    } else {
        sendBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i>';
        queryInput.focus();
    }
}

function scrollToBottom() {
    const chatArea = document.querySelector('.chat-area');
    if (chatArea) {
        chatArea.scrollTop = chatArea.scrollHeight;
    }
}

function showPipelineStatus(show) {
    if (show) {
        agentPipeline.style.display = 'flex';
        resetPipelineSteps();
    } else {
        agentPipeline.style.display = 'none';
    }
}

function resetPipelineSteps() {
    document.querySelectorAll('.pipeline-steps .step').forEach(step => {
        step.className = 'step';
        step.querySelector('i').className = 'fa-regular fa-circle';
    });
}

function runSimulatedPipelineSteps() {
    const steps = [
        { id: 'step-schema', delay: 100 },
        { id: 'step-query', delay: 1500 },
        { id: 'step-code', delay: 3000 },
        { id: 'step-execute', delay: 4800 },
        { id: 'step-visualization', delay: 6500 },
        { id: 'step-insight', delay: 8200 }
    ];
    
    steps.forEach((step, index) => {
        setTimeout(() => {
            if (!state.loading) return; // cancel if finished early
            
            // Mark previous as complete
            if (index > 0) {
                const prev = document.getElementById(steps[index-1].id);
                prev.className = 'step completed';
                prev.querySelector('i').className = 'fa-solid fa-circle-check';
            }
            
            // Active current
            const curr = document.getElementById(step.id);
            curr.className = 'step active';
            curr.querySelector('i').className = 'fa-solid fa-circle-notch fa-spin';
            
            scrollToBottom();
        }, step.delay);
    });
}

function completeAllPipelineSteps() {
    document.querySelectorAll('.pipeline-steps .step').forEach(step => {
        step.className = 'step completed';
        step.querySelector('i').className = 'fa-solid fa-circle-check';
    });
}

// Load and display dataset preview / schema in inspector
async function loadDatasetPreview(convId) {
    const inspectorPanel = document.getElementById('inspector-panel');
    const tableContainer = document.getElementById('inspector-table-container');
    const schemaContainer = document.getElementById('inspector-schema-container');
    const statsContainer = document.getElementById('inspector-stats-container');
    const metaText = document.getElementById('inspector-meta-text');
    
    if (!convId) {
        inspectorPanel.style.display = 'none';
        return;
    }
    
    try {
        const res = await fetch(`${API_BASE}/api/conversations/${convId}/preview`);
        if (!res.ok) throw new Error("Failed to load preview");
        
        const preview = await res.json();
        
        if (preview.status === "empty") {
            inspectorPanel.style.display = 'none';
            return;
        }
        
        // Show panel
        inspectorPanel.style.display = 'flex';
        
        // Render Meta Info
        const shape = preview.shape || [0, 0];
        metaText.innerText = `${shape[0].toLocaleString()} rows × ${shape[1]} columns`;
        
        // Render Table Preview
        if (preview.columns && preview.data) {
            let headers = `<th>#</th>` + preview.columns.map(c => `<th>${c}</th>`).join('');
            let rows = preview.data.map((row, rIdx) => {
                let cells = `<td class="index-col">${rIdx + 1}</td>` + row.map(cell => {
                    return `<td>${cell === null ? '<span style="color: var(--text-muted); font-style: italic;">null</span>' : cell}</td>`;
                }).join('');
                return `<tr class="${rIdx % 2 === 1 ? 'odd-row' : ''}">${cells}</tr>`;
            }).join('');
            
            tableContainer.innerHTML = `
                <table class="inspector-table">
                    <thead><tr>${headers}</tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            `;
        } else {
            tableContainer.innerHTML = '<div class="inspector-empty-state">No preview data available.</div>';
        }
        
        // Render Schema & Types
        if (preview.columns && preview.dtypes) {
            let schemaHtml = '';
            preview.columns.forEach(col => {
                const type = preview.dtypes[col] || 'unknown';
                let badgeClass = 'type-object';
                if (type.includes('int')) badgeClass = 'type-int';
                else if (type.includes('float')) badgeClass = 'type-float';
                else if (type.includes('bool')) badgeClass = 'type-bool';
                
                const missingCount = preview.missing ? (preview.missing[col] || 0) : 0;
                const uniqueCount = preview.nunique ? (preview.nunique[col] || 0) : 0;
                
                schemaHtml += `
                    <div class="schema-card">
                        <div class="schema-card-header">
                            <span class="schema-col-name">${col}</span>
                            <span class="type-badge ${badgeClass}">${type}</span>
                        </div>
                        <div class="schema-card-body">
                            <div class="schema-stat-item">
                                <span class="schema-stat-label">Missing Values</span>
                                <span class="schema-stat-value" style="${missingCount > 0 ? 'color: var(--error);' : ''}">${missingCount}</span>
                            </div>
                            <div class="schema-stat-item">
                                <span class="schema-stat-label">Unique Values</span>
                                <span class="schema-stat-value">${uniqueCount}</span>
                            </div>
                        </div>
                    </div>
                `;
            });
            schemaContainer.innerHTML = schemaHtml;
        } else {
            schemaContainer.innerHTML = '<div class="inspector-empty-state">No schema details available.</div>';
        }
        
        // Render Summary Stats
        if (preview.summary) {
            // Find all unique stat labels across columns
            let statKeys = ['count', 'unique', 'top', 'freq', 'mean', 'std', 'min', '25%', '50%', '75%', 'max'];
            
            // Build summary statistics table
            let headers = `<th>Stat</th>` + preview.columns.map(c => `<th>${c}</th>`).join('');
            
            let rows = statKeys.map((key, rIdx) => {
                // Check if at least one column has this stat key
                let hasStat = preview.columns.some(col => preview.summary[col] && preview.summary[col][key] !== undefined && preview.summary[col][key] !== null);
                if (!hasStat) return ''; // Skip this stat row if no column has it
                
                let cells = `<td class="index-col" style="text-align: left; padding-left: 10px; width: 80px;">${key}</td>` + preview.columns.map(col => {
                    let val = (preview.summary[col] && preview.summary[col][key] !== undefined) ? preview.summary[col][key] : '-';
                    // Format float numbers
                    if (typeof val === 'number' && !Number.isInteger(val)) {
                        val = val.toFixed(4);
                    }
                    return `<td>${val}</td>`;
                }).join('');
                return `<tr class="${rIdx % 2 === 1 ? 'odd-row' : ''}">${cells}</tr>`;
            }).filter(Boolean).join('');
            
            statsContainer.innerHTML = `
                <table class="inspector-table">
                    <thead><tr>${headers}</tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            `;
        } else {
            statsContainer.innerHTML = '<div class="inspector-empty-state">No stats summary available.</div>';
        }
        
    } catch (err) {
        console.error("Error loading preview:", err);
        tableContainer.innerHTML = `<div class="inspector-empty-state" style="color: var(--error);">Failed to load preview: ${err.message}</div>`;
        schemaContainer.innerHTML = `<div class="inspector-empty-state" style="color: var(--error);">Failed to load schema.</div>`;
        statsContainer.innerHTML = `<div class="inspector-empty-state" style="color: var(--error);">Failed to load summary statistics.</div>`;
    }
}
