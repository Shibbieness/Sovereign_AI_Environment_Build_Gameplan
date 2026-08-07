"""
ML Filesystem v1.8 - Main Application Entry Point

Initializes and runs the complete system:
- Database
- ML models
- Web API
- System tray (if enabled)
- External API (if enabled)
"""

import sys
import os
from pathlib import Path

# Add project root (sovereign_py/, parent of entry/) to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Must run before any ml./api./coding./vm./filesystem./models import: installs
# the sys.modules aliases those old import paths resolve through.
import core.module_path_bridge  # noqa: E402,F401

from core.config import Config
from core.database import db
from ml.model_manager import MLModelManager
from ml.local_backend import LocalMLBackend
from ml.training_blocks import TrainingBlockManager
from api.internal_api import create_app


def initialize_system():
    """Initialize the complete system."""
    print("\n" + "="*60)
    print("ML Filesystem v1.8 Professional - Initializing")
    print("="*60 + "\n")
    
    # Print configuration
    Config.print_config()
    
    # Step 1: Initialize database
    print("1. Initializing database...")
    db.init_db()
    
    # Step 2: Check ML models
    print("\n2. Checking ML models...")
    model_manager = MLModelManager()
    model_info = model_manager.get_model_info()
    
    print(f"   Profile: {model_info['profile']}")
    print(f"   Total size: {model_info['total_size_mb']}MB")
    print(f"   Downloaded: {model_info['downloaded_size_mb']}MB")
    
    if not model_info['download_complete']:
        print("\n   ⚠️  Models not fully downloaded!")
        print("   Run the following to download models:")
        print(f"   python -c 'from ml.model_manager import MLModelManager; MLModelManager().download_models()'")
        
        response = input("\n   Download now? (y/n): ")
        if response.lower() == 'y':
            print("\n   Downloading models...")
            try:
                model_manager.download_models()
            except Exception as e:
                print(f"   ✗ Download failed: {e}")
                print("   You can continue without models, but ML features will be limited.")
        else:
            print("   Continuing without full ML capabilities...")
    else:
        print("   ✓ All models downloaded")
    
    # Step 3: Initialize ML backend
    print("\n3. Initializing ML backend...")
    try:
        local_ml = LocalMLBackend(model_manager)
        capabilities = local_ml.get_capabilities()
        print(f"   ✓ ML backend ready")
        print(f"   Capabilities: {', '.join([k for k, v in capabilities.items() if v])}")
    except Exception as e:
        print(f"   ⚠️  ML backend initialization failed: {e}")
        print("   Some features may not work")
        local_ml = None
    
    # Step 4: Initialize training block manager
    print("\n4. Initializing training blocks...")
    training_block_manager = TrainingBlockManager(local_ml)
    print("   ✓ Training blocks ready")
    
    print("\n" + "="*60)
    print("✓ System initialized successfully!")
    print("="*60 + "\n")
    
    return {
        'model_manager': model_manager,
        'local_ml': local_ml,
        'training_block_manager': training_block_manager
    }


def run_web_interface():
    """Run the web interface."""
    print("Starting web interface...")
    print(f"Server will run on http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    print("\nPress Ctrl+C to stop\n")
    
    # Create Flask app
    app = create_app()
    
    # Run
    from flask_socketio import SocketIO
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    socketio.run(
        app,
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.DEBUG,
        use_reloader=False  # Disable reloader to avoid double initialization
    )


def main():
    """Main entry point."""
    try:
        # Initialize system
        components = initialize_system()
        
        # Run web interface
        run_web_interface()
        
    except KeyboardInterrupt:
        print("\n\n✓ Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
