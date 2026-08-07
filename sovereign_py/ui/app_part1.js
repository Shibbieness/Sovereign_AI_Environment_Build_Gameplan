/**
 * ML Filesystem - Main JavaScript Application
 * Part 1: Core Functions, File Operations, and UI Management
 */

// ============================================================================
// Utility Functions
// ============================================================================

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    const content = document.getElementById('notificationContent');
    
    const colors = {
        'info': '#3b82f6',
        'success': '#10b981',
        'error': '#ef4444',
        'warning': '#f59e0b'
    };
    
    content.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <div style="width: 4px; height: 40px; background: ${colors[type]}; border-radius: 2px;"></div>
            <div>${message}</div>
        </div>
    `;
    
    notification.classList.add('active');
    
    setTimeout(() => {
        notification.classList.remove('active');
    }, 3000);
}

function showModal(title, content, actions = []) {
    const modalId = 'modal-' + Date.now();
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = modalId;
    
    const actionsHtml = actions.map(action => `
        <button class="btn ${action.class || 'btn-primary'}" onclick="${action.onclick}">
            ${action.icon ? `<i class="${action.icon}"></i>` : ''} ${action.label}
        </button>
    `).join('');
    
    modal.innerHTML = `
        <div class="modal-content" style="max-width: ${actions.maxWidth || '600px'};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <h2 class="text-2xl font-bold">${title}</h2>
                <button onclick="document.getElementById('${modalId}').remove()" class="text-gray-400 hover:text-white">
                    <i class="fas fa-times text-xl"></i>
                </button>
            </div>
            <div>${content}</div>
            ${actions.length > 0 ? `
                <div style="display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1.5rem;">
                    ${actionsHtml}
                </div>
            ` : ''}
        </div>
    `;
    
    document.body.appendChild(modal);
    return modalId;
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 300);
    }
}

// ============================================================================
// View Management
// ============================================================================

async function loadView(view) {
    const contentArea = document.getElementById('contentArea');
    
    switch (view) {
        case 'files':
            await loadFiles(state.currentPath);
            renderFiles();
            break;
            
        case 'agents':
            await loadAgents();
            renderAgentsView();
            break;
            
        case 'chains':
            await loadChains();
            renderChainsView();
            break;
            
        case 'search':
            renderSearchView();
            break;
            
        case 'activity':
            await loadActivity();
            renderActivityView();
            break;
            
        case 'profile':
            renderProfileView();
            break;
    }
}

function updateBreadcrumb() {
    const breadcrumb = document.getElementById('breadcrumb');
    const parts = state.currentPath.split('/').filter(p => p);
    
    let html = `
        <div class="breadcrumb-item" onclick="navigateToPath('/')">
            <i class="fas fa-home"></i>
        </div>
    `;
    
    let currentPath = '';
    for (const part of parts) {
        currentPath += '/' + part;
        const path = currentPath;
        html += `
            <i class="fas fa-chevron-right text-gray-500 text-xs"></i>
            <div class="breadcrumb-item" onclick="navigateToPath('${path}')">
                ${escapeHtml(part)}
            </div>
        `;
    }
    
    breadcrumb.innerHTML = html;
}

async function navigateToPath(path) {
    await loadFiles(path);
    renderFiles();
}

function toggleView() {
    state.viewMode = state.viewMode === 'grid' ? 'list' : 'grid';
    const icon = document.querySelector('#viewToggle i');
    icon.className = state.viewMode === 'grid' ? 'fas fa-th' : 'fas fa-list';
    renderFiles();
}

// ============================================================================
// File Operations
// ============================================================================

function showNewFileModal() {
    const modalId = showModal('Create New File', `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-2">File Name</label>
                <input type="text" id="newFileName" class="input" placeholder="example.txt">
            </div>
            <div>
                <label class="block text-sm font-medium mb-2">Content (optional)</label>
                <textarea id="newFileContent" class="input" rows="6" placeholder="File content..."></textarea>
            </div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Create',
            class: 'btn-primary',
            icon: 'fas fa-check',
            onclick: `createNewFile('${modalId}')`
        }
    ]);
}

async function createNewFile(modalId) {
    const fileName = document.getElementById('newFileName').value.trim();
    const content = document.getElementById('newFileContent').value;
    
    if (!fileName) {
        showNotification('Please enter a file name', 'error');
        return;
    }
    
    const path = state.currentPath === '/' ? `/${fileName}` : `${state.currentPath}/${fileName}`;
    
    try {
        const response = await fetch(`${API_BASE}/files/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, content })
        });
        
        if (response.ok) {
            showNotification('File created successfully', 'success');
            closeModal(modalId);
            await loadFiles(state.currentPath);
            renderFiles();
        } else {
            const error = await response.json();
            showNotification('Failed to create file: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to create file: ' + error.message, 'error');
    }
}

function showNewFolderModal() {
    const modalId = showModal('Create New Folder', `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-2">Folder Name</label>
                <input type="text" id="newFolderName" class="input" placeholder="My Folder">
            </div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Create',
            class: 'btn-primary',
            icon: 'fas fa-check',
            onclick: `createNewFolder('${modalId}')`
        }
    ]);
}

async function createNewFolder(modalId) {
    const folderName = document.getElementById('newFolderName').value.trim();
    
    if (!folderName) {
        showNotification('Please enter a folder name', 'error');
        return;
    }
    
    const path = state.currentPath === '/' ? `/${folderName}` : `${state.currentPath}/${folderName}`;
    
    try {
        const response = await fetch(`${API_BASE}/files/mkdir`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        
        if (response.ok) {
            showNotification('Folder created successfully', 'success');
            closeModal(modalId);
            await loadFiles(state.currentPath);
            renderFiles();
        } else {
            const error = await response.json();
            showNotification('Failed to create folder: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to create folder: ' + error.message, 'error');
    }
}

function showUploadModal() {
    const modalId = showModal('Upload File', `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-2">Select File</label>
                <input type="file" id="uploadFile" class="input" multiple>
            </div>
            <div class="text-sm text-gray-400">
                Maximum file size: 100MB
            </div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Upload',
            class: 'btn-primary',
            icon: 'fas fa-upload',
            onclick: `uploadFiles('${modalId}')`
        }
    ]);
}

async function uploadFiles(modalId) {
    const input = document.getElementById('uploadFile');
    const files = input.files;
    
    if (files.length === 0) {
        showNotification('Please select a file', 'error');
        return;
    }
    
    for (const file of files) {
        const reader = new FileReader();
        
        reader.onload = async (e) => {
            const content = e.target.result;
            const fileName = file.name;
            const path = state.currentPath === '/' ? `/${fileName}` : `${state.currentPath}/${fileName}`;
            
            try {
                const response = await fetch(`${API_BASE}/files/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path, content })
                });
                
                if (response.ok) {
                    showNotification(`File uploaded: ${fileName}`, 'success');
                } else {
                    const error = await response.json();
                    showNotification(`Failed to upload ${fileName}: ` + error.error, 'error');
                }
            } catch (error) {
                showNotification(`Failed to upload ${fileName}: ` + error.message, 'error');
            }
        };
        
        reader.readAsText(file);
    }
    
    closeModal(modalId);
    
    setTimeout(async () => {
        await loadFiles(state.currentPath);
        renderFiles();
    }, 1000);
}

async function deleteFile(fileId) {
    const file = state.files.find(f => f.id === fileId);
    if (!file) return;
    
    if (!confirm(`Are you sure you want to delete "${file.name}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/files/delete?path=${encodeURIComponent(file.path)}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('File deleted successfully', 'success');
            await loadFiles(state.currentPath);
            renderFiles();
        } else {
            const error = await response.json();
            showNotification('Failed to delete file: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to delete file: ' + error.message, 'error');
    }
}

function renameFile(fileId) {
    const file = state.files.find(f => f.id === fileId);
    if (!file) return;
    
    const modalId = showModal('Rename', `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-2">New Name</label>
                <input type="text" id="renameInput" class="input" value="${escapeHtml(file.name)}">
            </div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Rename',
            class: 'btn-primary',
            icon: 'fas fa-check',
            onclick: `performRename(${fileId}, '${modalId}')`
        }
    ]);
}

async function performRename(fileId, modalId) {
    const file = state.files.find(f => f.id === fileId);
    const newName = document.getElementById('renameInput').value.trim();
    
    if (!newName) {
        showNotification('Please enter a name', 'error');
        return;
    }
    
    const pathParts = file.path.split('/');
    pathParts[pathParts.length - 1] = newName;
    const newPath = pathParts.join('/');
    
    try {
        const response = await fetch(`${API_BASE}/files/move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source: file.path,
                destination: newPath
            })
        });
        
        if (response.ok) {
            showNotification('File renamed successfully', 'success');
            closeModal(modalId);
            await loadFiles(state.currentPath);
            renderFiles();
        } else {
            const error = await response.json();
            showNotification('Failed to rename file: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to rename file: ' + error.message, 'error');
    }
}

async function markForLearning(fileId) {
    try {
        const response = await fetch(`${API_BASE}/files/mark-for-learning`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_ids: [fileId],
                marked: true
            })
        });
        
        if (response.ok) {
            showNotification('File marked for learning', 'success');
            await loadFiles(state.currentPath);
            renderFiles();
        } else {
            const error = await response.json();
            showNotification('Failed to mark file: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to mark file: ' + error.message, 'error');
    }
}

// ============================================================================
// File Editor
// ============================================================================

let monacoEditor = null;
let currentEditingFile = null;

async function openFileEditor(file) {
    try {
        const response = await fetch(`${API_BASE}/files/read?path=${encodeURIComponent(file.path)}`);
        if (!response.ok) {
            throw new Error('Failed to load file');
        }
        
        const data = await response.json();
        currentEditingFile = file;
        
        const modalId = showModal(`Edit: ${file.name}`, `
            <div id="editorContainer" class="editor-container"></div>
        `, [
            {
                label: 'Close',
                class: 'btn-secondary',
                onclick: `closeEditor('${modalId}')`
            },
            {
                label: 'Save',
                class: 'btn-success',
                icon: 'fas fa-save',
                onclick: `saveFile('${modalId}')`
            }
        ]);
        
        // Wait for modal to render
        setTimeout(() => {
            initializeMonacoEditor(data.content, file.file_type);
        }, 100);
        
    } catch (error) {
        showNotification('Failed to open file: ' + error.message, 'error');
    }
}

function initializeMonacoEditor(content, fileType) {
    require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.44.0/min/vs' } });
    
    require(['vs/editor/editor.main'], function() {
        const languageMap = {
            'code': 'javascript',
            'text': 'plaintext',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'python': 'python'
        };
        
        const language = languageMap[fileType] || 'plaintext';
        
        monacoEditor = monaco.editor.create(document.getElementById('editorContainer'), {
            value: content,
            language: language,
            theme: 'vs-dark',
            automaticLayout: true,
            fontSize: 14,
            minimap: { enabled: true },
            wordWrap: 'on',
            lineNumbers: 'on',
            scrollBeyondLastLine: false
        });
    });
}

async function saveFile(modalId) {
    if (!monacoEditor || !currentEditingFile) return;
    
    const content = monacoEditor.getValue();
    
    try {
        const response = await fetch(`${API_BASE}/files/update`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                path: currentEditingFile.path,
                content: content
            })
        });
        
        if (response.ok) {
            showNotification('File saved successfully', 'success');
        } else {
            const error = await response.json();
            showNotification('Failed to save file: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to save file: ' + error.message, 'error');
    }
}

function closeEditor(modalId) {
    if (monacoEditor) {
        monacoEditor.dispose();
        monacoEditor = null;
    }
    currentEditingFile = null;
    closeModal(modalId);
}

// ============================================================================
// Search
// ============================================================================

async function handleQuickSearch(event) {
    const query = event.target.value.trim();
    
    if (query.length < 2) {
        if (state.currentView === 'files') {
            await loadFiles(state.currentPath);
            renderFiles();
        }
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/files/search?q=${encodeURIComponent(query)}`);
        if (response.ok) {
            const data = await response.json();
            state.files = data.results;
            renderFiles();
        }
    } catch (error) {
        console.error('Search failed:', error);
    }
}

function renderSearchView() {
    const contentArea = document.getElementById('contentArea');
    contentArea.innerHTML = `
        <div class="max-w-4xl mx-auto">
            <h2 class="text-3xl font-bold mb-6">Advanced Search</h2>
            
            <div class="bg-gray-800 p-6 rounded-lg space-y-4">
                <div>
                    <label class="block text-sm font-medium mb-2">Search Query</label>
                    <input type="text" id="advancedSearchQuery" class="input" placeholder="Search files...">
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium mb-2">File Type</label>
                        <select id="searchFileType" class="input">
                            <option value="">All Types</option>
                            <option value="text">Text</option>
                            <option value="code">Code</option>
                            <option value="pdf">PDF</option>
                            <option value="document">Document</option>
                            <option value="image">Image</option>
                        </select>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium mb-2">Tags</label>
                        <select id="searchTags" class="input" multiple>
                            ${state.tags.map(tag => `
                                <option value="${tag.name}">${tag.name}</option>
                            `).join('')}
                        </select>
                    </div>
                </div>
                
                <div>
                    <button class="btn btn-primary" onclick="performAdvancedSearch()">
                        <i class="fas fa-search"></i> Search
                    </button>
                </div>
            </div>
            
            <div id="searchResults" class="mt-6"></div>
        </div>
    `;
}

async function performAdvancedSearch() {
    const query = document.getElementById('advancedSearchQuery').value;
    const fileType = document.getElementById('searchFileType').value;
    const tags = Array.from(document.getElementById('searchTags').selectedOptions).map(o => o.value);
    
    let url = `${API_BASE}/files/search?q=${encodeURIComponent(query)}`;
    if (fileType) url += `&type=${fileType}`;
    tags.forEach(tag => url += `&tags=${encodeURIComponent(tag)}`);
    
    try {
        const response = await fetch(url);
        if (response.ok) {
            const data = await response.json();
            displaySearchResults(data.results);
        }
    } catch (error) {
        showNotification('Search failed: ' + error.message, 'error');
    }
}

function displaySearchResults(results) {
    const container = document.getElementById('searchResults');
    
    if (results.length === 0) {
        container.innerHTML = `
            <div class="text-center py-10 text-gray-400">
                <i class="fas fa-search text-5xl mb-4"></i>
                <p class="text-xl">No results found</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <h3 class="text-xl font-bold mb-4">${results.length} Results</h3>
        <div class="space-y-2">
            ${results.map(file => `
                <div class="bg-gray-800 p-4 rounded-lg flex items-center justify-between hover:bg-gray-700 cursor-pointer"
                     onclick="navigateToFile('${file.path}')">
                    <div class="flex items-center gap-3">
                        <div class="text-2xl">${getFileIcon(file)}</div>
                        <div>
                            <div class="font-medium">${escapeHtml(file.name)}</div>
                            <div class="text-sm text-gray-400">${file.path}</div>
                        </div>
                    </div>
                    <div class="text-sm text-gray-400">${file.file_type}</div>
                </div>
            `).join('')}
        </div>
    `;
}

async function navigateToFile(filePath) {
    const pathParts = filePath.split('/');
    pathParts.pop(); // Remove filename
    const dirPath = pathParts.join('/') || '/';
    
    state.currentView = 'files';
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.querySelector('[data-view="files"]').classList.add('active');
    
    await loadFiles(dirPath);
    renderFiles();
}

console.log('ML Filesystem JavaScript - Part 1 Loaded');
