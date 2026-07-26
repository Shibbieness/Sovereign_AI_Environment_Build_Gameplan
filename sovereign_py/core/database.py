"""
Database models for ML Filesystem v1.8
Includes Training Blocks as first-class citizens.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import json
import hashlib
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    Boolean, ForeignKey, Table, Float, JSON, LargeBinary
)
from sqlalchemy.orm import relationship, sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

from core.config import Config
from core.exceptions import DatabaseConnectionError
from core.base import Base


# Association Tables
file_tags = Table(
    'file_tags',
    Base.metadata,
    Column('file_id', Integer, ForeignKey('files.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

filechain_files = Table(
    'filechain_files',
    Base.metadata,
    Column('filechain_id', Integer, ForeignKey('filechains.id'), primary_key=True),
    Column('file_id', Integer, ForeignKey('files.id'), primary_key=True),
    Column('order', Integer, default=0)
)

training_block_files = Table(
    'training_block_files',
    Base.metadata,
    Column('training_block_id', Integer, ForeignKey('training_blocks.id'), primary_key=True),
    Column('file_id', Integer, ForeignKey('files.id'), primary_key=True),
    Column('added_at', DateTime, default=datetime.utcnow)
)

training_block_filechains = Table(
    'training_block_filechains',
    Base.metadata,
    Column('training_block_id', Integer, ForeignKey('training_blocks.id'), primary_key=True),
    Column('filechain_id', Integer, ForeignKey('filechains.id'), primary_key=True),
    Column('added_at', DateTime, default=datetime.utcnow)
)


class User(Base):
    """User accounts."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    preferences = Column(JSON, default=dict)
    
    # Relationships
    files = relationship('File', back_populates='owner', cascade='all, delete-orphan')
    filechains = relationship('FileChain', back_populates='owner', cascade='all, delete-orphan')
    training_blocks = relationship('TrainingBlock', back_populates='owner', cascade='all, delete-orphan')
    ml_agents = relationship('MLAgent', back_populates='owner', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'preferences': self.preferences
        }


class File(Base):
    """
    Semantic file object.
    Files can be in multiple training blocks and filechains.
    """
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    path = Column(String(500), nullable=False, unique=True)
    content_hash = Column(String(64))  # SHA-256
    size = Column(Integer, default=0)
    mime_type = Column(String(100))
    file_type = Column(String(50))  # document, image, video, audio, code, etc.
    
    # Content (for text files, stored directly)
    content = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    accessed_at = Column(DateTime)
    
    # Ownership
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship('User', back_populates='files')
    
    # ML metadata
    embedding_generated = Column(Boolean, default=False)
    last_embedded = Column(DateTime)
    
    # Training block participation
    in_training_blocks = Column(Boolean, default=False)
    
    # Relationships
    tags = relationship('Tag', secondary=file_tags, back_populates='files')
    filechains = relationship('FileChain', secondary=filechain_files, back_populates='files')
    training_blocks = relationship('TrainingBlock', secondary=training_block_files, back_populates='files')
    embeddings = relationship('FileEmbedding', back_populates='file', cascade='all, delete-orphan')
    
    def generate_hash(self):
        """Generate content hash."""
        if self.content:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()
        return self.content_hash
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'size': self.size,
            'mime_type': self.mime_type,
            'file_type': self.file_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'modified_at': self.modified_at.isoformat() if self.modified_at else None,
            'tags': [tag.name for tag in self.tags],
            'in_training_blocks': self.in_training_blocks,
            'training_blocks': [tb.name for tb in self.training_blocks],
            'filechains': [fc.name for fc in self.filechains],
            'owner_id': self.owner_id
        }


class FileChain(Base):
    """
    Group of related files.
    Can be added to training blocks as a unit.
    """
    __tablename__ = 'filechains'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Ownership
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship('User', back_populates='filechains')
    
    # ML metadata
    summary = Column(Text)
    embedding_generated = Column(Boolean, default=False)
    
    # Relationships
    files = relationship('File', secondary=filechain_files, back_populates='filechains', order_by='filechain_files.c.order')
    training_blocks = relationship('TrainingBlock', secondary=training_block_filechains, back_populates='filechains')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'file_count': len(self.files),
            'files': [{'id': f.id, 'name': f.name} for f in self.files],
            'training_blocks': [tb.name for tb in self.training_blocks],
            'summary': self.summary
        }


class TrainingBlock(Base):
    """
    Training Block - collection of files/filechains for ML training.
    Can be enabled/disabled to control what AI has access to.
    
    This is the core new feature for v1.8.
    """
    __tablename__ = 'training_blocks'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Type of training block
    block_type = Column(String(50), default='rote')  # 'rote' or 'process'
    # rote = factual data (dates, names, facts)
    # process = how to do things (patterns, workflows)
    
    # Enable/disable state
    enabled = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_trained = Column(DateTime)
    
    # Statistics
    file_count = Column(Integer, default=0)
    filechain_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)  # Approximate
    
    # Ownership
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship('User', back_populates='training_blocks')
    
    # Relationships
    files = relationship('File', secondary=training_block_files, back_populates='training_blocks')
    filechains = relationship('FileChain', secondary=training_block_filechains, back_populates='training_blocks')
    agents = relationship('MLAgent', back_populates='training_block')
    
    def update_counts(self):
        """Update file and filechain counts."""
        self.file_count = len(self.files)
        self.filechain_count = len(self.filechains)
    
    def get_all_files(self) -> List['File']:
        """Get all files including those in filechains."""
        all_files = set(self.files)
        for chain in self.filechains:
            all_files.update(chain.files)
        return list(all_files)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'block_type': self.block_type,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_trained': self.last_trained.isoformat() if self.last_trained else None,
            'file_count': self.file_count,
            'filechain_count': self.filechain_count,
            'total_tokens': self.total_tokens,
            'files': [{'id': f.id, 'name': f.name} for f in self.files],
            'filechains': [{'id': fc.id, 'name': fc.name} for fc in self.filechains]
        }


class MLAgent(Base):
    """
    ML Agent - can be assigned training blocks.
    """
    __tablename__ = 'ml_agents'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    agent_type = Column(String(50), nullable=False)  # organizer, learner, analyzer, custom
    description = Column(Text)
    
    # Configuration
    config = Column(JSON, default=dict)
    
    # Training block assignment
    training_block_id = Column(Integer, ForeignKey('training_blocks.id'))
    training_block = relationship('TrainingBlock', back_populates='agents')
    
    # State
    active = Column(Boolean, default=True)
    last_active = Column(DateTime)
    
    # Ownership
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship('User', back_populates='ml_agents')
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'agent_type': self.agent_type,
            'description': self.description,
            'config': self.config,
            'training_block': self.training_block.name if self.training_block else None,
            'active': self.active,
            'last_active': self.last_active.isoformat() if self.last_active else None
        }


class Tag(Base):
    """Tags for organizing files."""
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    color = Column(String(7))  # Hex color
    
    # Relationships
    files = relationship('File', secondary=file_tags, back_populates='tags')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'file_count': len(self.files)
        }


class FileEmbedding(Base):
    """Stored embeddings for files."""
    __tablename__ = 'file_embeddings'
    
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    file = relationship('File', back_populates='embeddings')
    
    # Embedding data
    model_name = Column(String(100))
    embedding = Column(LargeBinary)  # Stored as bytes
    dimension = Column(Integer)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'file_id': self.file_id,
            'model_name': self.model_name,
            'dimension': self.dimension,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ActivityLog(Base):
    """Activity logging for audit trail."""
    __tablename__ = 'activity_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(Integer)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'details': self.details,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class Database:
    """
    Database manager.
    Handles connection, session management, and initialization.
    """
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or Config.DATABASE_URL
        self.engine = None
        self.Session = None
        
    def init_db(self):
        """Initialize database connection and create tables."""
        try:
            # Create engine
            if self.database_url.startswith('sqlite'):
                self.engine = create_engine(
                    self.database_url,
                    connect_args={'check_same_thread': False},
                    poolclass=StaticPool
                )
            else:
                self.engine = create_engine(self.database_url)
            
            # Create session factory
            self.Session = scoped_session(sessionmaker(bind=self.engine))

            # Import enhanced models so their tables register on Base.metadata
            # before create_all runs. Without this only the 12 base tables
            # get created; the 5 enhanced tables are silently skipped.
            from core.enhanced_models import (
                APIConnection, CodingProject, CodeExecution,
                VMConfiguration, VMSnapshot
            )

            # Create all tables
            Base.metadata.create_all(self.engine)
            
            print("✓ Database initialized successfully")
            
            # Create default data
            self._create_defaults()
            
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to initialize database: {str(e)}")
    
    def _create_defaults(self):
        """Create default user and data."""
        session = self.Session()
        
        try:
            # Check if admin user exists
            admin = session.query(User).filter_by(username='admin').first()
            
            if not admin:
                # Create admin user
                admin = User(
                    username='admin',
                    email='admin@localhost',
                    password_hash=hashlib.sha256('admin'.encode()).hexdigest(),
                    preferences={
                        'theme': 'dark',
                        'ml_model_profile': Config.ML_MODEL_PROFILE
                    }
                )
                session.add(admin)
                
                # Create default tags
                default_tags = [
                    Tag(name='important', color='#ff0000'),
                    Tag(name='work', color='#0000ff'),
                    Tag(name='personal', color='#00ff00'),
                    Tag(name='archive', color='#888888'),
                ]
                session.add_all(default_tags)
                
                # Create default training blocks
                default_blocks = [
                    TrainingBlock(
                        name='General Knowledge',
                        description='General facts and information',
                        block_type='rote',
                        enabled=True,
                        owner=admin
                    ),
                    TrainingBlock(
                        name='Code Patterns',
                        description='Programming patterns and solutions',
                        block_type='process',
                        enabled=True,
                        owner=admin
                    ),
                    TrainingBlock(
                        name='Personal Notes',
                        description='Private notes and thoughts',
                        block_type='rote',
                        enabled=False,  # Disabled by default for privacy
                        owner=admin
                    )
                ]
                session.add_all(default_blocks)
                
                session.commit()
                print("✓ Default data created")
        
        except Exception as e:
            session.rollback()
            print(f"⚠️  Error creating defaults: {e}")
        
        finally:
            session.close()
    
    def get_session(self):
        """Get a new database session."""
        return self.Session()
    
    def close(self):
        """Close database connection."""
        if self.Session:
            self.Session.remove()
        if self.engine:
            self.engine.dispose()


# Global database instance
db = Database()
