"""
ML Filesystem - Core Database Models
Defines all database models for the system including files, users, ML agents, and relationships.
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Table, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import json
import hashlib
import os

Base = declarative_base()

# Association tables for many-to-many relationships
file_tags = Table('file_tags', Base.metadata,
    Column('file_id', Integer, ForeignKey('files.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)

file_ml_agents = Table('file_ml_agents', Base.metadata,
    Column('file_id', Integer, ForeignKey('files.id')),
    Column('ml_agent_id', Integer, ForeignKey('ml_agents.id'))
)

file_chain_files = Table('file_chain_files', Base.metadata,
    Column('file_chain_id', Integer, ForeignKey('file_chains.id')),
    Column('file_id', Integer, ForeignKey('files.id')),
    Column('position', Integer, default=0)
)

class User(Base):
    """User model for authentication and personalization."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Profile information
    display_name = Column(String(120))
    bio = Column(Text)
    avatar_url = Column(String(500))
    preferences = Column(JSON, default={})
    
    # Relationships
    files = relationship('File', back_populates='owner', cascade='all, delete-orphan')
    ml_agents = relationship('MLAgent', back_populates='owner', cascade='all, delete-orphan')
    file_chains = relationship('FileChain', back_populates='owner', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set user password."""
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        """Verify user password."""
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()
    
    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'display_name': self.display_name,
            'bio': self.bio,
            'avatar_url': self.avatar_url,
            'preferences': self.preferences,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class File(Base):
    """File model representing files in the virtual filesystem."""
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    path = Column(String(1000), nullable=False, unique=True)
    file_type = Column(String(50))  # text, code, pdf, html, directory, etc.
    mime_type = Column(String(100))
    size = Column(Integer, default=0)
    
    # Content storage
    content = Column(Text)  # For text files
    content_hash = Column(String(64))  # SHA-256 hash for deduplication
    storage_path = Column(String(1000))  # Path to actual file on disk if large
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accessed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    parent_id = Column(Integer, ForeignKey('files.id'))
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # File hierarchy
    parent = relationship('File', remote_side=[id], backref='children')
    owner = relationship('User', back_populates='files')
    
    # ML and organization
    tags = relationship('Tag', secondary=file_tags, back_populates='files')
    ml_agents = relationship('MLAgent', secondary=file_ml_agents, back_populates='files')
    embeddings = relationship('FileEmbedding', back_populates='file', cascade='all, delete-orphan')
    
    # Flags
    is_directory = Column(Boolean, default=False)
    is_marked_for_learning = Column(Boolean, default=False)
    is_executable = Column(Boolean, default=False)
    is_hidden = Column(Boolean, default=False)
    
    # ML metadata
    ml_metadata = Column(JSON, default={})
    
    def to_dict(self, include_content=False):
        """Convert file to dictionary."""
        data = {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'file_type': self.file_type,
            'mime_type': self.mime_type,
            'size': self.size,
            'is_directory': self.is_directory,
            'is_marked_for_learning': self.is_marked_for_learning,
            'is_executable': self.is_executable,
            'is_hidden': self.is_hidden,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'modified_at': self.modified_at.isoformat() if self.modified_at else None,
            'accessed_at': self.accessed_at.isoformat() if self.accessed_at else None,
            'parent_id': self.parent_id,
            'owner_id': self.owner_id,
            'tags': [tag.name for tag in self.tags],
            'ml_agents': [agent.id for agent in self.ml_agents],
            'ml_metadata': self.ml_metadata
        }
        
        if include_content and not self.is_directory:
            data['content'] = self.content
        
        return data
    
    def update_hash(self):
        """Update content hash."""
        if self.content:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


class FileChain(Base):
    """File chain model for organizing related files."""
    __tablename__ = 'file_chains'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship('User', back_populates='file_chains')
    
    # Files in this chain (ordered)
    files = relationship('File', secondary=file_chain_files, backref='file_chains')
    
    # ML agents assigned to this chain
    ml_agents = relationship('MLAgent', back_populates='file_chain')
    
    # Chain metadata
    metadata = Column(JSON, default={})
    is_marked_for_learning = Column(Boolean, default=False)
    
    def to_dict(self):
        """Convert file chain to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'modified_at': self.modified_at.isoformat() if self.modified_at else None,
            'owner_id': self.owner_id,
            'files': [f.to_dict() for f in self.files],
            'ml_agents': [agent.id for agent in self.ml_agents],
            'metadata': self.metadata,
            'is_marked_for_learning': self.is_marked_for_learning
        }


class MLAgent(Base):
    """ML Agent model for AI-powered file organization and learning."""
    __tablename__ = 'ml_agents'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    agent_type = Column(String(50))  # organizer, learner, analyzer, custom
    
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active = Column(DateTime)
    
    # Configuration
    config = Column(JSON, default={})
    system_prompt = Column(Text)
    model = Column(String(100), default='claude-sonnet-4-20250514')
    
    # Relationships
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship('User', back_populates='ml_agents')
    
    file_chain_id = Column(Integer, ForeignKey('file_chains.id'))
    file_chain = relationship('FileChain', back_populates='ml_agents')
    
    files = relationship('File', secondary=file_ml_agents, back_populates='ml_agents')
    
    # Learning data
    knowledge_base = Column(JSON, default={})  # Stores learned information
    embeddings_collection = Column(String(255))  # ChromaDB collection name
    
    # Statistics
    interactions_count = Column(Integer, default=0)
    files_processed = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_learning = Column(Boolean, default=False)
    
    def to_dict(self):
        """Convert ML agent to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'agent_type': self.agent_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'modified_at': self.modified_at.isoformat() if self.modified_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'config': self.config,
            'system_prompt': self.system_prompt,
            'model': self.model,
            'owner_id': self.owner_id,
            'file_chain_id': self.file_chain_id,
            'files': [f.id for f in self.files],
            'knowledge_base': self.knowledge_base,
            'interactions_count': self.interactions_count,
            'files_processed': self.files_processed,
            'is_active': self.is_active,
            'is_learning': self.is_learning
        }


class Tag(Base):
    """Tag model for file categorization."""
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    color = Column(String(7), default='#3B82F6')  # Hex color
    description = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    files = relationship('File', secondary=file_tags, back_populates='tags')
    
    def to_dict(self):
        """Convert tag to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'file_count': len(self.files)
        }


class FileEmbedding(Base):
    """Store vector embeddings for semantic search."""
    __tablename__ = 'file_embeddings'
    
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    file = relationship('File', back_populates='embeddings')
    
    # Embedding data
    embedding_model = Column(String(100))
    chunk_index = Column(Integer, default=0)  # For large files split into chunks
    chunk_text = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert embedding to dictionary."""
        return {
            'id': self.id,
            'file_id': self.file_id,
            'embedding_model': self.embedding_model,
            'chunk_index': self.chunk_index,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ActivityLog(Base):
    """Log system activities and ML agent actions."""
    __tablename__ = 'activity_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey('users.id'))
    ml_agent_id = Column(Integer, ForeignKey('ml_agents.id'))
    file_id = Column(Integer, ForeignKey('files.id'))
    
    action = Column(String(100))  # create, update, delete, organize, learn, etc.
    details = Column(JSON, default={})
    
    def to_dict(self):
        """Convert activity log to dictionary."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': self.user_id,
            'ml_agent_id': self.ml_agent_id,
            'file_id': self.file_id,
            'action': self.action,
            'details': self.details
        }


# Database initialization
class Database:
    """Database manager class."""
    
    def __init__(self, db_url='sqlite:///ml_filesystem.db'):
        """Initialize database connection."""
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        
    def create_all(self):
        """Create all tables."""
        Base.metadata.create_all(self.engine)
        
    def drop_all(self):
        """Drop all tables."""
        Base.metadata.drop_all(self.engine)
        
    def get_session(self):
        """Get a new session."""
        return self.Session()
    
    def init_default_data(self):
        """Initialize database with default data."""
        session = self.get_session()
        
        try:
            # Create default user if not exists
            user = session.query(User).filter_by(username='admin').first()
            if not user:
                user = User(
                    username='admin',
                    email='admin@mlfs.local',
                    display_name='Administrator',
                    preferences={
                        'theme': 'dark',
                        'default_view': 'grid',
                        'auto_organize': True
                    }
                )
                user.set_password('admin')  # Change in production!
                session.add(user)
                session.commit()
                
                # Create root directory
                root = File(
                    name='/',
                    path='/',
                    is_directory=True,
                    file_type='directory',
                    owner_id=user.id
                )
                session.add(root)
                
                # Create default directories
                directories = ['Documents', 'Projects', 'Archive', 'Trash']
                for dir_name in directories:
                    directory = File(
                        name=dir_name,
                        path=f'/{dir_name}',
                        is_directory=True,
                        file_type='directory',
                        owner_id=user.id,
                        parent=root
                    )
                    session.add(directory)
                
                # Create default ML agents
                organizer = MLAgent(
                    name='Auto Organizer',
                    description='Automatically organizes files based on content and metadata',
                    agent_type='organizer',
                    system_prompt='You are an intelligent file organizer. Analyze files and suggest optimal organization strategies.',
                    owner_id=user.id,
                    config={
                        'auto_tag': True,
                        'suggest_folders': True,
                        'analyze_duplicates': True
                    }
                )
                session.add(organizer)
                
                learner = MLAgent(
                    name='Knowledge Learner',
                    description='Learns from marked files and file chains',
                    agent_type='learner',
                    system_prompt='You are a knowledge extraction system. Learn and synthesize information from provided files.',
                    owner_id=user.id,
                    config={
                        'extract_key_concepts': True,
                        'build_knowledge_graph': True,
                        'generate_summaries': True
                    }
                )
                session.add(learner)
                
                # Create default tags
                default_tags = [
                    ('Important', '#EF4444'),
                    ('Work', '#3B82F6'),
                    ('Personal', '#10B981'),
                    ('Archive', '#6B7280'),
                    ('Learning', '#8B5CF6')
                ]
                
                for tag_name, color in default_tags:
                    tag = Tag(name=tag_name, color=color)
                    session.add(tag)
                
                session.commit()
                print("Default data initialized successfully!")
                
        except Exception as e:
            session.rollback()
            print(f"Error initializing default data: {e}")
            raise
        finally:
            session.close()


if __name__ == '__main__':
    # Test database creation
    db = Database()
    db.create_all()
    db.init_default_data()
    print("Database models created successfully!")
