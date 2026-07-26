/**
 * ML Filesystem - Main JavaScript Application
 * Part 2: ML Agents, File Chains, Profile, and Activity
 */

// ============================================================================
// ML Agents View
// ============================================================================

function renderAgentsView() {
    const contentArea = document.getElementById('contentArea');
    
    contentArea.innerHTML = `
        <div>
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-3xl font-bold">ML Agents</h2>
                <button class="btn btn-primary" onclick="showCreateAgentModal()">
                    <i class="fas fa-plus"></i> Create Agent
                </button>
            </div>
            
            ${state.agents.length === 0 ? `
                <div class="text-center py-20 text-gray-400">
                    <i class="fas fa-robot text-6xl mb-4"></i>
                    <p class="text-xl">No ML agents created yet</p>
                    <p class="mt-2">Create an agent to start organizing and learning from your files</p>
                </div>
            ` : `
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    ${state.agents.map(agent => renderAgentCard(agent)).join('')}
                </div>
            `}
        </div>
    `;
}

function renderAgentCard(agent) {
    const typeIcons = {
        'organizer': 'fa-folder-tree',
        'learner': 'fa-graduation-cap',
        'analyzer': 'fa-chart-line',
        'custom': 'fa-robot'
    };
    
    const typeColors = {
        'organizer': '#3b82f6',
        'learner': '#10b981',
        'analyzer': '#f59e0b',
        'custom': '#8b5cf6'
    };
    
    return `
        <div class="agent-card">
            <div class="flex items-start justify-between mb-4">
                <div class="flex items-center gap-3">
                    <div class="text-4xl" style="color: ${typeColors[agent.agent_type]};">
                        <i class="fas ${typeIcons[agent.agent_type]}"></i>
                    </div>
                    <div>
                        <h3 class="text-xl font-bold">${escapeHtml(agent.name)}</h3>
                        <p class="text-sm text-gray-400">${agent.agent_type}</p>
                    </div>
                </div>
                <div>
                    ${agent.is_active ? 
                        '<span class="tag" style="background: #10b981;">Active</span>' : 
                        '<span class="tag" style="background: #64748b;">Inactive</span>'
                    }
                </div>
            </div>
            
            <p class="text-gray-300 mb-4">${escapeHtml(agent.description)}</p>
            
            <div class="grid grid-cols-3 gap-4 mb-4 text-center">
                <div>
                    <div class="text-2xl font-bold text-blue-400">${agent.interactions_count}</div>
                    <div class="text-xs text-gray-400">Interactions</div>
                </div>
                <div>
                    <div class="text-2xl font-bold text-green-400">${agent.files_processed}</div>
                    <div class="text-xs text-gray-400">Files Processed</div>
                </div>
                <div>
                    <div class="text-2xl font-bold text-purple-400">${agent.files.length}</div>
                    <div class="text-xs text-gray-400">Assigned Files</div>
                </div>
            </div>
            
            <div class="flex gap-2">
                ${agent.agent_type === 'organizer' ? `
                    <button class="btn btn-primary flex-1" onclick="showOrganizeFilesModal(${agent.id})">
                        <i class="fas fa-folder-tree"></i> Organize
                    </button>
                ` : ''}
                
                ${agent.agent_type === 'learner' ? `
                    <button class="btn btn-success flex-1" onclick="showLearnFilesModal(${agent.id})">
                        <i class="fas fa-graduation-cap"></i> Learn
                    </button>
                    <button class="btn btn-primary flex-1" onclick="showQueryAgentModal(${agent.id})">
                        <i class="fas fa-question-circle"></i> Query
                    </button>
                ` : ''}
                
                ${agent.agent_type === 'analyzer' ? `
                    <button class="btn btn-primary flex-1" onclick="showAnalyzeModal(${agent.id})">
                        <i class="fas fa-chart-line"></i> Analyze
                    </button>
                ` : ''}
                
                <button class="btn btn-secondary" onclick="showAgentDetails(${agent.id})">
                    <i class="fas fa-info-circle"></i>
                </button>
            </div>
        </div>
    `;
}

function showCreateAgentModal() {
    const modalId = showModal('Create ML Agent', `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-2">Agent Name</label>
                <input type="text" id="agentName" class="input" placeholder="My Agent">
            </div>
            
            <div>
                <label class="block text-sm font-medium mb-2">Agent Type</label>
                <select id="agentType" class="input">
                    <option value="organizer">Organizer - Organize and categorize files</option>
                    <option value="learner">Learner - Learn from files and answer questions</option>
                    <option value="analyzer">Analyzer - Analyze file content and patterns</option>
                    <option value="custom">Custom - Define your own behavior</option>
                </select>
            </div>
            
            <div>
                <label class="block text-sm font-medium mb-2">Description</label>
                <textarea id="agentDescription" class="input" rows="3" placeholder="What does this agent do?"></textarea>
            </div>
            
            <div id="customPromptSection" style="display: none;">
                <label class="block text-sm font-medium mb-2">System Prompt</label>
                <textarea id="agentPrompt" class="input" rows="5" placeholder="Custom system prompt..."></textarea>
            </div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Create Agent',
            class: 'btn-primary',
            icon: 'fas fa-plus',
            onclick: `createAgent('${modalId}')`
        }
    ]);
    
    // Show custom prompt section for custom agents
    document.getElementById('agentType').addEventListener('change', (e) => {
        const section = document.getElementById('customPromptSection');
        section.style.display = e.target.value === 'custom' ? 'block' : 'none';
    });
}

async function createAgent(modalId) {
    const name = document.getElementById('agentName').value.trim();
    const type = document.getElementById('agentType').value;
    const description = document.getElementById('agentDescription').value.trim();
    const prompt = document.getElementById('agentPrompt')?.value.trim();
    
    if (!name) {
        showNotification('Please enter an agent name', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/agents`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                agent_type: type,
                description,
                system_prompt: prompt || undefined
            })
        });
        
        if (response.ok) {
            showNotification('Agent created successfully', 'success');
            closeModal(modalId);
            await loadAgents();
            renderAgentsView();
        } else {
            const error = await response.json();
            showNotification('Failed to create agent: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to create agent: ' + error.message, 'error');
    }
}

function showOrganizeFilesModal(agentId) {
    const modalId = showModal('Organize Files', `
        <div class="space-y-4">
            <p class="text-gray-300">Select files to organize with this agent.</p>
            
            <div>
                <label class="block text-sm font-medium mb-2">Select Files</label>
                <div class="max-h-64 overflow-y-auto space-y-2 bg-gray-900 p-4 rounded">
                    ${state.files.filter(f => !f.is_directory).map(file => `
                        <label class="flex items-center gap-2 cursor-pointer hover:bg-gray-800 p-2 rounded">
                            <input type="checkbox" class="organize-file-checkbox" value="${file.id}">
                            <span>${escapeHtml(file.name)}</span>
                        </label>
                    `).join('')}
                </div>
            </div>
            
            <div id="organizeResults" class="hidden">
                <div class="bg-gray-900 p-4 rounded">
                    <div class="flex items-center gap-2 mb-2">
                        <div class="spinner"></div>
                        <span>Analyzing files...</span>
                    </div>
                </div>
            </div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Organize',
            class: 'btn-primary',
            icon: 'fas fa-folder-tree',
            onclick: `organizeFiles(${agentId}, '${modalId}')`
        }
    ]);
}

async function organizeFiles(agentId, modalId) {
    const checkboxes = document.querySelectorAll('.organize-file-checkbox:checked');
    const fileIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    if (fileIds.length === 0) {
        showNotification('Please select files to organize', 'error');
        return;
    }
    
    const resultsDiv = document.getElementById('organizeResults');
    resultsDiv.classList.remove('hidden');
    
    try {
        const response = await fetch(`${API_BASE}/agents/${agentId}/organize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_ids: fileIds })
        });
        
        if (response.ok) {
            const result = await response.json();
            displayOrganizationResults(result);
        } else {
            const error = await response.json();
            showNotification('Organization failed: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Organization failed: ' + error.message, 'error');
    }
}

function displayOrganizationResults(result) {
    const resultsDiv = document.getElementById('organizeResults');
    
    resultsDiv.innerHTML = `
        <div class="bg-gray-900 p-4 rounded space-y-4">
            <h3 class="text-lg font-bold text-green-400">
                <i class="fas fa-check-circle"></i> Organization Complete
            </h3>
            
            ${result.raw_response ? `
                <div class="text-gray-300 whitespace-pre-wrap">${escapeHtml(result.raw_response)}</div>
            ` : `
                ${result.folder_structure ? `
                    <div>
                        <h4 class="font-medium mb-2">Suggested Folder Structure:</h4>
                        <pre class="bg-gray-800 p-3 rounded text-sm">${JSON.stringify(result.folder_structure, null, 2)}</pre>
                    </div>
                ` : ''}
                
                ${result.insights ? `
                    <div>
                        <h4 class="font-medium mb-2">Insights:</h4>
                        <ul class="list-disc list-inside space-y-1 text-gray-300">
                            ${result.insights.map(insight => `<li>${escapeHtml(insight)}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            `}
        </div>
    `;
}

function showLearnFilesModal(agentId) {
    const modalId = showModal('Learn from Files', `
        <div class="space-y-4">
            <p class="text-gray-300">Select files for the agent to learn from.</p>
            
            <div>
                <label class="block text-sm font-medium mb-2">Select Files</label>
                <div class="max-h-64 overflow-y-auto space-y-2 bg-gray-900 p-4 rounded">
                    ${state.files.filter(f => !f.is_directory).map(file => `
                        <label class="flex items-center gap-2 cursor-pointer hover:bg-gray-800 p-2 rounded">
                            <input type="checkbox" class="learn-file-checkbox" value="${file.id}" 
                                   ${file.is_marked_for_learning ? 'checked' : ''}>
                            <span>${escapeHtml(file.name)}</span>
                            ${file.is_marked_for_learning ? '<i class="fas fa-graduation-cap text-yellow-400"></i>' : ''}
                        </label>
                    `).join('')}
                </div>
            </div>
            
            <div id="learnResults" class="hidden"></div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Start Learning',
            class: 'btn-success',
            icon: 'fas fa-graduation-cap',
            onclick: `learnFromFiles(${agentId}, '${modalId}')`
        }
    ]);
}

async function learnFromFiles(agentId, modalId) {
    const checkboxes = document.querySelectorAll('.learn-file-checkbox:checked');
    const fileIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    if (fileIds.length === 0) {
        showNotification('Please select files to learn from', 'error');
        return;
    }
    
    const resultsDiv = document.getElementById('learnResults');
    resultsDiv.classList.remove('hidden');
    resultsDiv.innerHTML = `
        <div class="bg-gray-900 p-4 rounded">
            <div class="flex items-center gap-2">
                <div class="spinner"></div>
                <span>Learning from files...</span>
            </div>
        </div>
    `;
    
    try {
        const response = await fetch(`${API_BASE}/agents/${agentId}/learn`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_ids: fileIds })
        });
        
        if (response.ok) {
            const result = await response.json();
            resultsDiv.innerHTML = `
                <div class="bg-gray-900 p-4 rounded">
                    <h3 class="text-lg font-bold text-green-400 mb-2">
                        <i class="fas fa-check-circle"></i> Learning Complete
                    </h3>
                    <p class="text-gray-300">Processed ${result.files_processed} files</p>
                </div>
            `;
            showNotification('Learning completed successfully', 'success');
        } else {
            const error = await response.json();
            showNotification('Learning failed: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Learning failed: ' + error.message, 'error');
    }
}

function showQueryAgentModal(agentId) {
    const agent = state.agents.find(a => a.id === agentId);
    
    const modalId = showModal(`Query: ${agent.name}`, `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-2">Your Question</label>
                <textarea id="queryInput" class="input" rows="4" placeholder="Ask the agent about what it has learned..."></textarea>
            </div>
            
            <div id="queryResult" class="hidden"></div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Ask',
            class: 'btn-primary',
            icon: 'fas fa-question-circle',
            onclick: `queryAgent(${agentId}, '${modalId}')`
        }
    ]);
}

async function queryAgent(agentId, modalId) {
    const query = document.getElementById('queryInput').value.trim();
    
    if (!query) {
        showNotification('Please enter a question', 'error');
        return;
    }
    
    const resultDiv = document.getElementById('queryResult');
    resultDiv.classList.remove('hidden');
    resultDiv.innerHTML = `
        <div class="bg-gray-900 p-4 rounded">
            <div class="flex items-center gap-2">
                <div class="spinner"></div>
                <span>Thinking...</span>
            </div>
        </div>
    `;
    
    try {
        const response = await fetch(`${API_BASE}/agents/${agentId}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        
        if (response.ok) {
            const result = await response.json();
            resultDiv.innerHTML = `
                <div class="bg-gray-900 p-4 rounded space-y-3">
                    <div class="flex items-center gap-2 text-blue-400 font-medium">
                        <i class="fas fa-robot"></i>
                        <span>${escapeHtml(result.agent_name)}</span>
                    </div>
                    <div class="text-gray-300 whitespace-pre-wrap">${escapeHtml(result.answer)}</div>
                    
                    ${result.sources && result.sources.length > 0 ? `
                        <div class="border-t border-gray-700 pt-3 mt-3">
                            <div class="text-sm font-medium mb-2">Sources:</div>
                            <div class="space-y-1">
                                ${result.sources.map(source => `
                                    <div class="text-xs text-gray-400">
                                        <i class="fas fa-file"></i> ${escapeHtml(source.file_name)}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        } else {
            const error = await response.json();
            showNotification('Query failed: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Query failed: ' + error.message, 'error');
    }
}

// ============================================================================
// File Chains View
// ============================================================================

function renderChainsView() {
    const contentArea = document.getElementById('contentArea');
    
    contentArea.innerHTML = `
        <div>
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-3xl font-bold">File Chains</h2>
                <button class="btn btn-primary" onclick="showCreateChainModal()">
                    <i class="fas fa-plus"></i> Create Chain
                </button>
            </div>
            
            ${state.chains.length === 0 ? `
                <div class="text-center py-20 text-gray-400">
                    <i class="fas fa-link text-6xl mb-4"></i>
                    <p class="text-xl">No file chains created yet</p>
                    <p class="mt-2">Create chains to organize related files together</p>
                </div>
            ` : `
                <div class="space-y-4">
                    ${state.chains.map(chain => renderChainCard(chain)).join('')}
                </div>
            `}
        </div>
    `;
}

function renderChainCard(chain) {
    return `
        <div class="bg-gray-800 p-6 rounded-lg">
            <div class="flex items-start justify-between mb-4">
                <div>
                    <h3 class="text-xl font-bold mb-2">${escapeHtml(chain.name)}</h3>
                    <p class="text-gray-400">${escapeHtml(chain.description)}</p>
                </div>
                <div class="flex gap-2">
                    <button class="btn btn-primary" onclick="showChainDetails(${chain.id})">
                        <i class="fas fa-eye"></i> View
                    </button>
                    <button class="btn btn-secondary" onclick="showEditChainModal(${chain.id})">
                        <i class="fas fa-edit"></i>
                    </button>
                </div>
            </div>
            
            <div class="flex items-center gap-6 text-sm text-gray-400">
                <div>
                    <i class="fas fa-file"></i> ${chain.files.length} files
                </div>
                <div>
                    <i class="fas fa-robot"></i> ${chain.ml_agents.length} agents
                </div>
                <div>
                    <i class="fas fa-clock"></i> ${formatDate(chain.modified_at)}
                </div>
            </div>
        </div>
    `;
}

function showCreateChainModal() {
    const modalId = showModal('Create File Chain', `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-2">Chain Name</label>
                <input type="text" id="chainName" class="input" placeholder="My File Chain">
            </div>
            
            <div>
                <label class="block text-sm font-medium mb-2">Description</label>
                <textarea id="chainDescription" class="input" rows="3" placeholder="What is this chain for?"></textarea>
            </div>
            
            <div>
                <label class="block text-sm font-medium mb-2">Select Files</label>
                <div class="max-h-48 overflow-y-auto space-y-2 bg-gray-900 p-4 rounded">
                    ${state.files.filter(f => !f.is_directory).map(file => `
                        <label class="flex items-center gap-2 cursor-pointer hover:bg-gray-800 p-2 rounded">
                            <input type="checkbox" class="chain-file-checkbox" value="${file.id}">
                            <span>${escapeHtml(file.name)}</span>
                        </label>
                    `).join('')}
                </div>
            </div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Create Chain',
            class: 'btn-primary',
            icon: 'fas fa-plus',
            onclick: `createChain('${modalId}')`
        }
    ]);
}

async function createChain(modalId) {
    const name = document.getElementById('chainName').value.trim();
    const description = document.getElementById('chainDescription').value.trim();
    const checkboxes = document.querySelectorAll('.chain-file-checkbox:checked');
    const fileIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    if (!name) {
        showNotification('Please enter a chain name', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/chains`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, file_ids: fileIds })
        });
        
        if (response.ok) {
            showNotification('Chain created successfully', 'success');
            closeModal(modalId);
            await loadChains();
            renderChainsView();
        } else {
            const error = await response.json();
            showNotification('Failed to create chain: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to create chain: ' + error.message, 'error');
    }
}

// ============================================================================
// Profile View
// ============================================================================

function renderProfileView() {
    const contentArea = document.getElementById('contentArea');
    
    contentArea.innerHTML = `
        <div class="max-w-4xl mx-auto">
            <h2 class="text-3xl font-bold mb-6">User Profile</h2>
            
            <div class="profile-header">
                <div class="avatar">
                    ${state.user.avatar_url ? 
                        `<img src="${state.user.avatar_url}" alt="Avatar" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;">` :
                        `<i class="fas fa-user"></i>`
                    }
                </div>
                <div class="flex-1">
                    <h3 class="text-2xl font-bold">${escapeHtml(state.user.display_name || state.user.username)}</h3>
                    <p class="text-gray-400">@${escapeHtml(state.user.username)}</p>
                    <p class="text-gray-400">${escapeHtml(state.user.email)}</p>
                    ${state.user.bio ? `<p class="mt-2 text-gray-300">${escapeHtml(state.user.bio)}</p>` : ''}
                </div>
                <button class="btn btn-primary" onclick="showEditProfileModal()">
                    <i class="fas fa-edit"></i> Edit Profile
                </button>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div class="bg-gray-800 p-6 rounded-lg text-center">
                    <div class="text-3xl font-bold text-blue-400">${state.files.length}</div>
                    <div class="text-gray-400">Files</div>
                </div>
                <div class="bg-gray-800 p-6 rounded-lg text-center">
                    <div class="text-3xl font-bold text-green-400">${state.agents.length}</div>
                    <div class="text-gray-400">ML Agents</div>
                </div>
                <div class="bg-gray-800 p-6 rounded-lg text-center">
                    <div class="text-3xl font-bold text-purple-400">${state.chains.length}</div>
                    <div class="text-gray-400">File Chains</div>
                </div>
            </div>
            
            <div class="bg-gray-800 p-6 rounded-lg">
                <h3 class="text-xl font-bold mb-4">Preferences</h3>
                <div class="space-y-4">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="font-medium">Theme</div>
                            <div class="text-sm text-gray-400">Choose your preferred theme</div>
                        </div>
                        <select class="input" style="width: 150px;" onchange="updatePreference('theme', this.value)">
                            <option value="dark" ${state.user.preferences?.theme === 'dark' ? 'selected' : ''}>Dark</option>
                            <option value="light" ${state.user.preferences?.theme === 'light' ? 'selected' : ''}>Light</option>
                        </select>
                    </div>
                    
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="font-medium">Default View</div>
                            <div class="text-sm text-gray-400">Default file view mode</div>
                        </div>
                        <select class="input" style="width: 150px;" onchange="updatePreference('default_view', this.value)">
                            <option value="grid" ${state.user.preferences?.default_view === 'grid' ? 'selected' : ''}>Grid</option>
                            <option value="list" ${state.user.preferences?.default_view === 'list' ? 'selected' : ''}>List</option>
                        </select>
                    </div>
                    
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="font-medium">Auto Organize</div>
                            <div class="text-sm text-gray-400">Automatically organize new files</div>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" ${state.user.preferences?.auto_organize ? 'checked' : ''} 
                                   onchange="updatePreference('auto_organize', this.checked)" class="sr-only peer">
                            <div class="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                        </label>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function showEditProfileModal() {
    const modalId = showModal('Edit Profile', `
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-2">Display Name</label>
                <input type="text" id="displayName" class="input" value="${escapeHtml(state.user.display_name || '')}">
            </div>
            
            <div>
                <label class="block text-sm font-medium mb-2">Bio</label>
                <textarea id="bio" class="input" rows="3">${escapeHtml(state.user.bio || '')}</textarea>
            </div>
            
            <div>
                <label class="block text-sm font-medium mb-2">Avatar URL</label>
                <input type="text" id="avatarUrl" class="input" value="${escapeHtml(state.user.avatar_url || '')}">
            </div>
        </div>
    `, [
        {
            label: 'Cancel',
            class: 'btn-secondary',
            onclick: `closeModal('${modalId}')`
        },
        {
            label: 'Save',
            class: 'btn-success',
            icon: 'fas fa-save',
            onclick: `saveProfile('${modalId}')`
        }
    ]);
}

async function saveProfile(modalId) {
    const displayName = document.getElementById('displayName').value.trim();
    const bio = document.getElementById('bio').value.trim();
    const avatarUrl = document.getElementById('avatarUrl').value.trim();
    
    try {
        const response = await fetch(`${API_BASE}/profile`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                display_name: displayName,
                bio: bio,
                avatar_url: avatarUrl
            })
        });
        
        if (response.ok) {
            const updatedUser = await response.json();
            state.user = updatedUser;
            showNotification('Profile updated successfully', 'success');
            closeModal(modalId);
            renderProfileView();
        } else {
            const error = await response.json();
            showNotification('Failed to update profile: ' + error.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to update profile: ' + error.message, 'error');
    }
}

async function updatePreference(key, value) {
    try {
        const response = await fetch(`${API_BASE}/profile`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                preferences: {
                    ...state.user.preferences,
                    [key]: value
                }
            })
        });
        
        if (response.ok) {
            const updatedUser = await response.json();
            state.user = updatedUser;
            showNotification('Preference updated', 'success');
        }
    } catch (error) {
        console.error('Failed to update preference:', error);
    }
}

// ============================================================================
// Activity View
// ============================================================================

let activityLogs = [];

async function loadActivity() {
    try {
        const response = await fetch(`${API_BASE}/activity`);
        if (response.ok) {
            const data = await response.json();
            activityLogs = data.logs;
        }
    } catch (error) {
        console.error('Failed to load activity:', error);
    }
}

function renderActivityView() {
    const contentArea = document.getElementById('contentArea');
    
    contentArea.innerHTML = `
        <div class="max-w-4xl mx-auto">
            <h2 class="text-3xl font-bold mb-6">Activity Log</h2>
            
            ${activityLogs.length === 0 ? `
                <div class="text-center py-20 text-gray-400">
                    <i class="fas fa-history text-6xl mb-4"></i>
                    <p class="text-xl">No activity yet</p>
                </div>
            ` : `
                <div class="space-y-3">
                    ${activityLogs.map(log => `
                        <div class="bg-gray-800 p-4 rounded-lg flex items-center gap-4">
                            <div class="text-2xl">
                                ${getActivityIcon(log.action)}
                            </div>
                            <div class="flex-1">
                                <div class="font-medium">${formatActivityAction(log.action)}</div>
                                <div class="text-sm text-gray-400">${formatDate(log.timestamp)}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `}
        </div>
    `;
}

function getActivityIcon(action) {
    const icons = {
        'create_file': '<i class="fas fa-file-plus text-green-400"></i>',
        'update_file': '<i class="fas fa-file-edit text-blue-400"></i>',
        'delete_file': '<i class="fas fa-trash text-red-400"></i>',
        'create_directory': '<i class="fas fa-folder-plus text-green-400"></i>',
        'move_file': '<i class="fas fa-arrows-alt text-purple-400"></i>',
        'create_agent': '<i class="fas fa-robot text-blue-400"></i>',
        'organize_files': '<i class="fas fa-folder-tree text-yellow-400"></i>',
        'learn_from_files': '<i class="fas fa-graduation-cap text-green-400"></i>',
        'query_knowledge': '<i class="fas fa-question-circle text-blue-400"></i>'
    };
    return icons[action] || '<i class="fas fa-circle text-gray-400"></i>';
}

function formatActivityAction(action) {
    const actions = {
        'create_file': 'Created file',
        'update_file': 'Updated file',
        'delete_file': 'Deleted file',
        'create_directory': 'Created directory',
        'move_file': 'Moved file',
        'create_agent': 'Created ML agent',
        'organize_files': 'Organized files',
        'learn_from_files': 'Learned from files',
        'query_knowledge': 'Queried knowledge'
    };
    return actions[action] || action.replace(/_/g, ' ');
}

console.log('ML Filesystem JavaScript - Part 2 Loaded');
