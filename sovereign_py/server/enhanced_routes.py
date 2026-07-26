"""
Enhanced API Routes for ML Filesystem v1.8+

New endpoints for:
- API Connection Management
- Integrated Coding IDE
- VM Management
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps

from api.api_manager import APIConnectionManager
from coding.ide_manager import CodingIDEManager
from vm.vm_manager import VMManager


# Create blueprints
api_connections_bp = Blueprint('api_connections', __name__, url_prefix='/api/connections')
coding_bp = Blueprint('coding', __name__, url_prefix='/api/coding')
vm_bp = Blueprint('vms', __name__, url_prefix='/api/vms')


# Initialize managers
api_manager = APIConnectionManager()
ide_manager = CodingIDEManager()
vm_manager = VMManager()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# API CONNECTION ROUTES
# ============================================================

@api_connections_bp.route('', methods=['GET'])
@login_required
def list_api_connections():
    """List all API connections."""
    service_type = request.args.get('service_type')
    enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
    
    connections = api_manager.list_connections(
        owner_id=session['user_id'],
        service_type=service_type,
        enabled_only=enabled_only
    )
    
    return jsonify([conn.to_dict_safe() for conn in connections])


@api_connections_bp.route('', methods=['POST'])
@login_required
def create_api_connection():
    """Create a new API connection."""
    data = request.json
    
    try:
        connection = api_manager.create_connection(
            name=data['name'],
            service_type=data['service_type'],
            provider=data['provider'],
            api_key=data['api_key'],
            owner_id=session['user_id'],
            description=data.get('description'),
            base_url=data.get('base_url'),
            model_name=data.get('model_name'),
            config=data.get('config')
        )
        return jsonify(connection.to_dict_safe()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@api_connections_bp.route('/<int:connection_id>', methods=['GET'])
@login_required
def get_api_connection(connection_id):
    """Get API connection details."""
    connection = api_manager.get_connection(connection_id)
    if connection:
        return jsonify(connection.to_dict_safe())
    return jsonify({'error': 'Connection not found'}), 404


@api_connections_bp.route('/<int:connection_id>', methods=['PUT'])
@login_required
def update_api_connection(connection_id):
    """Update API connection."""
    data = request.json
    
    connection = api_manager.update_connection(
        connection_id,
        name=data.get('name'),
        description=data.get('description'),
        api_key=data.get('api_key'),
        base_url=data.get('base_url'),
        model_name=data.get('model_name'),
        config=data.get('config')
    )
    
    if connection:
        return jsonify(connection.to_dict_safe())
    return jsonify({'error': 'Connection not found'}), 404


@api_connections_bp.route('/<int:connection_id>', methods=['DELETE'])
@login_required
def delete_api_connection(connection_id):
    """Delete API connection."""
    success = api_manager.delete_connection(connection_id)
    return jsonify({'success': success})


@api_connections_bp.route('/<int:connection_id>/toggle', methods=['POST'])
@login_required
def toggle_api_connection(connection_id):
    """Enable/disable API connection."""
    data = request.json
    enabled = api_manager.toggle_connection(connection_id, data.get('enabled'))
    return jsonify({'enabled': enabled})


@api_connections_bp.route('/<int:connection_id>/test', methods=['POST'])
@login_required
def test_api_connection(connection_id):
    """Test API connection."""
    result = api_manager.test_connection(connection_id)
    return jsonify(result)


@api_connections_bp.route('/<int:connection_id>/usage', methods=['GET'])
@login_required
def get_connection_usage(connection_id):
    """Get usage statistics for connection."""
    stats = api_manager.get_usage_stats(connection_id)
    return jsonify(stats)


# ============================================================
# CODING IDE ROUTES
# ============================================================

@coding_bp.route('/projects', methods=['GET'])
@login_required
def list_coding_projects():
    """List all coding projects."""
    language = request.args.get('language')
    projects = ide_manager.list_projects(
        owner_id=session['user_id'],
        language=language
    )
    return jsonify([p.to_dict() for p in projects])


@coding_bp.route('/projects', methods=['POST'])
@login_required
def create_coding_project():
    """Create a new coding project."""
    data = request.json
    
    try:
        project = ide_manager.create_project(
            name=data['name'],
            language=data['language'],
            owner_id=session['user_id'],
            description=data.get('description'),
            framework=data.get('framework'),
            template=data.get('template')
        )
        return jsonify(project.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@coding_bp.route('/projects/<int:project_id>', methods=['GET'])
@login_required
def get_coding_project(project_id):
    """Get project details."""
    project = ide_manager.get_project(project_id)
    if project:
        return jsonify(project.to_dict())
    return jsonify({'error': 'Project not found'}), 404


@coding_bp.route('/projects/<int:project_id>/files', methods=['GET'])
@login_required
def list_project_files(project_id):
    """List files in project."""
    files = ide_manager.get_project_files(project_id)
    return jsonify(files)


@coding_bp.route('/projects/<int:project_id>/files', methods=['POST'])
@login_required
def create_project_file(project_id):
    """Create/update file in project."""
    data = request.json
    
    success = ide_manager.write_file(
        project_id,
        data['path'],
        data['content']
    )
    
    return jsonify({'success': success})


@coding_bp.route('/projects/<int:project_id>/files/<path:file_path>', methods=['GET'])
@login_required
def read_project_file(project_id, file_path):
    """Read file from project."""
    content = ide_manager.read_file(project_id, file_path)
    if content is not None:
        return jsonify({'content': content})
    return jsonify({'error': 'File not found'}), 404


@coding_bp.route('/projects/<int:project_id>/execute', methods=['POST'])
@login_required
def execute_project_code(project_id):
    """Execute code in project."""
    data = request.json
    
    try:
        execution = ide_manager.execute_code(
            project_id,
            data['file_path'],
            args=data.get('args', []),
            env_vars=data.get('env_vars'),
            timeout=data.get('timeout', 30)
        )
        return jsonify(execution.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@coding_bp.route('/projects/<int:project_id>/executions', methods=['GET'])
@login_required
def list_project_executions(project_id):
    """Get execution history."""
    limit = int(request.args.get('limit', 20))
    executions = ide_manager.get_execution_history(project_id, limit)
    return jsonify([e.to_dict() for e in executions])


@coding_bp.route('/projects/<int:project_id>/format', methods=['POST'])
@login_required
def format_project_file(project_id):
    """Format code file."""
    data = request.json
    
    formatted = ide_manager.format_code(project_id, data['file_path'])
    if formatted:
        return jsonify({'content': formatted})
    return jsonify({'error': 'Formatting failed'}), 400


@coding_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@login_required
def delete_coding_project(project_id):
    """Delete project."""
    success = ide_manager.delete_project(project_id)
    return jsonify({'success': success})


@coding_bp.route('/languages', methods=['GET'])
@login_required
def get_supported_languages():
    """Get list of supported languages."""
    return jsonify(list(ide_manager.SUPPORTED_LANGUAGES.keys()))


# ============================================================
# VM MANAGEMENT ROUTES
# ============================================================

@vm_bp.route('', methods=['GET'])
@login_required
def list_vms():
    """List all VMs."""
    vm_type = request.args.get('vm_type')
    vms = vm_manager.list_vms(
        owner_id=session['user_id'],
        vm_type=vm_type
    )
    return jsonify([vm.to_dict() for vm in vms])


@vm_bp.route('', methods=['POST'])
@login_required
def create_vm():
    """Create a new VM."""
    data = request.json
    
    try:
        vm = vm_manager.create_vm(
            name=data['name'],
            vm_type=data['vm_type'],
            image=data['image'],
            owner_id=session['user_id'],
            description=data.get('description'),
            os_type=data.get('os_type', 'linux'),
            cpu_cores=data.get('cpu_cores', 2),
            memory_mb=data.get('memory_mb', 2048),
            disk_gb=data.get('disk_gb', 20),
            network_mode=data.get('network_mode', 'bridge'),
            port_mappings=data.get('port_mappings'),
            config=data.get('config')
        )
        return jsonify(vm.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@vm_bp.route('/<int:vm_id>', methods=['GET'])
@login_required
def get_vm(vm_id):
    """Get VM details and status."""
    status = vm_manager.get_vm_status(vm_id)
    return jsonify(status)


@vm_bp.route('/<int:vm_id>/start', methods=['POST'])
@login_required
def start_vm(vm_id):
    """Start a VM."""
    result = vm_manager.start_vm(vm_id)
    return jsonify(result)


@vm_bp.route('/<int:vm_id>/stop', methods=['POST'])
@login_required
def stop_vm(vm_id):
    """Stop a VM."""
    result = vm_manager.stop_vm(vm_id)
    return jsonify(result)


@vm_bp.route('/<int:vm_id>/snapshots', methods=['GET'])
@login_required
def list_vm_snapshots(vm_id):
    """List VM snapshots."""
    snapshots = vm_manager.list_snapshots(vm_id)
    return jsonify([s.to_dict() for s in snapshots])


@vm_bp.route('/<int:vm_id>/snapshots', methods=['POST'])
@login_required
def create_vm_snapshot(vm_id):
    """Create VM snapshot."""
    data = request.json
    
    snapshot = vm_manager.create_snapshot(
        vm_id,
        data['name'],
        data.get('description')
    )
    
    if snapshot:
        return jsonify(snapshot.to_dict()), 201
    return jsonify({'error': 'Snapshot creation failed'}), 400


@vm_bp.route('/<int:vm_id>', methods=['DELETE'])
@login_required
def delete_vm(vm_id):
    """Delete a VM."""
    success = vm_manager.delete_vm(vm_id)
    return jsonify({'success': success})


# ============================================================
# ENHANCEMENTS ROUTES (auto-suggest, universal search, webhooks,
# project/VM integration, enhanced-agent configuration)
# ============================================================

enhancements_bp = Blueprint('enhancements', __name__, url_prefix='/api/enhancements')

_local_ml = None
_training_block_manager = None
_chroma_manager = None
_webhook_manager = None
_project_training = None
_vm_project = None


def _get_local_ml():
    global _local_ml
    if _local_ml is None:
        from ml.local_backend import LocalMLBackend
        _local_ml = LocalMLBackend()
    return _local_ml


def _get_training_block_manager():
    global _training_block_manager
    if _training_block_manager is None:
        from ml.training_blocks import TrainingBlockManager
        _training_block_manager = TrainingBlockManager(_get_local_ml())
    return _training_block_manager


def _get_chroma_manager():
    """Returns None if chromadb isn't installed; callers fall back gracefully."""
    global _chroma_manager
    if _chroma_manager is None:
        from ml.enhancements import ChromaDBManager
        from ml_runtime.graceful import MLBackendUnavailable
        try:
            _chroma_manager = ChromaDBManager()
        except MLBackendUnavailable:
            return None
    return _chroma_manager


def _get_webhook_manager():
    global _webhook_manager
    if _webhook_manager is None:
        from ml.enhancements import WebhookManager
        _webhook_manager = WebhookManager()
    return _webhook_manager


def _get_project_training():
    global _project_training
    if _project_training is None:
        from ml.enhancements import ProjectTrainingIntegration
        _project_training = ProjectTrainingIntegration()
    return _project_training


def _get_vm_project():
    global _vm_project
    if _vm_project is None:
        from ml.enhancements import VMProjectIntegration
        _vm_project = VMProjectIntegration()
    return _vm_project


@enhancements_bp.route('/suggest-blocks/<int:file_id>', methods=['GET'])
@login_required
def suggest_blocks(file_id):
    """Get training block suggestions for a file."""
    from ml.enhancements import BlockAutoSuggest

    threshold = float(request.args.get('threshold', 0.7))
    max_suggestions = int(request.args.get('max', 3))

    auto_suggest = BlockAutoSuggest(_get_local_ml(), _get_chroma_manager())
    suggestions = auto_suggest.suggest_blocks_for_file(file_id, threshold, max_suggestions)
    return jsonify(suggestions)


@enhancements_bp.route('/search', methods=['POST'])
@login_required
def universal_search():
    """Search across everything."""
    from ml.enhancements import UniversalSearch

    data = request.json
    query = data.get('query', '')
    limit = data.get('limit', 5)
    semantic = data.get('semantic', True)

    search = UniversalSearch(_get_local_ml(), _get_chroma_manager())
    results = search.search_all(query, limit_per_category=limit, semantic=semantic)
    return jsonify(results)


@enhancements_bp.route('/webhooks/<webhook_id>', methods=['POST'])
def webhook_handler(webhook_id):
    """Handle incoming webhooks."""
    payload = request.json
    result = _get_webhook_manager().handle_webhook(webhook_id, payload)
    return jsonify(result)


@enhancements_bp.route('/projects/<int:project_id>/add-to-block', methods=['POST'])
@login_required
def add_project_to_block(project_id):
    """Add coding project to training block."""
    data = request.json
    block_id = data.get('block_id')
    auto_sync = data.get('auto_sync', False)

    result = _get_project_training().add_project_to_block(
        project_id, block_id, auto_sync=auto_sync
    )
    return jsonify(result)


@enhancements_bp.route('/projects/<int:project_id>/assign-vm', methods=['POST'])
@login_required
def assign_vm_to_project(project_id):
    """Assign VM to coding project."""
    data = request.json
    vm_id = data.get('vm_id')
    auto_start = data.get('auto_start', True)

    result = _get_vm_project().assign_vm_to_project(
        project_id, vm_id, auto_start=auto_start
    )
    return jsonify(result)


@enhancements_bp.route('/agents/<int:agent_id>/configure', methods=['POST'])
@login_required
def configure_agent(agent_id):
    """Configure enhanced agent."""
    from ml.enhanced_agents import EnhancedAgent

    data = request.json
    agent = EnhancedAgent(agent_id=agent_id)

    if 'training_blocks' in data:
        agent.assign_training_blocks(
            data['training_blocks'],
            enforce=data.get('enforce_binding', True)
        )

    if 'api_connections' in data:
        agent.assign_api_connections(data['api_connections'])

    if 'model_config' in data:
        mc = data['model_config']
        agent.set_model_config(
            primary_model=mc.get('primary_model'),
            fallback_models=mc.get('fallback_models', []),
            execution_mode=mc.get('execution_mode', 'single'),
            enable_parallel=mc.get('enable_parallel', False)
        )

    agent.save_to_db()
    return jsonify(agent.get_stats())


@enhancements_bp.route('/agents/<int:agent_id>/query', methods=['POST'])
@login_required
def query_enhanced_agent(agent_id):
    """Query enhanced agent with full control."""
    from ml.enhanced_agents import EnhancedAgent

    data = request.json
    agent = EnhancedAgent(
        agent_id=agent_id,
        local_ml=_get_local_ml(),
        training_block_manager=_get_training_block_manager()
    )

    result = agent.query(
        question=data.get('question'),
        use_functional_blocks=data.get('use_functional_blocks', True),
        force_model=data.get('force_model')
    )
    return jsonify(result)


@enhancements_bp.route('/agents/<int:agent_id>/functional-blocks', methods=['POST'])
@login_required
def create_functional_block(agent_id):
    """Create functional training block (proficiency domain)."""
    from ml.enhanced_agents import EnhancedAgent

    data = request.json
    agent = EnhancedAgent(
        agent_id=agent_id,
        local_ml=_get_local_ml(),
        training_block_manager=_get_training_block_manager()
    )

    func_block = agent.create_functional_block(
        name=data['name'],
        domain=data['domain'],
        source_block_ids=data['source_blocks']
    )
    return jsonify(func_block.to_dict())


# Export blueprints
def register_enhanced_routes(app):
    """Register all enhanced route blueprints."""
    app.register_blueprint(api_connections_bp)
    app.register_blueprint(coding_bp)
    app.register_blueprint(vm_bp)
    app.register_blueprint(enhancements_bp)
