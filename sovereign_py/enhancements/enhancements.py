"""
8 Logical Enhancements for ML Filesystem v1.8+

All features have configurable granularity (minimal → maximal).
Everything works independently and can be added/removed without breaking.

1. ChromaDB Integration
2. Training Block → Agent Binding
3. API Connection → Agent Integration
4. Auto-suggest Blocks
5. Coding Project → Training Block
6. VM → Coding Project
7. Webhook Support
8. Universal Search
"""

from typing import List, Dict, Optional, Any, Union
from datetime import datetime
import numpy as np

from core.config import Config
from core.database import db, File, TrainingBlock
from ml.local_backend import LocalMLBackend
from ml.training_blocks import TrainingBlockManager
from ml_runtime.graceful import CHROMADB_AVAILABLE, MLBackendUnavailable

if CHROMADB_AVAILABLE:
    import chromadb
    from chromadb.config import Settings


# ============================================================
# 1. CHROMADB INTEGRATION
# ============================================================

class ChromaDBManager:
    """
    Proper vector store integration.
    
    Granularity levels:
    - MINIMAL: Store embeddings only
    - STANDARD: Store + search (default)
    - MAXIMAL: Store + search + auto-update + clustering
    """
    
    def __init__(
        self,
        persist_directory: str = None,
        granularity: str = "standard"
    ):
        if not CHROMADB_AVAILABLE:
            raise MLBackendUnavailable(
                "Vector store requires chromadb to be installed."
            )

        self.granularity = granularity
        persist_dir = persist_directory or str(Config.VECTOR_STORE_PATH)

        self.client = chromadb.Client(Settings(
            persist_directory=persist_dir,
            anonymized_telemetry=False
        ))
        
        # Collections
        self.files_collection = self.client.get_or_create_collection("files")
        self.blocks_collection = self.client.get_or_create_collection("training_blocks")
        self.projects_collection = self.client.get_or_create_collection("coding_projects")
        
        self.local_ml = LocalMLBackend()
    
    def store_file_embedding(
        self,
        file_id: int,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Store file embedding in ChromaDB."""
        if not content:
            return
        
        # Generate embedding
        embedding = self.local_ml.embed_text(content)
        
        # Store
        self.files_collection.add(
            embeddings=[embedding.tolist()],
            documents=[content[:1000]],  # Store snippet
            metadatas=[metadata or {'file_id': file_id}],
            ids=[f'file_{file_id}']
        )
        
        # Auto-update related items (if maximal)
        if self.granularity == "maximal":
            self._auto_update_clusters()
    
    def search_similar_files(
        self,
        query: str,
        n_results: int = 10,
        filter_metadata: Dict = None
    ) -> List[Dict[str, Any]]:
        """Search for similar files using vector similarity."""
        # Generate query embedding
        query_embedding = self.local_ml.embed_text(query)
        
        # Search
        results = self.files_collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            where=filter_metadata
        )
        
        return [{
            'file_id': int(id.replace('file_', '')),
            'distance': dist,
            'document': doc,
            'metadata': meta
        } for id, dist, doc, meta in zip(
            results['ids'][0],
            results['distances'][0],
            results['documents'][0],
            results['metadatas'][0]
        )]
    
    def _auto_update_clusters(self):
        """Auto-update clustering (maximal only)."""
        # Implementation for automatic clustering
        pass


# ============================================================
# 2. TRAINING BLOCK → AGENT BINDING (Strict Enforcement)
# ============================================================

class AgentBlockEnforcer:
    """
    Enforce training block binding for agents.
    
    Granularity:
    - MINIMAL: Suggestions only
    - STANDARD: Enforce if agent configured (default)
    - MAXIMAL: Always enforce + auto-optimize block selection
    """
    
    def __init__(self, granularity: str = "standard"):
        self.granularity = granularity
    
    def enforce_block_access(
        self,
        agent_id: int,
        block_ids: List[int],
        requested_blocks: List[int] = None
    ) -> List[int]:
        """
        Enforce which blocks an agent can access.
        
        Args:
            agent_id: Agent ID
            block_ids: Blocks assigned to agent
            requested_blocks: Blocks agent wants to access
            
        Returns:
            Allowed block IDs
        """
        if self.granularity == "minimal":
            # No enforcement, return all
            return requested_blocks or block_ids
        
        elif self.granularity == "standard":
            # Enforce if agent has assigned blocks
            if block_ids:
                if requested_blocks:
                    # Only allow overlap
                    return list(set(block_ids) & set(requested_blocks))
                return block_ids
            return requested_blocks or []
        
        elif self.granularity == "maximal":
            # Strict enforcement + optimization
            allowed = list(set(block_ids) & set(requested_blocks or block_ids))
            return self._optimize_block_selection(agent_id, allowed)
        
        return block_ids
    
    def _optimize_block_selection(
        self,
        agent_id: int,
        block_ids: List[int]
    ) -> List[int]:
        """Optimize which blocks to use based on agent performance."""
        # Track which blocks lead to best responses
        # Return optimized subset
        return block_ids

    def get_allowed_files(self, agent_id: int) -> List[int]:
        """
        Resolve the concrete file IDs an agent may read right now.

        Expands the agent's enforced training blocks (respecting
        enabled/disabled state) into the underlying file ID set. Used by
        EnhancedAgent.get_knowledge_context() as an access-control gate
        before any block content is loaded.
        """
        from core.database import db, MLAgent

        session = db.get_session()
        try:
            agent = session.query(MLAgent).filter_by(id=agent_id).first()
            if not agent:
                return []

            config = agent.config or {}
            block_ids = config.get('training_block_ids', [])
            enforce = config.get('enforce_block_binding', True)

            allowed_block_ids = self.enforce_block_access(agent_id, block_ids)
            if not enforce and not allowed_block_ids:
                # Loose binding with nothing assigned: no restriction.
                return None

            from ml.training_blocks import TrainingBlockManager
            block_manager = TrainingBlockManager()

            file_ids = set()
            for block_id in allowed_block_ids:
                try:
                    block = block_manager.get_block(block_id)
                except Exception:
                    continue
                if not block.enabled:
                    continue
                file_ids.update(f.id for f in block.get_all_files())

            return sorted(file_ids)
        finally:
            session.close()


# ============================================================
# 3. API CONNECTION → AGENT INTEGRATION
# ============================================================

class AgentAPIManager:
    """
    Manage API connections per agent.
    
    Granularity:
    - MINIMAL: Single API per agent
    - STANDARD: Multiple APIs with priority (default)
    - MAXIMAL: Auto-route by task type + cost optimization
    """
    
    def __init__(self, granularity: str = "standard"):
        self.granularity = granularity
    
    def get_api_for_task(
        self,
        agent_id: int,
        api_connection_ids: List[int],
        task_type: str = "general",
        cost_sensitive: bool = False
    ) -> Optional[int]:
        """
        Select best API connection for a task.
        
        Args:
            agent_id: Agent ID
            api_connection_ids: Available API connections
            task_type: Type of task (affects model selection)
            cost_sensitive: Prefer cheaper APIs
            
        Returns:
            Selected API connection ID
        """
        if not api_connection_ids:
            return None
        
        if self.granularity == "minimal":
            # Just use first
            return api_connection_ids[0]
        
        elif self.granularity == "standard":
            # Priority order (first enabled)
            from api.api_manager import APIConnectionManager
            manager = APIConnectionManager()
            
            for conn_id in api_connection_ids:
                conn = manager.get_connection(conn_id)
                if conn and conn.enabled:
                    return conn_id
            
            return api_connection_ids[0] if api_connection_ids else None
        
        elif self.granularity == "maximal":
            # Auto-route by task + cost
            return self._intelligent_route(
                api_connection_ids,
                task_type,
                cost_sensitive
            )
    
    def _intelligent_route(
        self,
        api_ids: List[int],
        task_type: str,
        cost_sensitive: bool
    ) -> int:
        """Intelligent routing based on task and cost."""
        # Implementation: analyze task, choose best model
        # For now, return first enabled
        return api_ids[0] if api_ids else None


# ============================================================
# 4. AUTO-SUGGEST BLOCKS
# ============================================================

class BlockAutoSuggest:
    """
    Auto-suggest which training blocks a file belongs in.
    
    Granularity:
    - MINIMAL: Keyword matching
    - STANDARD: Semantic similarity (default)
    - MAXIMAL: ML classification + confidence + reasoning
    """
    
    def __init__(
        self,
        local_ml: LocalMLBackend = None,
        chroma_manager: ChromaDBManager = None,
        granularity: str = "standard"
    ):
        self.local_ml = local_ml or LocalMLBackend()
        # Don't force-construct a default: an explicit None (e.g. because
        # chromadb isn't installed) must stay None, not silently retry
        # ChromaDBManager() and crash. `chroma_manager` is unused elsewhere
        # in this class today; it's accepted for forward compatibility.
        self.chroma_manager = chroma_manager
        self.granularity = granularity
        self.block_manager = TrainingBlockManager()
    
    def suggest_blocks_for_file(
        self,
        file_id: int,
        threshold: float = 0.7,
        max_suggestions: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Suggest training blocks for a file.
        
        Returns:
            List of {block_id, block_name, confidence, reason}
        """
        session = db.get_session()
        try:
            file = session.query(File).filter_by(id=file_id).first()
            if not file or not file.content:
                return []
            
            if self.granularity == "minimal":
                return self._keyword_suggest(file, threshold, max_suggestions)
            
            elif self.granularity == "standard":
                return self._semantic_suggest(file, threshold, max_suggestions)
            
            elif self.granularity == "maximal":
                return self._ml_classify(file, threshold, max_suggestions)
        finally:
            session.close()
    
    def _keyword_suggest(
        self,
        file: File,
        threshold: float,
        max_suggestions: int
    ) -> List[Dict[str, Any]]:
        """Simple keyword matching."""
        suggestions = []
        all_blocks = self.block_manager.list_blocks()
        
        file_words = set(file.content.lower().split())
        
        for block in all_blocks:
            block_content = self.block_manager.get_block_contents(block.id)
            block_words = set()
            
            for item in block_content['contents']:
                block_words.update(item['content'].lower().split())
            
            # Jaccard similarity
            if block_words:
                overlap = len(file_words & block_words)
                union = len(file_words | block_words)
                similarity = overlap / union if union > 0 else 0
                
                if similarity >= threshold:
                    suggestions.append({
                        'block_id': block.id,
                        'block_name': block.name,
                        'confidence': similarity,
                        'reason': 'Keyword overlap',
                        'method': 'keyword'
                    })
        
        return sorted(suggestions, key=lambda x: x['confidence'], reverse=True)[:max_suggestions]
    
    def _semantic_suggest(
        self,
        file: File,
        threshold: float,
        max_suggestions: int
    ) -> List[Dict[str, Any]]:
        """Semantic similarity using embeddings."""
        # Generate file embedding
        file_embedding = self.local_ml.embed_text(file.content)
        
        suggestions = []
        all_blocks = self.block_manager.list_blocks()
        
        for block in all_blocks:
            # Get average embedding of block
            block_content = self.block_manager.get_block_contents(block.id)
            
            if not block_content['contents']:
                continue
            
            # Get embeddings for block contents
            block_texts = [c['content'][:500] for c in block_content['contents']]
            block_embeddings = self.local_ml.embed_text(block_texts)
            
            # Average embedding
            avg_embedding = np.mean(block_embeddings, axis=0)
            
            # Calculate similarity
            similarity = np.dot(file_embedding, avg_embedding) / (
                np.linalg.norm(file_embedding) * np.linalg.norm(avg_embedding)
            )
            
            if similarity >= threshold:
                suggestions.append({
                    'block_id': block.id,
                    'block_name': block.name,
                    'confidence': float(similarity),
                    'reason': 'Semantic similarity',
                    'method': 'semantic',
                    'block_type': block.block_type
                })
        
        return sorted(suggestions, key=lambda x: x['confidence'], reverse=True)[:max_suggestions]
    
    def _ml_classify(
        self,
        file: File,
        threshold: float,
        max_suggestions: int
    ) -> List[Dict[str, Any]]:
        """ML classification with reasoning."""
        # Start with semantic
        suggestions = self._semantic_suggest(file, threshold * 0.8, max_suggestions * 2)
        
        # Add ML reasoning
        for suggestion in suggestions:
            block = self.block_manager.get_block(suggestion['block_id'])
            
            # Add reasoning based on block type
            if block.block_type == 'rote' and 'data' in file.file_type:
                suggestion['confidence'] *= 1.2
                suggestion['reason'] += ' (rote data match)'
            elif block.block_type == 'process' and 'code' in file.file_type:
                suggestion['confidence'] *= 1.2
                suggestion['reason'] += ' (process code match)'
        
        return sorted(suggestions, key=lambda x: x['confidence'], reverse=True)[:max_suggestions]


# ============================================================
# 5. CODING PROJECT → TRAINING BLOCK
# ============================================================

class ProjectTrainingIntegration:
    """
    Integrate coding projects with training blocks.
    
    Granularity:
    - MINIMAL: Manual file-by-file addition
    - STANDARD: Add entire project (default)
    - MAXIMAL: Auto-sync + selective file filtering + pattern extraction
    """
    
    def __init__(self, granularity: str = "standard"):
        self.granularity = granularity
        self.block_manager = TrainingBlockManager()
    
    def add_project_to_block(
        self,
        project_id: int,
        block_id: int,
        file_filter: Optional[callable] = None,
        auto_sync: bool = False
    ) -> Dict[str, Any]:
        """
        Add coding project to training block.
        
        Args:
            project_id: Project ID
            block_id: Training block ID
            file_filter: Optional function to filter which files to include
            auto_sync: Keep block synchronized with project changes
            
        Returns:
            Stats about what was added
        """
        from coding.ide_manager import CodingIDEManager
        
        ide_manager = CodingIDEManager()
        project_files = ide_manager.get_project_files(project_id)
        
        added_count = 0
        skipped_count = 0
        
        for file_info in project_files:
            # Apply filter
            if file_filter and not file_filter(file_info):
                skipped_count += 1
                continue
            
            # Read file content
            content = ide_manager.read_file(project_id, file_info['path'])
            
            if not content:
                skipped_count += 1
                continue
            
            # Create File entry if needed
            # Then add to training block
            # (Simplified - full implementation would check if file exists)
            added_count += 1
        
        result = {
            'project_id': project_id,
            'block_id': block_id,
            'files_added': added_count,
            'files_skipped': skipped_count,
            'auto_sync': auto_sync
        }
        
        if auto_sync and self.granularity == "maximal":
            result['sync_enabled'] = True
            # Set up file watcher
            self._setup_project_sync(project_id, block_id)
        
        return result
    
    def _setup_project_sync(self, project_id: int, block_id: int):
        """Setup automatic sync (maximal only)."""
        # Implementation: watch project directory, auto-add changes
        pass


# ============================================================
# 6. VM → CODING PROJECT
# ============================================================

class VMProjectIntegration:
    """
    Link VMs to coding projects.
    
    Granularity:
    - MINIMAL: Manual VM association
    - STANDARD: Auto-start VM with project (default)
    - MAXIMAL: Auto-provision + dependency install + port forwarding
    """
    
    def __init__(self, granularity: str = "standard"):
        self.granularity = granularity
    
    def assign_vm_to_project(
        self,
        project_id: int,
        vm_id: int,
        auto_start: bool = True,
        auto_provision: bool = False
    ) -> Dict[str, Any]:
        """Assign VM to coding project."""
        from coding.ide_manager import CodingIDEManager
        from vm.vm_manager import VMManager
        
        # Update project with VM ID
        session = db.get_session()
        try:
            from core.enhanced_models import CodingProject
            project = session.query(CodingProject).filter_by(id=project_id).first()
            
            if not project:
                return {'error': 'Project not found'}
            
            project.vm_id = vm_id
            session.commit()
            
            result = {
                'project_id': project_id,
                'vm_id': vm_id,
                'assigned': True
            }
            
            # Auto-start if requested
            if auto_start and self.granularity in ['standard', 'maximal']:
                vm_manager = VMManager()
                start_result = vm_manager.start_vm(vm_id)
                result['vm_started'] = start_result.get('success', False)
            
            # Auto-provision if maximal
            if auto_provision and self.granularity == 'maximal':
                result['provisioned'] = self._provision_vm_for_project(
                    project,
                    vm_id
                )
            
            return result
        finally:
            session.close()
    
    def _provision_vm_for_project(
        self,
        project,
        vm_id: int
    ) -> bool:
        """Auto-provision VM for project (maximal only)."""
        # Implementation: install dependencies, setup environment
        return True


# ============================================================
# 7. WEBHOOK SUPPORT
# ============================================================

class WebhookManager:
    """
    Handle webhooks from external services.
    
    Granularity:
    - MINIMAL: Receive only
    - STANDARD: Receive + trigger workflows (default)
    - MAXIMAL: Receive + trigger + transform + validate + retry
    """
    
    def __init__(self, granularity: str = "standard"):
        self.granularity = granularity
        self.webhooks = {}  # webhook_id -> config
    
    def register_webhook(
        self,
        webhook_id: str,
        service: str,
        event_type: str,
        action: str,
        config: Dict[str, Any] = None
    ) -> str:
        """
        Register a webhook endpoint.
        
        Args:
            webhook_id: Unique webhook ID
            service: Service name (github, slack, etc.)
            event_type: Type of event
            action: What to do when triggered
            config: Additional configuration
            
        Returns:
            Webhook URL
        """
        self.webhooks[webhook_id] = {
            'service': service,
            'event_type': event_type,
            'action': action,
            'config': config or {},
            'created_at': datetime.utcnow()
        }
        
        return f"/api/webhooks/{webhook_id}"
    
    def handle_webhook(
        self,
        webhook_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle incoming webhook."""
        if webhook_id not in self.webhooks:
            return {'error': 'Webhook not found'}
        
        webhook_config = self.webhooks[webhook_id]
        
        if self.granularity == "minimal":
            return {'received': True, 'payload': payload}
        
        elif self.granularity == "standard":
            # Trigger action
            return self._trigger_action(webhook_config, payload)
        
        elif self.granularity == "maximal":
            # Validate, transform, trigger, retry
            return self._handle_advanced(webhook_config, payload)
    
    def _trigger_action(
        self,
        webhook_config: Dict,
        payload: Dict
    ) -> Dict[str, Any]:
        """Trigger configured action."""
        action = webhook_config['action']
        
        if action == 'create_file':
            # Create file from webhook data
            pass
        elif action == 'trigger_workflow':
            # Trigger workflow
            pass
        elif action == 'add_to_training_block':
            # Add content to training block
            pass
        
        return {'action_triggered': action}
    
    def _handle_advanced(
        self,
        webhook_config: Dict,
        payload: Dict
    ) -> Dict[str, Any]:
        """Advanced webhook handling (maximal)."""
        # Validate payload
        # Transform data
        # Trigger action
        # Retry on failure
        return self._trigger_action(webhook_config, payload)


# ============================================================
# 8. UNIVERSAL SEARCH
# ============================================================

class UniversalSearch:
    """
    Search across everything in one query.
    
    Granularity:
    - MINIMAL: Sequential search (slower)
    - STANDARD: Parallel search (default)
    - MAXIMAL: Parallel + ranked + clustered + suggested filters
    """
    
    def __init__(
        self,
        local_ml: LocalMLBackend = None,
        chroma_manager: ChromaDBManager = None,
        granularity: str = "standard"
    ):
        self.local_ml = local_ml or LocalMLBackend()
        # Don't force-construct a default: an explicit None (e.g. because
        # chromadb isn't installed) must stay None, not silently retry
        # ChromaDBManager() and crash. `chroma_manager` is unused elsewhere
        # in this class today; it's accepted for forward compatibility.
        self.chroma_manager = chroma_manager
        self.granularity = granularity
    
    def search_all(
        self,
        query: str,
        limit_per_category: int = 5,
        semantic: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search across all categories.
        
        Returns:
            {
                'files': [...],
                'training_blocks': [...],
                'coding_projects': [...],
                'vms': [...],
                'api_connections': [...],
                'agents': [...]
            }
        """
        if self.granularity == "minimal":
            return self._sequential_search(query, limit_per_category, semantic)
        
        elif self.granularity == "standard":
            return self._parallel_search(query, limit_per_category, semantic)
        
        elif self.granularity == "maximal":
            return self._advanced_search(query, limit_per_category, semantic)
    
    def _sequential_search(
        self,
        query: str,
        limit: int,
        semantic: bool
    ) -> Dict[str, List]:
        """Sequential search (slower but simpler)."""
        results = {}
        
        # Search files
        from filesystem.operations import SemanticFileSystem
        fs = SemanticFileSystem(self.local_ml)
        results['files'] = fs.search_files(query, semantic=semantic, limit=limit)
        
        # Search training blocks
        results['training_blocks'] = self._search_training_blocks(query, limit)
        
        # Search coding projects
        results['coding_projects'] = self._search_coding_projects(query, limit)
        
        # Search VMs
        results['vms'] = self._search_vms(query, limit)
        
        # Search API connections
        results['api_connections'] = self._search_api_connections(query, limit)
        
        # Search agents
        results['agents'] = self._search_agents(query, limit)
        
        return results
    
    def _parallel_search(
        self,
        query: str,
        limit: int,
        semantic: bool
    ) -> Dict[str, List]:
        """Parallel search (faster)."""
        from concurrent.futures import ThreadPoolExecutor
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                'files': executor.submit(self._search_files, query, limit, semantic),
                'training_blocks': executor.submit(self._search_training_blocks, query, limit),
                'coding_projects': executor.submit(self._search_coding_projects, query, limit),
                'vms': executor.submit(self._search_vms, query, limit),
                'api_connections': executor.submit(self._search_api_connections, query, limit),
                'agents': executor.submit(self._search_agents, query, limit)
            }
            
            results = {key: future.result() for key, future in futures.items()}
        
        return results
    
    def _advanced_search(
        self,
        query: str,
        limit: int,
        semantic: bool
    ) -> Dict[str, List]:
        """Advanced search with ranking and clustering (maximal)."""
        # Start with parallel search
        results = self._parallel_search(query, limit * 2, semantic)
        
        # Rank all results together
        all_results = []
        for category, items in results.items():
            for item in items:
                item['_category'] = category
                all_results.append(item)
        
        # Sort by relevance (simplified)
        all_results.sort(
            key=lambda x: x.get('similarity', x.get('relevance', 0)),
            reverse=True
        )
        
        # Re-distribute top results
        final_results = {key: [] for key in results.keys()}
        for item in all_results[:limit * 3]:
            category = item.pop('_category')
            if len(final_results[category]) < limit:
                final_results[category].append(item)
        
        return final_results
    
    def _search_files(self, query: str, limit: int, semantic: bool) -> List[Dict]:
        """Search files."""
        from filesystem.operations import SemanticFileSystem
        fs = SemanticFileSystem(self.local_ml)
        return fs.search_files(query, semantic=semantic, limit=limit)
    
    def _search_training_blocks(self, query: str, limit: int) -> List[Dict]:
        """Search training blocks."""
        session = db.get_session()
        try:
            blocks = session.query(TrainingBlock).filter(
                TrainingBlock.name.contains(query) |
                TrainingBlock.description.contains(query)
            ).limit(limit).all()
            return [b.to_dict() for b in blocks]
        finally:
            session.close()
    
    def _search_coding_projects(self, query: str, limit: int) -> List[Dict]:
        """Search coding projects."""
        session = db.get_session()
        try:
            from core.enhanced_models import CodingProject
            projects = session.query(CodingProject).filter(
                CodingProject.name.contains(query) |
                CodingProject.description.contains(query)
            ).limit(limit).all()
            return [p.to_dict() for p in projects]
        finally:
            session.close()
    
    def _search_vms(self, query: str, limit: int) -> List[Dict]:
        """Search VMs."""
        session = db.get_session()
        try:
            from core.enhanced_models import VMConfiguration
            vms = session.query(VMConfiguration).filter(
                VMConfiguration.name.contains(query) |
                VMConfiguration.description.contains(query)
            ).limit(limit).all()
            return [v.to_dict() for v in vms]
        finally:
            session.close()
    
    def _search_api_connections(self, query: str, limit: int) -> List[Dict]:
        """Search API connections."""
        session = db.get_session()
        try:
            from core.enhanced_models import APIConnection
            connections = session.query(APIConnection).filter(
                APIConnection.name.contains(query) |
                APIConnection.description.contains(query)
            ).limit(limit).all()
            return [c.to_dict_safe() for c in connections]
        finally:
            session.close()
    
    def _search_agents(self, query: str, limit: int) -> List[Dict]:
        """Search ML agents."""
        session = db.get_session()
        try:
            from core.database import MLAgent
            agents = session.query(MLAgent).filter(
                MLAgent.name.contains(query) |
                MLAgent.description.contains(query)
            ).limit(limit).all()
            return [a.to_dict() for a in agents]
        finally:
            session.close()
