"""
Enhanced Database Models for v1.8+
Adds: API Connections, Coding Projects, VM Configurations
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from core.base import Base


class ServiceType(enum.Enum):
    """Types of API services."""
    AI_INFERENCE = "ai_inference"  # Claude, GPT, Gemini, etc.
    STREAMING = "streaming"  # Twitch, YouTube, etc.
    SOCIAL_MEDIA = "social_media"  # Twitter, Reddit, etc.
    STORAGE = "storage"  # S3, Drive, Dropbox
    ANALYTICS = "analytics"  # Google Analytics, etc.
    CUSTOM = "custom"  # User-defined


class APIConnection(Base):
    """
    API Connection Configuration
    
    Allows multiple API connections per service type.
    Can enable/disable without deletion.
    Supports connection testing.
    """
    __tablename__ = 'api_connections'
    
    id = Column(Integer, primary_key=True)
    
    # Identification
    name = Column(String(200), nullable=False)  # User-friendly name
    description = Column(Text)  # Optional description
    service_type = Column(SQLEnum(ServiceType), nullable=False)
    provider = Column(String(100))  # e.g., "Anthropic", "OpenAI", "Custom"
    
    # Configuration
    api_key = Column(String(500))  # Encrypted in production
    base_url = Column(String(500))  # API endpoint
    model_name = Column(String(100))  # Default model if applicable
    config = Column(JSON, default=dict)  # Additional config (rate limits, etc.)
    
    # State
    enabled = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)
    last_tested = Column(DateTime)
    test_status = Column(String(50))  # success, failed, pending
    test_message = Column(Text)
    
    # Statistics
    usage_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    
    # Ownership
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship('User', backref='api_connections')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'service_type': self.service_type.value,
            'provider': self.provider,
            'base_url': self.base_url,
            'model_name': self.model_name,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'last_tested': self.last_tested.isoformat() if self.last_tested else None,
            'test_status': self.test_status,
            'test_message': self.test_message,
            'usage_count': self.usage_count,
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost,
            'has_api_key': bool(self.api_key)
        }
    
    def to_dict_safe(self):
        """Return dict without sensitive data."""
        data = self.to_dict()
        data.pop('api_key', None)
        return data


class CodingProject(Base):
    """
    Coding Project in IDE
    
    Projects contain files, settings, and execution history.
    """
    __tablename__ = 'coding_projects'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Project type
    language = Column(String(50))  # python, javascript, etc.
    framework = Column(String(50))  # flask, react, etc.
    
    # Paths
    root_path = Column(String(500), nullable=False)  # Within sandbox
    
    # Settings
    settings = Column(JSON, default=dict)  # Editor settings, linter config, etc.
    
    # Git integration
    git_repo = Column(String(500))  # Git repository URL
    git_branch = Column(String(100))  # Current branch
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_opened = Column(DateTime)
    
    # Ownership
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship('User', backref='coding_projects')
    
    # Relationships
    executions = relationship('CodeExecution', back_populates='project', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'language': self.language,
            'framework': self.framework,
            'root_path': self.root_path,
            'settings': self.settings,
            'git_repo': self.git_repo,
            'git_branch': self.git_branch,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'modified_at': self.modified_at.isoformat() if self.modified_at else None,
            'last_opened': self.last_opened.isoformat() if self.last_opened else None
        }


class CodeExecution(Base):
    """
    Code Execution History
    
    Tracks all code executions for debugging and analysis.
    """
    __tablename__ = 'code_executions'
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('coding_projects.id'), nullable=False)
    project = relationship('CodingProject', back_populates='executions')
    
    # Execution details
    code = Column(Text, nullable=False)  # Code that was run
    language = Column(String(50))
    entry_point = Column(String(500))  # File that was executed
    
    # Results
    status = Column(String(50))  # success, error, timeout
    stdout = Column(Text)
    stderr = Column(Text)
    exit_code = Column(Integer)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)
    
    # Environment
    env_vars = Column(JSON, default=dict)
    working_dir = Column(String(500))
    
    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'language': self.language,
            'entry_point': self.entry_point,
            'status': self.status,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'exit_code': self.exit_code,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_ms': self.duration_ms
        }


class VMConfiguration(Base):
    """
    Virtual Machine Configuration
    
    Supports both Docker containers and full VMs.
    """
    __tablename__ = 'vm_configurations'
    
    id = Column(Integer, primary_key=True)
    
    # Identification
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Type
    vm_type = Column(String(50), nullable=False)  # docker, qemu, virtualbox
    
    # Configuration
    image = Column(String(200))  # Docker image or VM image path
    os_type = Column(String(50))  # linux, windows, macos
    
    # Resources
    cpu_cores = Column(Integer, default=2)
    memory_mb = Column(Integer, default=2048)
    disk_gb = Column(Integer, default=20)
    
    # Network
    network_mode = Column(String(50))  # bridge, nat, host
    port_mappings = Column(JSON, default=dict)  # {guest_port: host_port}
    
    # Advanced settings
    config = Column(JSON, default=dict)
    
    # State
    status = Column(String(50))  # stopped, running, paused, error
    enabled = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_started = Column(DateTime)
    last_stopped = Column(DateTime)
    
    # Ownership
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship('User', backref='vm_configurations')
    
    # Relationships
    snapshots = relationship('VMSnapshot', back_populates='vm', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'vm_type': self.vm_type,
            'image': self.image,
            'os_type': self.os_type,
            'cpu_cores': self.cpu_cores,
            'memory_mb': self.memory_mb,
            'disk_gb': self.disk_gb,
            'network_mode': self.network_mode,
            'port_mappings': self.port_mappings,
            'status': self.status,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_started': self.last_started.isoformat() if self.last_started else None,
            'last_stopped': self.last_stopped.isoformat() if self.last_stopped else None
        }


class VMSnapshot(Base):
    """
    VM Snapshots for rollback/restore.
    """
    __tablename__ = 'vm_snapshots'
    
    id = Column(Integer, primary_key=True)
    vm_id = Column(Integer, ForeignKey('vm_configurations.id'), nullable=False)
    vm = relationship('VMConfiguration', back_populates='snapshots')
    
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Snapshot data
    snapshot_path = Column(String(500))
    size_mb = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'vm_id': self.vm_id,
            'name': self.name,
            'description': self.description,
            'size_mb': self.size_mb,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
