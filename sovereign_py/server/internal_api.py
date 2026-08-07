"""
Internal Flask API for ML Filesystem v1.8
Provides REST endpoints for web interface.
"""

from flask import Flask, request, jsonify, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from functools import wraps
import hashlib
from datetime import datetime

from core.config import Config
from core.database import db, User, File, FileChain, TrainingBlock, MLAgent
from filesystem.operations import SemanticFileSystem
from filesystem.filechain import FileChainManager
from ml.local_backend import LocalMLBackend
from ml.model_manager import MLModelManager
from ml.training_blocks import TrainingBlockManager
from ml.hybrid_agent import HybridMLAgent


# Global instances
model_manager = None
local_ml = None
semantic_fs = None
filechain_manager = None
training_block_manager = None


def create_app():
    """Create and configure Flask app."""
    global model_manager, local_ml, semantic_fs, filechain_manager, training_block_manager
    
    app = Flask(__name__,
                static_folder='../ui',
                template_folder='../ui')
    
    # Configuration
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE
    
    # CORS
    CORS(app)
    
    # Initialize components
    try:
        model_manager = MLModelManager()
        local_ml = LocalMLBackend(model_manager)

        # Vector store is optional (requires chromadb); degrade to
        # brute-force in-process semantic search when it isn't installed.
        chroma_manager = None
        try:
            from ml.enhancements import ChromaDBManager
            chroma_manager = ChromaDBManager()
        except Exception as chroma_err:
            print(f"  → Vector store unavailable, using in-process semantic search: {chroma_err}")

        semantic_fs = SemanticFileSystem(local_ml, chroma_manager=chroma_manager)
        filechain_manager = FileChainManager(local_ml)
        training_block_manager = TrainingBlockManager(local_ml)
    except Exception as e:
        print(f"⚠️  Warning: ML components not fully initialized: {e}")
    
    # Authentication decorator
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            return f(*args, **kwargs)
        return decorated_function
    
    # ============================================================
    # AUTHENTICATION ROUTES
    # ============================================================
    
    @app.route('/api/auth/login', methods=['POST'])
    def login():
        """User login."""
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        # Hash password
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Find user
        db_session = db.get_session()
        try:
            user = db_session.query(User).filter_by(
                username=username,
                password_hash=password_hash
            ).first()
            
            if user:
                session['user_id'] = user.id
                session['username'] = user.username
                user.last_login = datetime.utcnow()
                db_session.commit()
                
                return jsonify({
                    'success': True,
                    'user': user.to_dict()
                })
            else:
                return jsonify({'error': 'Invalid credentials'}), 401
        finally:
            db_session.close()
    
    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        """User logout."""
        session.clear()
        return jsonify({'success': True})
    
    @app.route('/api/auth/me', methods=['GET'])
    @login_required
    def get_current_user():
        """Get current user."""
        db_session = db.get_session()
        try:
            user = db_session.query(User).filter_by(id=session['user_id']).first()
            return jsonify(user.to_dict() if user else {})
        finally:
            db_session.close()
    
    # ============================================================
    # FILE ROUTES
    # ============================================================
    
    @app.route('/api/files', methods=['GET'])
    @login_required
    def list_files():
        """List all files."""
        path = request.args.get('path', '/')
        try:
            files = semantic_fs.list_directory(path)
            return jsonify(files)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @app.route('/api/files', methods=['POST'])
    @login_required
    def create_file():
        """Create a new file."""
        data = request.json
        try:
            file = semantic_fs.create_file(
                path=data['path'],
                content=data['content'],
                owner_id=session['user_id'],
                tags=data.get('tags', [])
            )
            return jsonify(file.to_dict()), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @app.route('/api/files/<int:file_id>', methods=['GET'])
    @login_required
    def get_file(file_id):
        """Get file details."""
        try:
            file = semantic_fs.read_file(file_id)
            return jsonify(file)
        except Exception as e:
            return jsonify({'error': str(e)}), 404
    
    @app.route('/api/files/<int:file_id>', methods=['PUT'])
    @login_required
    def update_file(file_id):
        """Update file content."""
        data = request.json
        try:
            file = semantic_fs.update_file(file_id, data['content'])
            return jsonify(file.to_dict())
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @app.route('/api/files/<int:file_id>', methods=['DELETE'])
    @login_required
    def delete_file(file_id):
        """Delete a file."""
        try:
            success = semantic_fs.delete_file(file_id)
            return jsonify({'success': success})
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @app.route('/api/files/search', methods=['POST'])
    @login_required
    def search_files():
        """Search files."""
        data = request.json
        try:
            results = semantic_fs.search_files(
                query=data['query'],
                semantic=data.get('semantic', True),
                owner_id=session['user_id'],
                file_type=data.get('file_type'),
                tags=data.get('tags'),
                limit=data.get('limit', 20)
            )
            return jsonify(results)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    # ============================================================
    # FILECHAIN ROUTES
    # ============================================================
    
    @app.route('/api/filechains', methods=['GET'])
    @login_required
    def list_filechains():
        """List all filechains."""
        chains = filechain_manager.list_chains(owner_id=session['user_id'])
        return jsonify(chains)
    
    @app.route('/api/filechains', methods=['POST'])
    @login_required
    def create_filechain():
        """Create a new filechain."""
        data = request.json
        try:
            chain = filechain_manager.create_chain(
                name=data['name'],
                description=data.get('description', ''),
                owner_id=session['user_id'],
                file_ids=data.get('file_ids', [])
            )
            return jsonify(chain.to_dict()), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @app.route('/api/filechains/<int:chain_id>', methods=['GET'])
    @login_required
    def get_filechain(chain_id):
        """Get filechain details."""
        chain = filechain_manager.get_chain(chain_id)
        if chain:
            return jsonify(chain)
        return jsonify({'error': 'Chain not found'}), 404
    
    @app.route('/api/filechains/<int:chain_id>/files', methods=['POST'])
    @login_required
    def add_file_to_chain(chain_id):
        """Add file to chain."""
        data = request.json
        success = filechain_manager.add_file(chain_id, data['file_id'])
        return jsonify({'success': success})
    
    @app.route('/api/filechains/<int:chain_id>/files/<int:file_id>', methods=['DELETE'])
    @login_required
    def remove_file_from_chain(chain_id, file_id):
        """Remove file from chain."""
        success = filechain_manager.remove_file(chain_id, file_id)
        return jsonify({'success': success})
    
    @app.route('/api/filechains/<int:chain_id>/query', methods=['POST'])
    @login_required
    def query_filechain(chain_id):
        """Query a filechain."""
        data = request.json
        result = filechain_manager.query_chain(chain_id, data['question'])
        return jsonify(result)
    
    # ============================================================
    # TRAINING BLOCK ROUTES ⭐ NEW
    # ============================================================
    
    @app.route('/api/training-blocks', methods=['GET'])
    @login_required
    def list_training_blocks():
        """List all training blocks."""
        blocks = training_block_manager.list_blocks(owner_id=session['user_id'])
        return jsonify([block.to_dict() for block in blocks])
    
    @app.route('/api/training-blocks', methods=['POST'])
    @login_required
    def create_training_block():
        """Create a new training block."""
        data = request.json
        try:
            block = training_block_manager.create_block(
                name=data['name'],
                description=data.get('description', ''),
                block_type=data.get('block_type', 'rote'),
                owner_id=session['user_id'],
                enabled=data.get('enabled', True)
            )
            return jsonify(block.to_dict()), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @app.route('/api/training-blocks/<int:block_id>', methods=['GET'])
    @login_required
    def get_training_block(block_id):
        """Get training block details."""
        try:
            block = training_block_manager.get_block(block_id)
            stats = training_block_manager.get_block_stats(block_id)
            return jsonify({**block.to_dict(), 'stats': stats})
        except Exception as e:
            return jsonify({'error': str(e)}), 404
    
    @app.route('/api/training-blocks/<int:block_id>', methods=['DELETE'])
    @login_required
    def delete_training_block(block_id):
        """Delete a training block."""
        success = training_block_manager.delete_block(block_id)
        return jsonify({'success': success})
    
    @app.route('/api/training-blocks/<int:block_id>/files', methods=['POST'])
    @login_required
    def add_file_to_training_block(block_id):
        """Add file to training block."""
        data = request.json
        success = training_block_manager.add_file_to_block(block_id, data['file_id'])
        return jsonify({'success': success})
    
    @app.route('/api/training-blocks/<int:block_id>/files/<int:file_id>', methods=['DELETE'])
    @login_required
    def remove_file_from_training_block(block_id, file_id):
        """Remove file from training block."""
        success = training_block_manager.remove_file_from_block(block_id, file_id)
        return jsonify({'success': success})
    
    @app.route('/api/training-blocks/<int:block_id>/filechains', methods=['POST'])
    @login_required
    def add_filechain_to_training_block(block_id):
        """Add filechain to training block."""
        data = request.json
        success = training_block_manager.add_filechain_to_block(block_id, data['filechain_id'])
        return jsonify({'success': success})
    
    @app.route('/api/training-blocks/<int:block_id>/toggle', methods=['POST'])
    @login_required
    def toggle_training_block(block_id):
        """Enable/disable training block."""
        data = request.json
        enabled = training_block_manager.toggle_block(block_id, data.get('enabled'))
        return jsonify({'enabled': enabled})
    
    @app.route('/api/training-blocks/<int:block_id>/train', methods=['POST'])
    @login_required
    def train_on_block(block_id):
        """Train ML models on training block."""
        result = training_block_manager.train_on_block(block_id)
        return jsonify(result)
    
    # ============================================================
    # ML AGENT ROUTES
    # ============================================================
    
    @app.route('/api/agents', methods=['GET'])
    @login_required
    def list_agents():
        """List all ML agents."""
        db_session = db.get_session()
        try:
            agents = db_session.query(MLAgent).filter_by(owner_id=session['user_id']).all()
            return jsonify([agent.to_dict() for agent in agents])
        finally:
            db_session.close()
    
    @app.route('/api/agents/<int:agent_id>/query', methods=['POST'])
    @login_required
    def query_agent(agent_id):
        """Query an ML agent."""
        data = request.json
        try:
            agent = HybridMLAgent(
                agent_id=agent_id,
                local_ml=local_ml,
                training_block_manager=training_block_manager
            )
            
            result = agent.query_knowledge(
                question=data['question'],
                use_training_blocks=data.get('use_training_blocks', True),
                use_api=data.get('use_api', False),
                owner_id=session['user_id']
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    # ============================================================
    # MODEL MANAGEMENT ROUTES
    # ============================================================
    
    @app.route('/api/models/info', methods=['GET'])
    @login_required
    def get_model_info():
        """Get ML model information."""
        if model_manager:
            info = model_manager.get_model_info()
            return jsonify(info)
        return jsonify({'error': 'Model manager not initialized'}), 500
    
    @app.route('/api/models/download', methods=['POST'])
    @login_required
    def download_models():
        """Download ML models."""
        if model_manager:
            try:
                model_manager.download_models()
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        return jsonify({'error': 'Model manager not initialized'}), 500
    
    # ============================================================
    # ROOT ROUTE
    # ============================================================
    
    @app.route('/')
    def index():
        """Serve the main application."""
        from flask import render_template
        return render_template('index.html')

    # Enhanced routes: API connections, Coding IDE, VM management, enhancements
    from api.enhanced_routes import register_enhanced_routes
    register_enhanced_routes(app)

    return app
