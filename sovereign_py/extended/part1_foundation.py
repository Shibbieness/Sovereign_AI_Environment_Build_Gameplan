"""
ML-Powered Operating System & Filesystem
Part 1: Foundation & Core Engine

This module provides the foundational components:
- Filesystem abstraction layer
- ML agent orchestration framework
- Event bus and messaging system
- Configuration management

Author: Shibbieness (Mark) with Claude
Version: 1.0.0
Date: 2026-03-24
"""

import os
import json
import uuid
import hashlib
import threading
import queue
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Set, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import shutil
import mimetypes
from collections import defaultdict


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class EventType(Enum):
    """Event types for the event bus system"""
    # Filesystem events
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    FILE_MOVED = "file_moved"
    DIR_CREATED = "dir_created"
    DIR_DELETED = "dir_deleted"
    
    # Agent events
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    AGENT_ERROR = "agent_error"
    AGENT_COMPLETED = "agent_completed"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_ERROR = "system_error"
    
    # Processing events
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_FAILED = "processing_failed"


class AgentState(Enum):
    """Agent execution states"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    COMPLETED = "completed"


class FileType(Enum):
    """File type classifications"""
    CODE = "code"
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    ARCHIVE = "archive"
    DATA = "data"
    EXECUTABLE = "executable"
    UNKNOWN = "unknown"


class Priority(Enum):
    """Task priority levels"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Event:
    """Event object for the event bus"""
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'data': self.data,
            'event_id': self.event_id
        }


@dataclass
class FileMetadata:
    """Metadata for filesystem items"""
    path: str
    name: str
    size: int
    created: datetime
    modified: datetime
    file_type: FileType
    mime_type: str
    hash: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            'path': self.path,
            'name': self.name,
            'size': self.size,
            'created': self.created.isoformat(),
            'modified': self.modified.isoformat(),
            'file_type': self.file_type.value,
            'mime_type': self.mime_type,
            'hash': self.hash,
            'tags': self.tags,
            'metadata': self.metadata
        }


@dataclass
class AgentTask:
    """Task for agent execution"""
    task_id: str
    agent_type: str
    target: str  # File or directory path
    priority: Priority = Priority.NORMAL
    params: Dict[str, Any] = field(default_factory=dict)
    created: datetime = field(default_factory=datetime.now)
    started: Optional[datetime] = None
    completed: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def __lt__(self, other):
        """Comparison for priority queue"""
        return self.priority.value < other.priority.value


@dataclass
class AgentConfig:
    """Configuration for an agent"""
    agent_id: str
    agent_type: str
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    max_concurrent: int = 1
    timeout: int = 300  # seconds


# ============================================================================
# CONFIGURATION MANAGER
# ============================================================================

class ConfigurationManager:
    """
    Manages application configuration with support for:
    - JSON-based configuration files
    - Environment variable overrides
    - Default values
    - Runtime updates
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.expanduser("~/.mlos/config.json")
        self.config: Dict[str, Any] = {}
        self.defaults: Dict[str, Any] = {
            'filesystem': {
                'root': os.path.expanduser("~/MLOSData"),
                'watch_enabled': True,
                'auto_organize': True,
                'max_file_size': 1024 * 1024 * 100,  # 100MB
            },
            'agents': {
                'max_concurrent': 4,
                'default_timeout': 300,
                'auto_start': True,
            },
            'ml': {
                'model_cache': os.path.expanduser("~/.mlos/models"),
                'use_gpu': False,
                'batch_size': 32,
            },
            'ui': {
                'theme': 'dark',
                'font_size': 12,
                'auto_refresh': True,
            },
            'logging': {
                'level': 'INFO',
                'file': os.path.expanduser("~/.mlos/logs/app.log"),
            }
        }
        self._lock = threading.Lock()
        self.load()
    
    def load(self):
        """Load configuration from file"""
        with self._lock:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r') as f:
                        self.config = json.load(f)
                    logger.info(f"Configuration loaded from {self.config_path}")
                except Exception as e:
                    logger.error(f"Error loading configuration: {e}")
                    self.config = {}
            else:
                self.config = {}
                logger.info("No configuration file found, using defaults")
            
            # Merge with defaults
            self._merge_defaults()
    
    def _merge_defaults(self):
        """Merge configuration with defaults"""
        def merge(target: Dict, source: Dict):
            for key, value in source.items():
                if key not in target:
                    target[key] = value
                elif isinstance(value, dict) and isinstance(target[key], dict):
                    merge(target[key], value)
        
        merge(self.config, self.defaults)
    
    def save(self):
        """Save configuration to file"""
        with self._lock:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            try:
                with open(self.config_path, 'w') as f:
                    json.dump(self.config, f, indent=2)
                logger.info(f"Configuration saved to {self.config_path}")
            except Exception as e:
                logger.error(f"Error saving configuration: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        Example: config.get('filesystem.root')
        """
        with self._lock:
            keys = key_path.split('.')
            value = self.config
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            return value
    
    def set(self, key_path: str, value: Any):
        """
        Set configuration value using dot notation
        Example: config.set('filesystem.root', '/path/to/data')
        """
        with self._lock:
            keys = key_path.split('.')
            target = self.config
            for key in keys[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]
            target[keys[-1]] = value
    
    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration"""
        with self._lock:
            return self.config.copy()


# ============================================================================
# EVENT BUS
# ============================================================================

class EventBus:
    """
    Thread-safe event bus for inter-component communication
    Supports:
    - Event publishing and subscription
    - Priority-based event handling
    - Event filtering
    - Async event processing
    """
    
    def __init__(self, max_queue_size: int = 1000):
        self.subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self.event_queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=max_queue_size)
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.event_history: List[Event] = []
        self.max_history = 1000
    
    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        """Subscribe to an event type"""
        with self._lock:
            if callback not in self.subscribers[event_type]:
                self.subscribers[event_type].append(callback)
                logger.debug(f"Subscribed to {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        """Unsubscribe from an event type"""
        with self._lock:
            if callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from {event_type.value}")
    
    def publish(self, event: Event, priority: int = 5):
        """Publish an event to the bus"""
        try:
            self.event_queue.put((priority, event), block=False)
            logger.debug(f"Published event: {event.event_type.value}")
        except queue.Full:
            logger.warning("Event queue full, dropping event")
    
    def start(self):
        """Start the event processing worker"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._process_events, daemon=True)
            self.worker_thread.start()
            logger.info("Event bus started")
    
    def stop(self):
        """Stop the event processing worker"""
        if self.running:
            self.running = False
            if self.worker_thread:
                self.worker_thread.join(timeout=5)
            logger.info("Event bus stopped")
    
    def _process_events(self):
        """Process events from the queue"""
        while self.running:
            try:
                priority, event = self.event_queue.get(timeout=0.1)
                self._dispatch_event(event)
                self._add_to_history(event)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    def _dispatch_event(self, event: Event):
        """Dispatch event to subscribers"""
        with self._lock:
            callbacks = self.subscribers.get(event.event_type, []).copy()
        
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")
    
    def _add_to_history(self, event: Event):
        """Add event to history"""
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)
    
    def get_history(self, event_type: Optional[EventType] = None, 
                    limit: int = 100) -> List[Event]:
        """Get event history, optionally filtered by type"""
        if event_type:
            return [e for e in self.event_history if e.event_type == event_type][-limit:]
        return self.event_history[-limit:]


# ============================================================================
# FILESYSTEM ABSTRACTION
# ============================================================================

class VirtualFilesystem:
    """
    Virtual filesystem abstraction layer
    Provides unified interface for file operations with:
    - Event emission on changes
    - Metadata tracking
    - Path normalization
    - Watch support
    """
    
    def __init__(self, root: str, event_bus: EventBus, config: ConfigurationManager):
        self.root = Path(root).resolve()
        self.event_bus = event_bus
        self.config = config
        self.metadata_cache: Dict[str, FileMetadata] = {}
        self._lock = threading.Lock()
        
        # Initialize root directory
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info(f"Filesystem initialized at {self.root}")
    
    def _normalize_path(self, path: Union[str, Path]) -> Path:
        """Normalize and validate path"""
        path = Path(path)
        if not path.is_absolute():
            path = self.root / path
        path = path.resolve()
        
        # Security check: ensure path is within root
        try:
            path.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Path {path} is outside filesystem root")
        
        return path
    
    def exists(self, path: Union[str, Path]) -> bool:
        """Check if path exists"""
        try:
            return self._normalize_path(path).exists()
        except ValueError:
            return False
    
    def is_file(self, path: Union[str, Path]) -> bool:
        """Check if path is a file"""
        try:
            return self._normalize_path(path).is_file()
        except ValueError:
            return False
    
    def is_dir(self, path: Union[str, Path]) -> bool:
        """Check if path is a directory"""
        try:
            return self._normalize_path(path).is_dir()
        except ValueError:
            return False
    
    def create_file(self, path: Union[str, Path], content: bytes = b"") -> Path:
        """Create a new file"""
        path = self._normalize_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            f.write(content)
        
        # Emit event
        self.event_bus.publish(Event(
            event_type=EventType.FILE_CREATED,
            source="filesystem",
            data={'path': str(path)}
        ))
        
        logger.info(f"Created file: {path}")
        return path
    
    def create_dir(self, path: Union[str, Path]) -> Path:
        """Create a new directory"""
        path = self._normalize_path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Emit event
        self.event_bus.publish(Event(
            event_type=EventType.DIR_CREATED,
            source="filesystem",
            data={'path': str(path)}
        ))
        
        logger.info(f"Created directory: {path}")
        return path
    
    def read_file(self, path: Union[str, Path]) -> bytes:
        """Read file contents"""
        path = self._normalize_path(path)
        with open(path, 'rb') as f:
            return f.read()
    
    def write_file(self, path: Union[str, Path], content: bytes):
        """Write content to file"""
        path = self._normalize_path(path)
        
        existed = path.exists()
        with open(path, 'wb') as f:
            f.write(content)
        
        # Emit event
        event_type = EventType.FILE_MODIFIED if existed else EventType.FILE_CREATED
        self.event_bus.publish(Event(
            event_type=event_type,
            source="filesystem",
            data={'path': str(path)}
        ))
        
        logger.info(f"Wrote to file: {path}")
    
    def delete(self, path: Union[str, Path]):
        """Delete file or directory"""
        path = self._normalize_path(path)
        
        if path.is_file():
            path.unlink()
            event_type = EventType.FILE_DELETED
        elif path.is_dir():
            shutil.rmtree(path)
            event_type = EventType.DIR_DELETED
        else:
            raise FileNotFoundError(f"Path not found: {path}")
        
        # Emit event
        self.event_bus.publish(Event(
            event_type=event_type,
            source="filesystem",
            data={'path': str(path)}
        ))
        
        logger.info(f"Deleted: {path}")
    
    def move(self, src: Union[str, Path], dst: Union[str, Path]) -> Path:
        """Move file or directory"""
        src = self._normalize_path(src)
        dst = self._normalize_path(dst)
        
        shutil.move(str(src), str(dst))
        
        # Emit event
        self.event_bus.publish(Event(
            event_type=EventType.FILE_MOVED,
            source="filesystem",
            data={'src': str(src), 'dst': str(dst)}
        ))
        
        logger.info(f"Moved {src} to {dst}")
        return dst
    
    def copy(self, src: Union[str, Path], dst: Union[str, Path]) -> Path:
        """Copy file or directory"""
        src = self._normalize_path(src)
        dst = self._normalize_path(dst)
        
        if src.is_file():
            shutil.copy2(str(src), str(dst))
        else:
            shutil.copytree(str(src), str(dst))
        
        logger.info(f"Copied {src} to {dst}")
        return dst
    
    def list_dir(self, path: Union[str, Path] = "") -> List[Path]:
        """List directory contents"""
        if not path:
            path = self.root
        else:
            path = self._normalize_path(path)
        
        return sorted(list(path.iterdir()))
    
    def walk(self, path: Union[str, Path] = "") -> List[Path]:
        """Recursively walk directory tree"""
        if not path:
            path = self.root
        else:
            path = self._normalize_path(path)
        
        result = []
        for item in path.rglob("*"):
            result.append(item)
        return result
    
    def get_metadata(self, path: Union[str, Path]) -> FileMetadata:
        """Get file metadata"""
        path = self._normalize_path(path)
        path_str = str(path)
        
        # Check cache
        with self._lock:
            if path_str in self.metadata_cache:
                cached = self.metadata_cache[path_str]
                # Verify cache is still valid
                if cached.modified == datetime.fromtimestamp(path.stat().st_mtime):
                    return cached
        
        # Generate metadata
        stat = path.stat()
        mime_type, _ = mimetypes.guess_type(str(path))
        mime_type = mime_type or "application/octet-stream"
        
        # Determine file type
        file_type = self._classify_file_type(path, mime_type)
        
        # Calculate hash for files
        file_hash = ""
        if path.is_file() and stat.st_size < self.config.get('filesystem.max_file_size', 100 * 1024 * 1024):
            file_hash = self._calculate_hash(path)
        
        metadata = FileMetadata(
            path=path_str,
            name=path.name,
            size=stat.st_size,
            created=datetime.fromtimestamp(stat.st_ctime),
            modified=datetime.fromtimestamp(stat.st_mtime),
            file_type=file_type,
            mime_type=mime_type,
            hash=file_hash
        )
        
        # Update cache
        with self._lock:
            self.metadata_cache[path_str] = metadata
        
        return metadata
    
    def _classify_file_type(self, path: Path, mime_type: str) -> FileType:
        """Classify file type based on extension and MIME type"""
        ext = path.suffix.lower()
        
        # Code files
        code_extensions = {
            '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp',
            '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala'
        }
        if ext in code_extensions:
            return FileType.CODE
        
        # Documents
        if mime_type.startswith('text/') or ext in {'.txt', '.md', '.pdf', '.doc', '.docx'}:
            return FileType.DOCUMENT
        
        # Images
        if mime_type.startswith('image/'):
            return FileType.IMAGE
        
        # Video
        if mime_type.startswith('video/'):
            return FileType.VIDEO
        
        # Audio
        if mime_type.startswith('audio/'):
            return FileType.AUDIO
        
        # Archives
        if ext in {'.zip', '.tar', '.gz', '.bz2', '.7z', '.rar'}:
            return FileType.ARCHIVE
        
        # Data files
        if ext in {'.json', '.xml', '.csv', '.yaml', '.yml', '.sql'}:
            return FileType.DATA
        
        # Executables
        if ext in {'.exe', '.dll', '.so', '.dylib', '.app'}:
            return FileType.EXECUTABLE
        
        return FileType.UNKNOWN
    
    def _calculate_hash(self, path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


# ============================================================================
# AGENT ORCHESTRATOR
# ============================================================================

class AgentOrchestrator:
    """
    Orchestrates ML agent execution
    Features:
    - Task queue management
    - Agent lifecycle control
    - Concurrent execution limits
    - Task prioritization
    """
    
    def __init__(self, event_bus: EventBus, config: ConfigurationManager):
        self.event_bus = event_bus
        self.config = config
        self.agents: Dict[str, 'BaseAgent'] = {}
        self.task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.active_tasks: Dict[str, AgentTask] = {}
        self.completed_tasks: List[AgentTask] = []
        self.running = False
        self.workers: List[threading.Thread] = []
        self._lock = threading.Lock()
        
        # Get max concurrent from config
        self.max_concurrent = config.get('agents.max_concurrent', 4)
    
    def register_agent(self, agent: 'BaseAgent'):
        """Register an agent"""
        with self._lock:
            self.agents[agent.agent_id] = agent
            logger.info(f"Registered agent: {agent.agent_id} ({agent.agent_type})")
    
    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        with self._lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                logger.info(f"Unregistered agent: {agent_id}")
    
    def submit_task(self, task: AgentTask):
        """Submit a task for execution"""
        self.task_queue.put(task)
        logger.info(f"Submitted task: {task.task_id} for {task.agent_type}")
    
    def start(self):
        """Start the orchestrator workers"""
        if not self.running:
            self.running = True
            for i in range(self.max_concurrent):
                worker = threading.Thread(target=self._worker, daemon=True, name=f"AgentWorker-{i}")
                worker.start()
                self.workers.append(worker)
            logger.info(f"Agent orchestrator started with {self.max_concurrent} workers")
    
    def stop(self):
        """Stop the orchestrator"""
        if self.running:
            self.running = False
            for worker in self.workers:
                worker.join(timeout=5)
            self.workers.clear()
            logger.info("Agent orchestrator stopped")
    
    def _worker(self):
        """Worker thread for processing tasks"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=0.1)
                self._execute_task(task)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def _execute_task(self, task: AgentTask):
        """Execute a task"""
        task.started = datetime.now()
        
        with self._lock:
            self.active_tasks[task.task_id] = task
        
        # Emit start event
        self.event_bus.publish(Event(
            event_type=EventType.PROCESSING_STARTED,
            source="orchestrator",
            data={'task_id': task.task_id, 'agent_type': task.agent_type}
        ))
        
        try:
            # Find appropriate agent
            agent = self._find_agent(task.agent_type)
            if not agent:
                raise ValueError(f"No agent found for type: {task.agent_type}")
            
            # Execute task
            result = agent.execute(task)
            task.result = result
            task.completed = datetime.now()
            
            # Emit completion event
            self.event_bus.publish(Event(
                event_type=EventType.PROCESSING_COMPLETED,
                source="orchestrator",
                data={'task_id': task.task_id, 'result': result}
            ))
            
            logger.info(f"Task completed: {task.task_id}")
            
        except Exception as e:
            task.error = str(e)
            task.completed = datetime.now()
            
            # Emit error event
            self.event_bus.publish(Event(
                event_type=EventType.PROCESSING_FAILED,
                source="orchestrator",
                data={'task_id': task.task_id, 'error': str(e)}
            ))
            
            logger.error(f"Task failed: {task.task_id} - {e}")
        
        finally:
            # Move to completed tasks
            with self._lock:
                if task.task_id in self.active_tasks:
                    del self.active_tasks[task.task_id]
                self.completed_tasks.append(task)
                
                # Keep only last 1000 completed tasks
                if len(self.completed_tasks) > 1000:
                    self.completed_tasks.pop(0)
    
    def _find_agent(self, agent_type: str) -> Optional['BaseAgent']:
        """Find an available agent of the specified type"""
        with self._lock:
            for agent in self.agents.values():
                if agent.agent_type == agent_type and agent.state == AgentState.IDLE:
                    return agent
        return None
    
    def get_task_status(self, task_id: str) -> Optional[AgentTask]:
        """Get status of a task"""
        with self._lock:
            if task_id in self.active_tasks:
                return self.active_tasks[task_id]
            for task in self.completed_tasks:
                if task.task_id == task_id:
                    return task
        return None
    
    def get_active_tasks(self) -> List[AgentTask]:
        """Get all active tasks"""
        with self._lock:
            return list(self.active_tasks.values())
    
    def get_completed_tasks(self, limit: int = 100) -> List[AgentTask]:
        """Get completed tasks"""
        with self._lock:
            return self.completed_tasks[-limit:]


# ============================================================================
# BASE AGENT CLASS
# ============================================================================

class BaseAgent(ABC):
    """
    Abstract base class for all ML agents
    Provides common functionality and interface
    """
    
    def __init__(self, agent_id: str, agent_type: str, config: AgentConfig):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.config = config
        self.state = AgentState.IDLE
        self._lock = threading.Lock()
    
    @abstractmethod
    def execute(self, task: AgentTask) -> Any:
        """Execute a task (must be implemented by subclasses)"""
        pass
    
    def set_state(self, state: AgentState):
        """Set agent state"""
        with self._lock:
            self.state = state
    
    def get_state(self) -> AgentState:
        """Get agent state"""
        with self._lock:
            return self.state
    
    def can_execute(self) -> bool:
        """Check if agent can execute a task"""
        return self.state == AgentState.IDLE and self.config.enabled


# ============================================================================
# MAIN APPLICATION CLASS
# ============================================================================

class MLOSCore:
    """
    Core application class that ties everything together
    """
    
    def __init__(self, config_path: Optional[str] = None):
        # Initialize components
        self.config = ConfigurationManager(config_path)
        self.event_bus = EventBus()
        
        filesystem_root = self.config.get('filesystem.root')
        self.filesystem = VirtualFilesystem(filesystem_root, self.event_bus, self.config)
        
        self.orchestrator = AgentOrchestrator(self.event_bus, self.config)
        
        self.running = False
        logger.info("MLOS Core initialized")
    
    def start(self):
        """Start all core services"""
        if not self.running:
            self.event_bus.start()
            self.orchestrator.start()
            self.running = True
            
            # Emit startup event
            self.event_bus.publish(Event(
                event_type=EventType.SYSTEM_STARTUP,
                source="core",
                data={'timestamp': datetime.now().isoformat()}
            ))
            
            logger.info("MLOS Core started")
    
    def stop(self):
        """Stop all core services"""
        if self.running:
            # Emit shutdown event
            self.event_bus.publish(Event(
                event_type=EventType.SYSTEM_SHUTDOWN,
                source="core",
                data={'timestamp': datetime.now().isoformat()}
            ))
            
            self.orchestrator.stop()
            self.event_bus.stop()
            self.config.save()
            self.running = False
            
            logger.info("MLOS Core stopped")
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_size(size: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def is_binary_file(path: Path) -> bool:
    """Check if file is binary"""
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192)
            if b'\0' in chunk:
                return True
            # Check for high ratio of non-text bytes
            text_chars = bytes(range(32, 127)) + b'\n\r\t\b'
            non_text = sum(1 for byte in chunk if byte not in text_chars)
            return non_text / len(chunk) > 0.3
    except:
        return True


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    'EventType', 'AgentState', 'FileType', 'Priority',
    'Event', 'FileMetadata', 'AgentTask', 'AgentConfig',
    'ConfigurationManager', 'EventBus', 'VirtualFilesystem',
    'AgentOrchestrator', 'BaseAgent', 'MLOSCore',
    'format_size', 'is_binary_file'
]


# ============================================================================
# MAIN ENTRY POINT (for testing)
# ============================================================================

if __name__ == "__main__":
    # Simple test of the core system
    print("ML-OS Foundation & Core Engine - Part 1")
    print("=" * 60)
    
    with MLOSCore() as core:
        print(f"System root: {core.filesystem.root}")
        print(f"Configuration loaded: {len(core.config.get_all())} sections")
        print(f"Event bus running: {core.event_bus.running}")
        print(f"Orchestrator workers: {len(core.orchestrator.workers)}")
        
        # Test file operations
        test_file = core.filesystem.create_file("test.txt", b"Hello, ML-OS!")
        print(f"\nCreated test file: {test_file}")
        
        metadata = core.filesystem.get_metadata(test_file)
        print(f"File type: {metadata.file_type.value}")
        print(f"MIME type: {metadata.mime_type}")
        print(f"Size: {format_size(metadata.size)}")
        
        # Test event history
        print(f"\nEvent history ({len(core.event_bus.get_history())} events):")
        for event in core.event_bus.get_history(limit=5):
            print(f"  - {event.event_type.value} at {event.timestamp}")
        
        print("\nSystem test completed successfully!")
