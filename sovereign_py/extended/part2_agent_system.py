"""
ML-Powered Operating System & Filesystem
Part 2: ML Agent System

This module provides the ML agent implementations:
- Concrete agent classes for various tasks
- Agent chain execution
- Inter-agent communication
- Agent result caching
- Agent dependency resolution

Author: Shibbieness (Mark) with Claude
Version: 1.0.0
Date: 2026-03-24
"""

import os
import json
import time
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from collections import deque
import hashlib

# Import from Part 1
from part1_foundation import (
    BaseAgent, AgentTask, AgentConfig, AgentState, Event, EventType,
    FileMetadata, FileType, Priority, EventBus, ConfigurationManager,
    VirtualFilesystem, logger
)


# ============================================================================
# AGENT RESULT CACHING
# ============================================================================

@dataclass
class AgentResult:
    """Cached result from agent execution"""
    task_id: str
    agent_type: str
    target: str
    result: Any
    timestamp: datetime
    params_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self, ttl: int = 3600) -> bool:
        """Check if result has expired"""
        return (datetime.now() - self.timestamp).total_seconds() > ttl


class ResultCache:
    """
    Cache for agent execution results
    Features:
    - TTL-based expiration
    - Parameter-aware caching
    - Memory limits
    - Cache invalidation
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.cache: Dict[str, AgentResult] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
    
    def _generate_key(self, agent_type: str, target: str, params: Dict[str, Any]) -> str:
        """Generate cache key"""
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.sha256(params_str.encode()).hexdigest()
        return f"{agent_type}:{target}:{params_hash}"
    
    def get(self, agent_type: str, target: str, params: Dict[str, Any]) -> Optional[AgentResult]:
        """Get cached result if available and not expired"""
        key = self._generate_key(agent_type, target, params)
        
        with self._lock:
            if key in self.cache:
                result = self.cache[key]
                if not result.is_expired(self.default_ttl):
                    logger.debug(f"Cache hit: {key}")
                    return result
                else:
                    # Remove expired entry
                    del self.cache[key]
                    logger.debug(f"Cache expired: {key}")
        
        return None
    
    def put(self, agent_type: str, target: str, params: Dict[str, Any], 
            result: Any, task_id: str):
        """Store result in cache"""
        key = self._generate_key(agent_type, target, params)
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.sha256(params_str.encode()).hexdigest()
        
        cached_result = AgentResult(
            task_id=task_id,
            agent_type=agent_type,
            target=target,
            result=result,
            timestamp=datetime.now(),
            params_hash=params_hash
        )
        
        with self._lock:
            self.cache[key] = cached_result
            
            # Enforce size limit (LRU-style)
            if len(self.cache) > self.max_size:
                # Remove oldest entry
                oldest_key = min(self.cache.keys(), 
                               key=lambda k: self.cache[k].timestamp)
                del self.cache[oldest_key]
        
        logger.debug(f"Cache put: {key}")
    
    def invalidate(self, target: str):
        """Invalidate all cache entries for a target"""
        with self._lock:
            keys_to_remove = [k for k, v in self.cache.items() if v.target == target]
            for key in keys_to_remove:
                del self.cache[key]
        
        logger.debug(f"Cache invalidated for: {target}")
    
    def clear(self):
        """Clear entire cache"""
        with self._lock:
            self.cache.clear()
        logger.debug("Cache cleared")


# ============================================================================
# AGENT CHAIN EXECUTION
# ============================================================================

@dataclass
class AgentChainStep:
    """Single step in an agent chain"""
    agent_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)  # Indices of dependencies
    optional: bool = False  # Continue chain even if this step fails


class AgentChain:
    """
    Defines a sequence of agent executions
    Features:
    - Dependency resolution
    - Result passing between agents
    - Partial execution on failure
    - Result aggregation
    """
    
    def __init__(self, chain_id: str, target: str, steps: List[AgentChainStep]):
        self.chain_id = chain_id
        self.target = target
        self.steps = steps
        self.results: Dict[int, Any] = {}
        self.errors: Dict[int, str] = {}
        self.completed_steps: Set[int] = set()
        self.failed_steps: Set[int] = set()
    
    def get_next_step(self) -> Optional[Tuple[int, AgentChainStep]]:
        """Get next executable step based on dependencies"""
        for i, step in enumerate(self.steps):
            # Skip if already completed or failed
            if i in self.completed_steps or i in self.failed_steps:
                continue
            
            # Check dependencies
            deps_met = all(dep in self.completed_steps for dep in step.depends_on)
            if deps_met:
                return (i, step)
        
        return None
    
    def record_success(self, step_index: int, result: Any):
        """Record successful step execution"""
        self.completed_steps.add(step_index)
        self.results[step_index] = result
    
    def record_failure(self, step_index: int, error: str):
        """Record failed step execution"""
        self.failed_steps.add(step_index)
        self.errors[step_index] = error
    
    def is_complete(self) -> bool:
        """Check if chain execution is complete"""
        return len(self.completed_steps) + len(self.failed_steps) == len(self.steps)
    
    def get_final_result(self) -> Dict[str, Any]:
        """Get aggregated results from chain"""
        return {
            'chain_id': self.chain_id,
            'target': self.target,
            'completed': list(self.completed_steps),
            'failed': list(self.failed_steps),
            'results': self.results,
            'errors': self.errors
        }


class ChainExecutor:
    """
    Executes agent chains
    """
    
    def __init__(self, orchestrator, event_bus: EventBus):
        self.orchestrator = orchestrator
        self.event_bus = event_bus
        self.active_chains: Dict[str, AgentChain] = {}
        self._lock = threading.Lock()
    
    def execute_chain(self, chain: AgentChain) -> Dict[str, Any]:
        """Execute an agent chain"""
        with self._lock:
            self.active_chains[chain.chain_id] = chain
        
        logger.info(f"Starting chain execution: {chain.chain_id}")
        
        while not chain.is_complete():
            next_step = chain.get_next_step()
            if not next_step:
                # No more executable steps (likely due to failed dependencies)
                break
            
            step_index, step = next_step
            
            try:
                # Create task for this step
                task = AgentTask(
                    task_id=f"{chain.chain_id}_step_{step_index}",
                    agent_type=step.agent_type,
                    target=chain.target,
                    params=step.params,
                    priority=Priority.NORMAL
                )
                
                # Execute synchronously (for chain execution)
                self.orchestrator.submit_task(task)
                
                # Wait for completion
                result = self._wait_for_task(task.task_id, timeout=300)
                
                if result and not result.error:
                    chain.record_success(step_index, result.result)
                else:
                    error = result.error if result else "Task timeout"
                    if step.optional:
                        logger.warning(f"Optional step failed: {error}")
                        chain.record_failure(step_index, error)
                    else:
                        logger.error(f"Required step failed: {error}")
                        chain.record_failure(step_index, error)
                        # Stop chain on required step failure
                        break
                
            except Exception as e:
                logger.error(f"Chain step error: {e}")
                chain.record_failure(step_index, str(e))
                if not step.optional:
                    break
        
        final_result = chain.get_final_result()
        
        with self._lock:
            if chain.chain_id in self.active_chains:
                del self.active_chains[chain.chain_id]
        
        logger.info(f"Chain execution completed: {chain.chain_id}")
        return final_result
    
    def _wait_for_task(self, task_id: str, timeout: int = 300) -> Optional[AgentTask]:
        """Wait for task completion"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            task = self.orchestrator.get_task_status(task_id)
            if task and task.completed:
                return task
            time.sleep(0.1)
        return None


# ============================================================================
# CONCRETE AGENT IMPLEMENTATIONS
# ============================================================================

class FileAnalyzerAgent(BaseAgent):
    """
    Analyzes files and extracts metadata
    - Content type detection
    - Encoding detection
    - Basic statistics
    """
    
    def __init__(self, agent_id: str, config: AgentConfig, filesystem: VirtualFilesystem):
        super().__init__(agent_id, "file_analyzer", config)
        self.filesystem = filesystem
    
    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Execute file analysis"""
        self.set_state(AgentState.RUNNING)
        
        try:
            path = task.target
            if not self.filesystem.exists(path):
                raise FileNotFoundError(f"File not found: {path}")
            
            metadata = self.filesystem.get_metadata(path)
            result = {
                'path': path,
                'name': metadata.name,
                'size': metadata.size,
                'type': metadata.file_type.value,
                'mime_type': metadata.mime_type,
                'hash': metadata.hash,
                'created': metadata.created.isoformat(),
                'modified': metadata.modified.isoformat(),
            }
            
            # Add file-specific analysis
            if self.filesystem.is_file(path):
                if metadata.file_type == FileType.CODE:
                    result['analysis'] = self._analyze_code_file(path)
                elif metadata.file_type == FileType.DOCUMENT:
                    result['analysis'] = self._analyze_document(path)
                elif metadata.file_type == FileType.DATA:
                    result['analysis'] = self._analyze_data_file(path)
            
            self.set_state(AgentState.COMPLETED)
            return result
            
        except Exception as e:
            self.set_state(AgentState.ERROR)
            raise
    
    def _analyze_code_file(self, path: str) -> Dict[str, Any]:
        """Analyze code file"""
        try:
            content = self.filesystem.read_file(path).decode('utf-8', errors='ignore')
            lines = content.split('\n')
            
            return {
                'lines': len(lines),
                'chars': len(content),
                'blank_lines': sum(1 for line in lines if not line.strip()),
                'comment_lines': self._count_comment_lines(lines, path),
            }
        except:
            return {'error': 'Could not analyze code file'}
    
    def _analyze_document(self, path: str) -> Dict[str, Any]:
        """Analyze document file"""
        try:
            content = self.filesystem.read_file(path).decode('utf-8', errors='ignore')
            words = content.split()
            
            return {
                'words': len(words),
                'chars': len(content),
                'lines': len(content.split('\n')),
            }
        except:
            return {'error': 'Could not analyze document'}
    
    def _analyze_data_file(self, path: str) -> Dict[str, Any]:
        """Analyze data file"""
        try:
            content = self.filesystem.read_file(path).decode('utf-8', errors='ignore')
            
            # Try to parse as JSON
            if path.endswith('.json'):
                data = json.loads(content)
                return {
                    'format': 'json',
                    'type': type(data).__name__,
                    'size': len(str(data))
                }
            
            # Try to parse as CSV
            elif path.endswith('.csv'):
                lines = content.split('\n')
                return {
                    'format': 'csv',
                    'rows': len(lines),
                    'estimated_columns': len(lines[0].split(',')) if lines else 0
                }
            
            return {'format': 'unknown'}
        except:
            return {'error': 'Could not analyze data file'}
    
    def _count_comment_lines(self, lines: List[str], path: str) -> int:
        """Count comment lines based on file extension"""
        ext = os.path.splitext(path)[1].lower()
        count = 0
        
        # Python-style comments
        if ext in ['.py', '.sh', '.yaml', '.yml']:
            count = sum(1 for line in lines if line.strip().startswith('#'))
        
        # C-style comments
        elif ext in ['.c', '.cpp', '.java', '.js', '.ts', '.cs', '.go']:
            count = sum(1 for line in lines if line.strip().startswith('//'))
        
        return count


class ContentExtractorAgent(BaseAgent):
    """
    Extracts content from various file types
    - Text extraction
    - Structure detection
    - Key information extraction
    """
    
    def __init__(self, agent_id: str, config: AgentConfig, filesystem: VirtualFilesystem):
        super().__init__(agent_id, "content_extractor", config)
        self.filesystem = filesystem
    
    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Execute content extraction"""
        self.set_state(AgentState.RUNNING)
        
        try:
            path = task.target
            metadata = self.filesystem.get_metadata(path)
            
            result = {
                'path': path,
                'content': None,
                'structure': None,
                'key_info': {}
            }
            
            # Extract based on file type
            if metadata.file_type == FileType.CODE:
                result['content'] = self._extract_code_content(path)
            elif metadata.file_type == FileType.DOCUMENT:
                result['content'] = self._extract_document_content(path)
            elif metadata.file_type == FileType.DATA:
                result['content'] = self._extract_data_content(path)
            
            self.set_state(AgentState.COMPLETED)
            return result
            
        except Exception as e:
            self.set_state(AgentState.ERROR)
            raise
    
    def _extract_code_content(self, path: str) -> Dict[str, Any]:
        """Extract code content"""
        content = self.filesystem.read_file(path).decode('utf-8', errors='ignore')
        
        # Extract imports/includes
        imports = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                imports.append(line)
            elif line.startswith('#include'):
                imports.append(line)
        
        # Extract function/class definitions (simple heuristic)
        definitions = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('def ') or line.startswith('class '):
                definitions.append(line.split(':')[0])
        
        return {
            'imports': imports,
            'definitions': definitions,
            'text': content[:1000]  # First 1000 chars
        }
    
    def _extract_document_content(self, path: str) -> Dict[str, Any]:
        """Extract document content"""
        content = self.filesystem.read_file(path).decode('utf-8', errors='ignore')
        
        # Extract headings (markdown-style)
        headings = []
        for line in content.split('\n'):
            if line.startswith('#'):
                headings.append(line)
        
        return {
            'headings': headings,
            'text': content[:2000],  # First 2000 chars
            'preview': content[:500]
        }
    
    def _extract_data_content(self, path: str) -> Dict[str, Any]:
        """Extract data content"""
        content = self.filesystem.read_file(path).decode('utf-8', errors='ignore')
        
        # Try JSON
        if path.endswith('.json'):
            try:
                data = json.loads(content)
                return {
                    'format': 'json',
                    'preview': json.dumps(data, indent=2)[:1000]
                }
            except:
                pass
        
        return {
            'format': 'text',
            'preview': content[:1000]
        }


class RelationshipDetectorAgent(BaseAgent):
    """
    Detects relationships between files
    - Similar content detection
    - Import/dependency detection
    - Naming pattern detection
    """
    
    def __init__(self, agent_id: str, config: AgentConfig, filesystem: VirtualFilesystem):
        super().__init__(agent_id, "relationship_detector", config)
        self.filesystem = filesystem
    
    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Execute relationship detection"""
        self.set_state(AgentState.RUNNING)
        
        try:
            path = task.target
            related_files = self._find_related_files(path)
            
            result = {
                'path': path,
                'related_files': related_files,
                'relationship_types': self._classify_relationships(path, related_files)
            }
            
            self.set_state(AgentState.COMPLETED)
            return result
            
        except Exception as e:
            self.set_state(AgentState.ERROR)
            raise
    
    def _find_related_files(self, path: str) -> List[str]:
        """Find files related to the target"""
        from pathlib import Path
        
        target_path = Path(path)
        target_dir = target_path.parent
        target_name = target_path.stem
        target_ext = target_path.suffix
        
        related = []
        
        # Same directory
        for file in self.filesystem.list_dir(str(target_dir)):
            if file.is_file() and str(file) != path:
                # Same base name
                if file.stem == target_name:
                    related.append(str(file))
                # Similar name
                elif target_name in file.stem or file.stem in target_name:
                    related.append(str(file))
        
        return related[:10]  # Limit to 10 related files
    
    def _classify_relationships(self, path: str, related_files: List[str]) -> Dict[str, List[str]]:
        """Classify relationship types"""
        from pathlib import Path
        
        relationships = {
            'same_name_different_ext': [],
            'similar_name': [],
            'same_directory': []
        }
        
        target_path = Path(path)
        target_name = target_path.stem
        
        for related in related_files:
            related_path = Path(related)
            related_name = related_path.stem
            
            if related_name == target_name:
                relationships['same_name_different_ext'].append(related)
            elif target_name in related_name or related_name in target_name:
                relationships['similar_name'].append(related)
            else:
                relationships['same_directory'].append(related)
        
        return relationships


class TagGeneratorAgent(BaseAgent):
    """
    Generates tags for files based on content and context
    - Automatic tag extraction
    - Category detection
    - Keyword extraction
    """
    
    def __init__(self, agent_id: str, config: AgentConfig, filesystem: VirtualFilesystem):
        super().__init__(agent_id, "tag_generator", config)
        self.filesystem = filesystem
    
    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Execute tag generation"""
        self.set_state(AgentState.RUNNING)
        
        try:
            path = task.target
            metadata = self.filesystem.get_metadata(path)
            
            tags = set()
            
            # Add file type tag
            tags.add(metadata.file_type.value)
            
            # Add extension tag
            from pathlib import Path
            ext = Path(path).suffix.lower()
            if ext:
                tags.add(f"ext:{ext[1:]}")
            
            # Add size category
            if metadata.size < 1024:
                tags.add("size:tiny")
            elif metadata.size < 1024 * 1024:
                tags.add("size:small")
            elif metadata.size < 10 * 1024 * 1024:
                tags.add("size:medium")
            else:
                tags.add("size:large")
            
            # Content-based tags
            if metadata.file_type == FileType.CODE:
                tags.update(self._generate_code_tags(path))
            elif metadata.file_type == FileType.DOCUMENT:
                tags.update(self._generate_document_tags(path))
            
            result = {
                'path': path,
                'tags': sorted(list(tags))
            }
            
            self.set_state(AgentState.COMPLETED)
            return result
            
        except Exception as e:
            self.set_state(AgentState.ERROR)
            raise
    
    def _generate_code_tags(self, path: str) -> Set[str]:
        """Generate tags for code files"""
        tags = set()
        
        try:
            content = self.filesystem.read_file(path).decode('utf-8', errors='ignore')
            lower_content = content.lower()
            
            # Language detection
            if 'import ' in content or 'def ' in content:
                tags.add('lang:python')
            if 'function ' in content or 'const ' in content:
                tags.add('lang:javascript')
            if '#include' in content:
                tags.add('lang:c')
            
            # Framework detection
            if 'react' in lower_content or 'jsx' in lower_content:
                tags.add('framework:react')
            if 'django' in lower_content:
                tags.add('framework:django')
            if 'flask' in lower_content:
                tags.add('framework:flask')
            
            # Purpose detection
            if 'test' in lower_content or 'assert' in lower_content:
                tags.add('purpose:testing')
            if 'main' in lower_content:
                tags.add('purpose:entry')
            if 'config' in lower_content:
                tags.add('purpose:config')
            
        except:
            pass
        
        return tags
    
    def _generate_document_tags(self, path: str) -> Set[str]:
        """Generate tags for document files"""
        tags = set()
        
        try:
            content = self.filesystem.read_file(path).decode('utf-8', errors='ignore')
            lower_content = content.lower()
            
            # Format detection
            if path.endswith('.md'):
                tags.add('format:markdown')
            if path.endswith('.txt'):
                tags.add('format:text')
            
            # Content type detection
            if 'readme' in lower_content:
                tags.add('type:readme')
            if 'license' in lower_content:
                tags.add('type:license')
            if 'todo' in lower_content:
                tags.add('type:todo')
            
        except:
            pass
        
        return tags


class DuplicateDetectorAgent(BaseAgent):
    """
    Detects duplicate and similar files
    - Hash-based duplicate detection
    - Fuzzy similarity detection
    - Size-based grouping
    """
    
    def __init__(self, agent_id: str, config: AgentConfig, filesystem: VirtualFilesystem):
        super().__init__(agent_id, "duplicate_detector", config)
        self.filesystem = filesystem
    
    def execute(self, task: AgentTask) -> Dict[str, Any]:
        """Execute duplicate detection"""
        self.set_state(AgentState.RUNNING)
        
        try:
            path = task.target
            metadata = self.filesystem.get_metadata(path)
            
            duplicates = []
            similar = []
            
            # Find files with same hash
            if metadata.hash:
                duplicates = self._find_by_hash(metadata.hash, path)
            
            # Find files with similar size
            similar = self._find_similar_size(metadata.size, path)
            
            result = {
                'path': path,
                'exact_duplicates': duplicates,
                'similar_files': similar
            }
            
            self.set_state(AgentState.COMPLETED)
            return result
            
        except Exception as e:
            self.set_state(AgentState.ERROR)
            raise
    
    def _find_by_hash(self, file_hash: str, exclude_path: str) -> List[str]:
        """Find files with matching hash"""
        matches = []
        
        try:
            for file_path in self.filesystem.walk():
                if str(file_path) != exclude_path and file_path.is_file():
                    metadata = self.filesystem.get_metadata(str(file_path))
                    if metadata.hash == file_hash:
                        matches.append(str(file_path))
        except:
            pass
        
        return matches[:10]  # Limit results
    
    def _find_similar_size(self, size: int, exclude_path: str) -> List[str]:
        """Find files with similar size (within 10%)"""
        matches = []
        tolerance = size * 0.1
        
        try:
            for file_path in self.filesystem.walk():
                if str(file_path) != exclude_path and file_path.is_file():
                    metadata = self.filesystem.get_metadata(str(file_path))
                    if abs(metadata.size - size) < tolerance:
                        matches.append(str(file_path))
        except:
            pass
        
        return matches[:10]  # Limit results


# ============================================================================
# AGENT FACTORY
# ============================================================================

class AgentFactory:
    """
    Factory for creating agent instances
    """
    
    def __init__(self, filesystem: VirtualFilesystem, config: ConfigurationManager):
        self.filesystem = filesystem
        self.config = config
        self._agent_classes = {
            'file_analyzer': FileAnalyzerAgent,
            'content_extractor': ContentExtractorAgent,
            'relationship_detector': RelationshipDetectorAgent,
            'tag_generator': TagGeneratorAgent,
            'duplicate_detector': DuplicateDetectorAgent,
        }
    
    def create_agent(self, agent_type: str, agent_id: Optional[str] = None) -> BaseAgent:
        """Create an agent instance"""
        if agent_type not in self._agent_classes:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        if not agent_id:
            import uuid
            agent_id = f"{agent_type}_{uuid.uuid4().hex[:8]}"
        
        agent_config = AgentConfig(
            agent_id=agent_id,
            agent_type=agent_type,
            enabled=True,
            config={},
            max_concurrent=1,
            timeout=self.config.get('agents.default_timeout', 300)
        )
        
        agent_class = self._agent_classes[agent_type]
        return agent_class(agent_id, agent_config, self.filesystem)
    
    def get_available_agent_types(self) -> List[str]:
        """Get list of available agent types"""
        return list(self._agent_classes.keys())


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    'AgentResult', 'ResultCache',
    'AgentChainStep', 'AgentChain', 'ChainExecutor',
    'FileAnalyzerAgent', 'ContentExtractorAgent', 'RelationshipDetectorAgent',
    'TagGeneratorAgent', 'DuplicateDetectorAgent',
    'AgentFactory'
]


# ============================================================================
# MAIN ENTRY POINT (for testing)
# ============================================================================

if __name__ == "__main__":
    from part1_foundation import MLOSCore
    
    print("ML-OS Agent System - Part 2")
    print("=" * 60)
    
    with MLOSCore() as core:
        # Create agent factory
        factory = AgentFactory(core.filesystem, core.config)
        
        print(f"Available agent types: {factory.get_available_agent_types()}")
        
        # Create test file
        test_file = core.filesystem.create_file(
            "test_code.py",
            b"import os\nimport sys\n\ndef hello():\n    print('Hello, World!')\n"
        )
        
        print(f"\nCreated test file: {test_file}")
        
        # Create and register agents
        analyzer = factory.create_agent('file_analyzer')
        core.orchestrator.register_agent(analyzer)
        
        extractor = factory.create_agent('content_extractor')
        core.orchestrator.register_agent(extractor)
        
        tag_gen = factory.create_agent('tag_generator')
        core.orchestrator.register_agent(tag_gen)
        
        print(f"Registered {len(core.orchestrator.agents)} agents")
        
        # Submit analysis task
        task = AgentTask(
            task_id="test_analysis",
            agent_type="file_analyzer",
            target=str(test_file),
            priority=Priority.HIGH
        )
        
        core.orchestrator.submit_task(task)
        print(f"\nSubmitted task: {task.task_id}")
        
        # Wait for completion
        time.sleep(2)
        
        result = core.orchestrator.get_task_status(task.task_id)
        if result and result.completed:
            print(f"\nTask result:")
            print(json.dumps(result.result, indent=2))
        
        print("\nAgent system test completed!")
