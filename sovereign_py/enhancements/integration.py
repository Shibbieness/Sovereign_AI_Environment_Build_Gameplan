"""
Integration Layer for ML Filesystem v1.8+

Wires everything together:
- Fixes all imports
- Registers enhanced routes
- Initializes all managers
- Creates missing __init__.py files programmatically
"""

import sys
from pathlib import Path

# Add project root (sovereign_py/, parent of enhancements/) to path so
# core/ml_runtime/server/features/fs_engine resolve when this is run directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

import core.module_path_bridge  # noqa: E402,F401  installs the ml/api/coding/vm/filesystem/models aliases


def initialize_all_components():
    """
    Initialize all system components in correct order.

    Returns:
        Dict of all initialized managers
    """
    from ml.model_manager import MLModelManager
    from ml.local_backend import LocalMLBackend
    from ml.training_blocks import TrainingBlockManager
    from ml.enhanced_agents import EnhancedAgent
    from ml.enhancements import (
        ChromaDBManager,
        AgentBlockEnforcer,
        AgentAPIManager,
        BlockAutoSuggest,
        ProjectTrainingIntegration,
        VMProjectIntegration,
        WebhookManager,
        UniversalSearch
    )
    from api.api_manager import APIConnectionManager
    from coding.ide_manager import CodingIDEManager
    from vm.vm_manager import VMManager
    from filesystem.operations import SemanticFileSystem
    from filesystem.filechain import FileChainManager
    
    print("Initializing ML Filesystem v1.8+ components...")
    
    components = {}
    
    # Core ML components
    print("  → Model Manager")
    components['model_manager'] = MLModelManager()
    
    print("  → Local ML Backend")
    components['local_ml'] = LocalMLBackend(components['model_manager'])
    
    print("  → Training Block Manager")
    components['training_block_manager'] = TrainingBlockManager(components['local_ml'])
    
    # Enhanced components
    print("  → ChromaDB Manager")
    components['chromadb'] = ChromaDBManager()
    
    print("  → Agent Block Enforcer")
    components['agent_enforcer'] = AgentBlockEnforcer()
    
    print("  → Agent API Manager")
    components['agent_api_manager'] = AgentAPIManager()
    
    print("  → Block Auto-Suggest")
    components['auto_suggest'] = BlockAutoSuggest(
        components['local_ml'],
        components['chromadb']
    )
    
    print("  → Project-Training Integration")
    components['project_training'] = ProjectTrainingIntegration()
    
    print("  → VM-Project Integration")
    components['vm_project'] = VMProjectIntegration()
    
    print("  → Webhook Manager")
    components['webhook_manager'] = WebhookManager()
    
    print("  → Universal Search")
    components['universal_search'] = UniversalSearch(
        components['local_ml'],
        components['chromadb']
    )
    
    # API & External components
    print("  → API Connection Manager")
    components['api_manager'] = APIConnectionManager()
    
    print("  → Coding IDE Manager")
    components['ide_manager'] = CodingIDEManager()
    
    print("  → VM Manager")
    components['vm_manager'] = VMManager()
    
    # Filesystem components
    print("  → Semantic Filesystem")
    components['semantic_fs'] = SemanticFileSystem(components['local_ml'])
    
    print("  → FileChain Manager")
    components['filechain_manager'] = FileChainManager(components['local_ml'])
    
    print("✓ All components initialized\n")
    
    return components


def register_all_routes(app, components):
    """
    Register all API routes with the Flask app.

    The actual route definitions live in server/enhanced_routes.py
    (register_enhanced_routes) so there is exactly one implementation of
    each blueprint instead of two diverging copies.

    Args:
        app: Flask application
        components: Dict of initialized components (unused now that the
            enhancements blueprint builds its own managers lazily; kept
            for call-site compatibility)
    """
    from api.enhanced_routes import register_enhanced_routes

    print("Registering API routes...")
    register_enhanced_routes(app)
    print("  ✓ API Connections, Coding IDE, VM Management, Enhancement routes")
    print("✓ All routes registered\n")


def create_missing_init_files():
    """Create missing __init__.py files."""
    from pathlib import Path
    
    project_root = Path(__file__).parent
    directories = [
        'coding',
        'vm',
        'widgets',
        'workflows',
        'plugins/bundled'
    ]
    
    for directory in directories:
        init_file = project_root / directory / '__init__.py'
        if not init_file.exists():
            init_file.parent.mkdir(parents=True, exist_ok=True)
            init_file.write_text(f'"""{directory.replace("/", ".")} module"""\n')
            print(f"✓ Created {init_file}")


def update_database_with_enhanced_models():
    """Import enhanced models into main database."""
    from core.database import Base, db
    from core.enhanced_models import (
        APIConnection,
        CodingProject,
        CodeExecution,
        VMConfiguration,
        VMSnapshot
    )
    
    # Models are now imported, will be created when db.init_db() is called
    print("✓ Enhanced models imported")


def integration_check():
    """
    Run integration checks to ensure everything is wired correctly.
    
    Returns:
        Dict with status of each component
    """
    status = {
        'overall': 'checking',
        'components': {},
        'routes': {},
        'database': {},
        'errors': []
    }
    
    try:
        # Check components
        components = initialize_all_components()
        for name, component in components.items():
            status['components'][name] = 'initialized' if component else 'failed'
        
        # Check database
        from core.database import db
        try:
            db.init_db()
            status['database']['connection'] = 'success'
            status['database']['tables_created'] = True
        except Exception as e:
            status['database']['error'] = str(e)
            status['errors'].append(f"Database: {e}")
        
        # Check if all routes can be registered
        from flask import Flask
        test_app = Flask(__name__)
        try:
            register_all_routes(test_app, components)
            status['routes']['registration'] = 'success'
            status['routes']['count'] = len(test_app.url_map._rules)
        except Exception as e:
            status['routes']['error'] = str(e)
            status['errors'].append(f"Routes: {e}")
        
        # Overall status
        if not status['errors']:
            status['overall'] = 'success'
        else:
            status['overall'] = 'partial'
    
    except Exception as e:
        status['overall'] = 'failed'
        status['errors'].append(f"Critical: {e}")
    
    return status


if __name__ == '__main__':
    print("="*60)
    print("ML Filesystem v1.8+ Integration Check")
    print("="*60 + "\n")
    
    # Create missing files
    print("1. Creating missing __init__.py files...")
    create_missing_init_files()
    print()
    
    # Update database
    print("2. Importing enhanced models...")
    update_database_with_enhanced_models()
    print()
    
    # Run integration check
    print("3. Running integration check...")
    status = integration_check()
    print()
    
    # Print results
    print("="*60)
    print("INTEGRATION CHECK RESULTS")
    print("="*60)
    print(f"\nOverall Status: {status['overall'].upper()}")
    print(f"\nComponents: {len([v for v in status['components'].values() if v == 'initialized'])}/{len(status['components'])} initialized")
    print(f"Routes: {status['routes'].get('count', 0)} registered")
    print(f"Database: {status['database'].get('connection', 'unknown')}")
    
    if status['errors']:
        print(f"\n⚠️  Errors ({len(status['errors'])}):")
        for error in status['errors']:
            print(f"   - {error}")
    else:
        print("\n✓ No errors detected")
    
    print("\n" + "="*60)
