"""
ML Filesystem - Flask Web Application
Main web server with REST API endpoints.
"""

from flask import Flask, request, jsonify, send_file, session as flask_session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import json
from functools import wraps

from models import Database, User, File, FileChain, MLAgent, Tag, ActivityLog
from filesystem import FileSystemManager, SecurityError
from ml_agents import MLAgentSystem


# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Enable CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize core systems
db = Database()
db.create_all()
db.init_default_data()

fs_manager = FileSystemManager(db=db)
ml_system = MLAgentSystem(db=db)


# Authentication decorator
def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = flask_session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(SecurityError)
def security_error(error):
    return jsonify({'error': str(error)}), 403


# ============================================================================
# Authentication Routes
# ============================================================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    session_obj = db.get_session()
    
    try:
        user = session_obj.query(User).filter_by(username=username).first()
        
        if user and user.check_password(password):
            # Set session
            flask_session['user_id'] = user.id
            flask_session['username'] = user.username
            flask_session.permanent = True
            
            # Update last login
            user.last_login = datetime.utcnow()
            session_obj.commit()
            
            return jsonify({
                'success': True,
                'user': user.to_dict()
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        session_obj.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_obj.close()


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """User logout endpoint."""
    flask_session.clear()
    return jsonify({'success': True})


@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint."""
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not all([username, email, password]):
        return jsonify({'error': 'All fields required'}), 400
    
    session_obj = db.get_session()
    
    try:
        # Check if user exists
        existing = session_obj.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing:
            return jsonify({'error': 'User already exists'}), 400
        
        # Create user
        user = User(
            username=username,
            email=email,
            display_name=data.get('display_name', username),
            preferences={}
        )
        user.set_password(password)
        
        session_obj.add(user)
        session_obj.commit()
        
        # Create root directory for user
        root = File(
            name='/',
            path='/',
            is_directory=True,
            file_type='directory',
            owner_id=user.id
        )
        session_obj.add(root)
        session_obj.commit()
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        })
        
    except Exception as e:
        session_obj.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_obj.close()


@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user information."""
    user_id = flask_session.get('user_id')
    session_obj = db.get_session()
    
    try:
        user = session_obj.query(User).filter_by(id=user_id).first()
        if user:
            return jsonify(user.to_dict())
        return jsonify({'error': 'User not found'}), 404
    finally:
        session_obj.close()


# ============================================================================
# User Profile Routes
# ============================================================================

@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    """Get user profile."""
    user_id = flask_session.get('user_id')
    session_obj = db.get_session()
    
    try:
        user = session_obj.query(User).filter_by(id=user_id).first()
        if user:
            return jsonify(user.to_dict())
        return jsonify({'error': 'User not found'}), 404
    finally:
        session_obj.close()


@app.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    """Update user profile."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    session_obj = db.get_session()
    
    try:
        user = session_obj.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update allowed fields
        if 'display_name' in data:
            user.display_name = data['display_name']
        if 'bio' in data:
            user.bio = data['bio']
        if 'avatar_url' in data:
            user.avatar_url = data['avatar_url']
        if 'preferences' in data:
            user.preferences.update(data['preferences'])
        
        session_obj.commit()
        
        return jsonify(user.to_dict())
        
    except Exception as e:
        session_obj.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_obj.close()


# ============================================================================
# File Operations Routes
# ============================================================================

@app.route('/api/files', methods=['GET'])
@login_required
def list_files():
    """List files in a directory."""
    user_id = flask_session.get('user_id')
    path = request.args.get('path', '/')
    show_hidden = request.args.get('show_hidden', 'false').lower() == 'true'
    
    try:
        files = fs_manager.list_directory(path, user_id, show_hidden)
        return jsonify({
            'path': path,
            'files': [f.to_dict() for f in files]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/files/create', methods=['POST'])
@login_required
def create_file():
    """Create a new file."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    path = data.get('path')
    content = data.get('content', '')
    tags = data.get('tags', [])
    metadata = data.get('metadata', {})
    
    if not path:
        return jsonify({'error': 'Path required'}), 400
    
    try:
        file = fs_manager.create_file(path, content, user_id, tags, metadata)
        
        # Emit real-time update
        socketio.emit('file_created', file.to_dict(), room=f'user_{user_id}')
        
        return jsonify(file.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/files/mkdir', methods=['POST'])
@login_required
def create_directory():
    """Create a new directory."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    path = data.get('path')
    
    if not path:
        return jsonify({'error': 'Path required'}), 400
    
    try:
        directory = fs_manager.create_directory(path, user_id)
        
        # Emit real-time update
        socketio.emit('directory_created', directory.to_dict(), room=f'user_{user_id}')
        
        return jsonify(directory.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/files/read', methods=['GET'])
@login_required
def read_file():
    """Read file content."""
    user_id = flask_session.get('user_id')
    path = request.args.get('path')
    
    if not path:
        return jsonify({'error': 'Path required'}), 400
    
    try:
        content = fs_manager.read_file(path, user_id)
        return jsonify({
            'path': path,
            'content': content
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/files/update', methods=['PUT'])
@login_required
def update_file():
    """Update file content."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    path = data.get('path')
    content = data.get('content')
    
    if not path or content is None:
        return jsonify({'error': 'Path and content required'}), 400
    
    try:
        file = fs_manager.update_file(path, content, user_id)
        
        # Emit real-time update
        socketio.emit('file_updated', file.to_dict(), room=f'user_{user_id}')
        
        return jsonify(file.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/files/delete', methods=['DELETE'])
@login_required
def delete_file():
    """Delete a file or directory."""
    user_id = flask_session.get('user_id')
    path = request.args.get('path')
    
    if not path:
        return jsonify({'error': 'Path required'}), 400
    
    try:
        fs_manager.delete_file(path, user_id)
        
        # Emit real-time update
        socketio.emit('file_deleted', {'path': path}, room=f'user_{user_id}')
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/files/move', methods=['POST'])
@login_required
def move_file():
    """Move/rename a file or directory."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    source = data.get('source')
    destination = data.get('destination')
    
    if not source or not destination:
        return jsonify({'error': 'Source and destination required'}), 400
    
    try:
        file = fs_manager.move_file(source, destination, user_id)
        
        # Emit real-time update
        socketio.emit('file_moved', {
            'source': source,
            'destination': destination,
            'file': file.to_dict()
        }, room=f'user_{user_id}')
        
        return jsonify(file.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/files/search', methods=['GET'])
@login_required
def search_files():
    """Search for files."""
    user_id = flask_session.get('user_id')
    query = request.args.get('q', '')
    file_type = request.args.get('type')
    tags = request.args.getlist('tags')
    path_prefix = request.args.get('path')
    
    try:
        files = fs_manager.search_files(query, user_id, file_type, tags, path_prefix)
        return jsonify({
            'query': query,
            'results': [f.to_dict() for f in files]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/files/info', methods=['GET'])
@login_required
def file_info():
    """Get file information."""
    path = request.args.get('path')
    
    if not path:
        return jsonify({'error': 'Path required'}), 400
    
    try:
        file = fs_manager.get_file_info(path)
        if file:
            return jsonify(file.to_dict(include_content=False))
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/files/mark-for-learning', methods=['POST'])
@login_required
def mark_for_learning():
    """Mark files for ML learning."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    file_ids = data.get('file_ids', [])
    marked = data.get('marked', True)
    
    session_obj = db.get_session()
    
    try:
        files = session_obj.query(File).filter(File.id.in_(file_ids)).all()
        
        for file in files:
            file.is_marked_for_learning = marked
        
        session_obj.commit()
        
        return jsonify({
            'success': True,
            'marked_count': len(files)
        })
        
    except Exception as e:
        session_obj.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_obj.close()


# ============================================================================
# File Chain Routes
# ============================================================================

@app.route('/api/chains', methods=['GET'])
@login_required
def list_chains():
    """List all file chains."""
    user_id = flask_session.get('user_id')
    session_obj = db.get_session()
    
    try:
        chains = session_obj.query(FileChain).filter_by(owner_id=user_id).all()
        return jsonify({
            'chains': [chain.to_dict() for chain in chains]
        })
    finally:
        session_obj.close()


@app.route('/api/chains', methods=['POST'])
@login_required
def create_chain():
    """Create a new file chain."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    name = data.get('name')
    description = data.get('description', '')
    file_ids = data.get('file_ids', [])
    
    if not name:
        return jsonify({'error': 'Chain name required'}), 400
    
    session_obj = db.get_session()
    
    try:
        chain = FileChain(
            name=name,
            description=description,
            owner_id=user_id
        )
        
        # Add files to chain
        if file_ids:
            files = session_obj.query(File).filter(File.id.in_(file_ids)).all()
            chain.files.extend(files)
        
        session_obj.add(chain)
        session_obj.commit()
        
        return jsonify(chain.to_dict())
        
    except Exception as e:
        session_obj.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_obj.close()


@app.route('/api/chains/<int:chain_id>', methods=['GET'])
@login_required
def get_chain(chain_id):
    """Get file chain details."""
    session_obj = db.get_session()
    
    try:
        chain = session_obj.query(FileChain).filter_by(id=chain_id).first()
        if chain:
            return jsonify(chain.to_dict())
        return jsonify({'error': 'Chain not found'}), 404
    finally:
        session_obj.close()


@app.route('/api/chains/<int:chain_id>', methods=['PUT'])
@login_required
def update_chain(chain_id):
    """Update file chain."""
    data = request.get_json()
    session_obj = db.get_session()
    
    try:
        chain = session_obj.query(FileChain).filter_by(id=chain_id).first()
        if not chain:
            return jsonify({'error': 'Chain not found'}), 404
        
        if 'name' in data:
            chain.name = data['name']
        if 'description' in data:
            chain.description = data['description']
        if 'file_ids' in data:
            files = session_obj.query(File).filter(File.id.in_(data['file_ids'])).all()
            chain.files = files
        
        chain.modified_at = datetime.utcnow()
        session_obj.commit()
        
        return jsonify(chain.to_dict())
        
    except Exception as e:
        session_obj.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_obj.close()


@app.route('/api/chains/<int:chain_id>', methods=['DELETE'])
@login_required
def delete_chain(chain_id):
    """Delete file chain."""
    session_obj = db.get_session()
    
    try:
        chain = session_obj.query(FileChain).filter_by(id=chain_id).first()
        if not chain:
            return jsonify({'error': 'Chain not found'}), 404
        
        session_obj.delete(chain)
        session_obj.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        session_obj.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_obj.close()


# ============================================================================
# ML Agent Routes
# ============================================================================

@app.route('/api/agents', methods=['GET'])
@login_required
def list_agents():
    """List all ML agents."""
    user_id = flask_session.get('user_id')
    session_obj = db.get_session()
    
    try:
        agents = session_obj.query(MLAgent).filter_by(owner_id=user_id).all()
        return jsonify({
            'agents': [agent.to_dict() for agent in agents]
        })
    finally:
        session_obj.close()


@app.route('/api/agents', methods=['POST'])
@login_required
def create_agent():
    """Create a new ML agent."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    name = data.get('name')
    description = data.get('description', '')
    agent_type = data.get('agent_type', 'custom')
    system_prompt = data.get('system_prompt')
    config = data.get('config', {})
    
    if not name:
        return jsonify({'error': 'Agent name required'}), 400
    
    try:
        agent = ml_system.create_agent(
            name=name,
            description=description,
            agent_type=agent_type,
            user_id=user_id,
            system_prompt=system_prompt,
            config=config
        )
        
        return jsonify(agent.to_dict())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/agents/<int:agent_id>', methods=['GET'])
@login_required
def get_agent(agent_id):
    """Get ML agent details."""
    session_obj = db.get_session()
    
    try:
        agent = session_obj.query(MLAgent).filter_by(id=agent_id).first()
        if agent:
            return jsonify(agent.to_dict())
        return jsonify({'error': 'Agent not found'}), 404
    finally:
        session_obj.close()


@app.route('/api/agents/<int:agent_id>/organize', methods=['POST'])
@login_required
def agent_organize(agent_id):
    """Use agent to organize files."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    file_ids = data.get('file_ids', [])
    
    if not file_ids:
        return jsonify({'error': 'File IDs required'}), 400
    
    try:
        result = ml_system.organize_files(agent_id, file_ids, user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/agents/<int:agent_id>/learn', methods=['POST'])
@login_required
def agent_learn(agent_id):
    """Use agent to learn from files."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    file_ids = data.get('file_ids', [])
    
    if not file_ids:
        return jsonify({'error': 'File IDs required'}), 400
    
    try:
        result = ml_system.learn_from_files(agent_id, file_ids, user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/agents/<int:agent_id>/query', methods=['POST'])
@login_required
def agent_query(agent_id):
    """Query agent's knowledge."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    query = data.get('query')
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    try:
        result = ml_system.query_agent_knowledge(agent_id, query, user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/agents/<int:agent_id>/analyze-chain', methods=['POST'])
@login_required
def agent_analyze_chain(agent_id):
    """Use agent to analyze file chain."""
    user_id = flask_session.get('user_id')
    data = request.get_json()
    
    chain_id = data.get('chain_id')
    
    if not chain_id:
        return jsonify({'error': 'Chain ID required'}), 400
    
    try:
        result = ml_system.analyze_file_chain(agent_id, chain_id, user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Tag Routes
# ============================================================================

@app.route('/api/tags', methods=['GET'])
@login_required
def list_tags():
    """List all tags."""
    session_obj = db.get_session()
    
    try:
        tags = session_obj.query(Tag).all()
        return jsonify({
            'tags': [tag.to_dict() for tag in tags]
        })
    finally:
        session_obj.close()


@app.route('/api/tags', methods=['POST'])
@login_required
def create_tag():
    """Create a new tag."""
    data = request.get_json()
    
    name = data.get('name')
    color = data.get('color', '#3B82F6')
    description = data.get('description', '')
    
    if not name:
        return jsonify({'error': 'Tag name required'}), 400
    
    session_obj = db.get_session()
    
    try:
        tag = Tag(name=name, color=color, description=description)
        session_obj.add(tag)
        session_obj.commit()
        
        return jsonify(tag.to_dict())
        
    except Exception as e:
        session_obj.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session_obj.close()


# ============================================================================
# Activity Log Routes
# ============================================================================

@app.route('/api/activity', methods=['GET'])
@login_required
def get_activity():
    """Get activity log."""
    user_id = flask_session.get('user_id')
    limit = request.args.get('limit', 50, type=int)
    
    session_obj = db.get_session()
    
    try:
        logs = session_obj.query(ActivityLog).filter_by(user_id=user_id)\
            .order_by(ActivityLog.timestamp.desc())\
            .limit(limit)\
            .all()
        
        return jsonify({
            'logs': [log.to_dict() for log in logs]
        })
    finally:
        session_obj.close()


# ============================================================================
# WebSocket Events
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    user_id = flask_session.get('user_id')
    if user_id:
        # Join user-specific room
        from flask_socketio import join_room
        join_room(f'user_{user_id}')
        emit('connected', {'user_id': user_id})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    pass


# ============================================================================
# ============================================================================
# Main Routes
# ============================================================================

@app.route('/')
def index():
    """Serve main HTML page."""
    from flask import render_template
    return render_template('index.html')


# ============================================================================
# Health Check
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })


if __name__ == '__main__':
    print("ML Filesystem Server Starting...")
    print("=" * 50)
    print("Server running on http://localhost:5000")
    print("API Documentation: http://localhost:5000/api")
    print("=" * 50)
    
    # Run server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
