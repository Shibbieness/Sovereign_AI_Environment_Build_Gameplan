"""
Enhanced Agent Architecture for ML Filesystem v1.8+

Implements:
- Agent Profiles (reasoning patterns)
- Multi-Model Support (swap/parallel)
- Training Block Binding (strict enforcement)
- API Connection Assignment
- Functional Training Blocks (proficiency domains)
- Agent-to-Agent knowledge transfer
"""

from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from enum import Enum
import json

from core.database import db
from core.enhanced_models import APIConnection
from core.database import MLAgent, TrainingBlock, User
from ml.local_backend import LocalMLBackend
from ml.training_blocks import TrainingBlockManager


class AgentProfile(Enum):
    """Agent reasoning profiles."""
    ANALYTICAL = "analytical"      # Detailed, step-by-step reasoning
    CREATIVE = "creative"          # Divergent thinking, novel connections
    EFFICIENT = "efficient"        # Fast, minimal processing
    THOROUGH = "thorough"          # Exhaustive, comprehensive
    BALANCED = "balanced"          # Default, general-purpose
    CUSTOM = "custom"              # User-defined


class ModelExecutionMode(Enum):
    """How to use multiple models."""
    SINGLE = "single"              # Use one model
    PARALLEL = "parallel"          # Run all models, compare results
    WATERFALL = "waterfall"        # Try models in order until success
    ENSEMBLE = "ensemble"          # Combine results from multiple models
    VOTE = "vote"                  # Majority vote from models


class FunctionalBlock:
    """
    Functional Training Block - compressed proficiency domain.
    
    Unlike regular training blocks (raw data), functional blocks are:
    - Compressed knowledge graphs
    - Learned patterns/rules
    - Quick-reference lookup
    - Transferable between agents
    - Validatable/repairable
    """
    
    def __init__(
        self,
        name: str,
        domain: str,
        knowledge_graph: Dict[str, Any],
        patterns: List[Dict[str, Any]],
        confidence: float,
        source_blocks: List[int],
        agent_id: int
    ):
        self.name = name
        self.domain = domain
        self.knowledge_graph = knowledge_graph
        self.patterns = patterns
        self.confidence = confidence
        self.source_blocks = source_blocks
        self.agent_id = agent_id
        self.created_at = datetime.utcnow()
        self.last_used = None
        self.usage_count = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'domain': self.domain,
            'confidence': self.confidence,
            'source_blocks': self.source_blocks,
            'pattern_count': len(self.patterns),
            'knowledge_nodes': len(self.knowledge_graph),
            'created_at': self.created_at.isoformat(),
            'usage_count': self.usage_count
        }


class EnhancedAgent:
    """
    Enhanced ML Agent with full control over:
    - Training blocks (strict binding)
    - Models (selection, parallel, ensemble)
    - APIs (specific connections)
    - Profiles (reasoning patterns)
    - Functional blocks (proficiency domains)
    """
    
    def __init__(
        self,
        agent_id: int,
        name: str = None,
        profile: AgentProfile = AgentProfile.BALANCED,
        training_block_ids: List[int] = None,
        api_connection_ids: List[int] = None,
        model_execution_mode: ModelExecutionMode = ModelExecutionMode.SINGLE,
        primary_model: str = None,
        fallback_models: List[str] = None,
        enable_parallel: bool = False,
        local_ml: LocalMLBackend = None,
        training_block_manager: TrainingBlockManager = None
    ):
        self.agent_id = agent_id
        self.name = name
        self.profile = profile
        
        # Training block binding - STRICT enforcement
        self.training_block_ids = training_block_ids or []
        self.enforce_block_binding = True  # Can be toggled per agent
        
        # API connection assignment
        self.api_connection_ids = api_connection_ids or []
        self.current_api_index = 0
        
        # Model configuration
        self.model_execution_mode = model_execution_mode
        self.primary_model = primary_model
        self.fallback_models = fallback_models or []
        self.enable_parallel = enable_parallel
        
        # ML backends
        self.local_ml = local_ml or LocalMLBackend()
        self.training_block_manager = training_block_manager or TrainingBlockManager()
        
        # Functional blocks (proficiency domains)
        self.functional_blocks: Dict[str, FunctionalBlock] = {}
        
        # Performance tracking
        self.query_count = 0
        self.success_rate = 1.0
        self.avg_response_time = 0.0
        
        # Load from database if exists
        if agent_id:
            self._load_from_db()
    
    def _load_from_db(self):
        """Load agent configuration from database."""
        session = db.get_session()
        try:
            agent = session.query(MLAgent).filter_by(id=self.agent_id).first()
            if agent:
                self.name = agent.name
                
                # Load configuration
                config = agent.config or {}
                self.training_block_ids = config.get('training_block_ids', [])
                self.api_connection_ids = config.get('api_connection_ids', [])
                self.profile = AgentProfile(config.get('profile', 'balanced'))
                self.model_execution_mode = ModelExecutionMode(
                    config.get('model_execution_mode', 'single')
                )
                self.primary_model = config.get('primary_model')
                self.fallback_models = config.get('fallback_models', [])
                self.enable_parallel = config.get('enable_parallel', False)
                self.enforce_block_binding = config.get('enforce_block_binding', True)
        finally:
            session.close()
    
    def save_to_db(self):
        """Save agent configuration to database."""
        session = db.get_session()
        try:
            agent = session.query(MLAgent).filter_by(id=self.agent_id).first()
            if agent:
                agent.config = {
                    'training_block_ids': self.training_block_ids,
                    'api_connection_ids': self.api_connection_ids,
                    'profile': self.profile.value,
                    'model_execution_mode': self.model_execution_mode.value,
                    'primary_model': self.primary_model,
                    'fallback_models': self.fallback_models,
                    'enable_parallel': self.enable_parallel,
                    'enforce_block_binding': self.enforce_block_binding
                }
                session.commit()
        finally:
            session.close()
    
    def assign_training_blocks(self, block_ids: List[int], enforce: bool = True):
        """
        Assign specific training blocks to this agent.
        
        Args:
            block_ids: List of training block IDs
            enforce: If True, agent ONLY uses these blocks (strict binding)
                    If False, these are preferred but not exclusive
        """
        self.training_block_ids = block_ids
        self.enforce_block_binding = enforce
        self.save_to_db()
    
    def assign_api_connections(self, connection_ids: List[int]):
        """Assign specific API connections to this agent."""
        self.api_connection_ids = connection_ids
        self.save_to_db()
    
    def set_model_config(
        self,
        primary_model: str,
        fallback_models: List[str] = None,
        execution_mode: ModelExecutionMode = ModelExecutionMode.SINGLE,
        enable_parallel: bool = False
    ):
        """
        Configure model selection and execution.
        
        Args:
            primary_model: Main model to use
            fallback_models: Models to try if primary fails
            execution_mode: How to use multiple models
            enable_parallel: Run models in parallel (costs more, faster results)
        """
        self.primary_model = primary_model
        self.fallback_models = fallback_models or []
        self.model_execution_mode = execution_mode
        self.enable_parallel = enable_parallel
        self.save_to_db()
    
    def get_knowledge_context(self, include_functional: bool = True) -> str:
        """
        Get knowledge context from training blocks.
        
        Respects training block binding if enforced.
        """
        context_parts = []

        # Access-control gate: resolve which files this agent is actually
        # allowed to read before loading any block content.
        from enhancements.enhancements import AgentBlockEnforcer
        allowed_file_ids = AgentBlockEnforcer().get_allowed_files(self.agent_id)

        # Get enabled training blocks
        if self.enforce_block_binding and self.training_block_ids:
            # STRICT: Only use assigned blocks
            blocks = [
                self.training_block_manager.get_block(bid)
                for bid in self.training_block_ids
            ]
            blocks = [b for b in blocks if b and b.enabled]
        else:
            # LOOSE: Use all enabled blocks (or assigned if specified)
            if self.training_block_ids:
                blocks = [
                    self.training_block_manager.get_block(bid)
                    for bid in self.training_block_ids
                ]
            else:
                blocks = self.training_block_manager.get_enabled_blocks()
            blocks = [b for b in blocks if b]
        
        # Extract content from blocks, respecting the access-control gate.
        # allowed_file_ids is None when the agent has no binding restriction
        # at all; otherwise it's the exact set of file IDs the agent may read.
        for block in blocks:
            block_content = self.training_block_manager.get_block_contents(block.id)
            included = 0
            for content_item in block_content['contents']:
                if included >= 5:  # Limit per block
                    break
                if allowed_file_ids is not None and content_item['file_id'] not in allowed_file_ids:
                    continue
                context_parts.append(content_item['content'][:500])
                included += 1
        
        # Include functional blocks (compressed knowledge)
        if include_functional and self.functional_blocks:
            for func_block in self.functional_blocks.values():
                # Add compressed patterns instead of raw data
                context_parts.append(
                    f"Domain: {func_block.domain}\n" +
                    f"Patterns: {json.dumps(func_block.patterns[:3])}"
                )
        
        return '\n\n'.join(context_parts)
    
    def query(
        self,
        question: str,
        use_functional_blocks: bool = True,
        force_model: str = None
    ) -> Dict[str, Any]:
        """
        Query the agent with full model control.
        
        Args:
            question: Question to answer
            use_functional_blocks: Include compressed knowledge
            force_model: Override model selection
            
        Returns:
            Answer with metadata about which model(s) were used
        """
        start_time = datetime.utcnow()
        
        # Get context
        context = self.get_knowledge_context(include_functional=use_functional_blocks)
        
        if not context:
            return {
                'answer': 'No knowledge available. Assign training blocks to this agent.',
                'error': 'no_context',
                'agent_id': self.agent_id
            }
        
        # Determine model(s) to use
        if force_model:
            models_to_use = [force_model]
            mode = ModelExecutionMode.SINGLE
        else:
            models_to_use = [self.primary_model] + self.fallback_models
            mode = self.model_execution_mode
        
        # Execute based on mode
        if mode == ModelExecutionMode.SINGLE:
            result = self._query_single_model(question, context, models_to_use[0])
        
        elif mode == ModelExecutionMode.PARALLEL and self.enable_parallel:
            result = self._query_parallel(question, context, models_to_use)
        
        elif mode == ModelExecutionMode.WATERFALL:
            result = self._query_waterfall(question, context, models_to_use)
        
        elif mode == ModelExecutionMode.ENSEMBLE:
            result = self._query_ensemble(question, context, models_to_use)
        
        elif mode == ModelExecutionMode.VOTE:
            result = self._query_vote(question, context, models_to_use)
        
        else:
            result = self._query_single_model(question, context, models_to_use[0])
        
        # Track performance
        duration = (datetime.utcnow() - start_time).total_seconds()
        self.query_count += 1
        self.avg_response_time = (
            (self.avg_response_time * (self.query_count - 1) + duration) /
            self.query_count
        )
        
        result['agent_id'] = self.agent_id
        result['agent_profile'] = self.profile.value
        result['duration_seconds'] = duration
        
        return result
    
    def _query_single_model(
        self,
        question: str,
        context: str,
        model: str
    ) -> Dict[str, Any]:
        """Query using a single model."""
        if model == 'api':
            return self._call_api(question, context)

        # Use local ML
        answer = self.local_ml.answer_question(question, context)
        answer['model_used'] = model or 'local'
        answer['execution_mode'] = 'single'
        return answer

    def _call_api(self, question: str, context: str, task_type: str = 'general') -> Dict[str, Any]:
        """
        Answer a question by routing to the best available API connection,
        rather than a hardcoded provider. Only connections assigned to this
        agent (self.api_connection_ids) are considered.
        """
        from api.api_manager import APIConnectionManager

        api_manager = APIConnectionManager()
        connection = api_manager.get_best_connection(task_type)

        if not connection or (self.api_connection_ids and connection.id not in self.api_connection_ids):
            return {
                'answer': None,
                'error': 'no_api_connection',
                'score': 0.0,
                'model_used': None,
                'execution_mode': 'api',
            }

        # Which vendor this is comes from the stored connection row and is
        # resolved through core/providers.py. No SDK is named here.
        from core import providers

        try:
            spec = providers.resolve(connection.provider)
        except providers.ProviderError:
            spec = None

        if not providers.has_chat_adapter(spec):
            return {
                'answer': None,
                'error': f"no_api_caller_for_provider:{connection.provider}",
                'score': 0.0,
                'model_used': connection.model_name or connection.provider,
                'execution_mode': 'api',
            }

        prompt = (
            f"Context:\n{context}\n\nQuestion: {question}\n\n"
            "Answer based only on the context provided:"
        )
        try:
            client = providers.load_client(spec, api_key=connection.api_key)
            answer_text, tokens = providers.chat(
                spec, client, prompt, model=connection.model_name)
        except providers.ProviderError as exc:
            # A missing SDK or absent key is a reportable condition, not a
            # traceback out of a query method that every other failure path
            # returns a dict from.
            return {
                'answer': None,
                'error': str(exc),
                'score': 0.0,
                'model_used': connection.model_name or connection.provider,
                'execution_mode': 'api',
            }

        api_manager.track_usage(connection.id, tokens=tokens)

        return {
            'answer': answer_text,
            'score': 1.0,
            'model_used': connection.model_name or connection.provider,
            'execution_mode': 'api',
            'api_connection_id': connection.id,
        }
    
    def _query_parallel(
        self,
        question: str,
        context: str,
        models: List[str]
    ) -> Dict[str, Any]:
        """Query multiple models in parallel and return all results."""
        from concurrent.futures import ThreadPoolExecutor
        
        results = []
        
        with ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = [
                executor.submit(self._query_single_model, question, context, model)
                for model in models
            ]
            results = [f.result() for f in futures]
        
        return {
            'answer': results[0]['answer'],  # Primary result
            'all_results': results,
            'execution_mode': 'parallel',
            'models_used': models
        }
    
    def _query_waterfall(
        self,
        question: str,
        context: str,
        models: List[str]
    ) -> Dict[str, Any]:
        """Try models in order until one succeeds."""
        for model in models:
            result = self._query_single_model(question, context, model)
            
            if result.get('score', 0) > 0.5 or not result.get('error'):
                result['execution_mode'] = 'waterfall'
                result['model_used'] = model
                return result
        
        # All failed
        return {
            'answer': 'Could not generate confident answer with any model.',
            'execution_mode': 'waterfall',
            'models_tried': models,
            'all_failed': True
        }
    
    def _query_ensemble(
        self,
        question: str,
        context: str,
        models: List[str]
    ) -> Dict[str, Any]:
        """Combine results from multiple models."""
        results = [
            self._query_single_model(question, context, model)
            for model in models
        ]
        
        # Simple ensemble: average confidence, concatenate answers
        avg_confidence = sum(r.get('score', 0) for r in results) / len(results)
        combined_answer = ' '.join([r['answer'] for r in results if r.get('answer')])
        
        return {
            'answer': combined_answer,
            'confidence': avg_confidence,
            'execution_mode': 'ensemble',
            'models_used': models,
            'individual_results': results
        }
    
    def _query_vote(
        self,
        question: str,
        context: str,
        models: List[str]
    ) -> Dict[str, Any]:
        """Vote on best answer from multiple models."""
        results = [
            self._query_single_model(question, context, model)
            for model in models
        ]
        
        # Vote: highest confidence wins
        winner = max(results, key=lambda r: r.get('score', 0))
        
        return {
            'answer': winner['answer'],
            'confidence': winner.get('score', 0),
            'execution_mode': 'vote',
            'winner_model': winner.get('model_used'),
            'vote_count': len(results),
            'all_results': results
        }
    
    def create_functional_block(
        self,
        name: str,
        domain: str,
        source_block_ids: List[int]
    ) -> FunctionalBlock:
        """
        Create a functional training block (compressed proficiency domain).
        
        Learns patterns from source blocks and creates compressed representation.
        """
        # Get content from source blocks
        all_content = []
        for block_id in source_block_ids:
            block_content = self.training_block_manager.get_block_contents(block_id)
            all_content.extend([c['content'] for c in block_content['contents']])
        
        # Extract patterns using ML
        # (Simplified - in production, use more sophisticated pattern extraction)
        patterns = []
        knowledge_graph = {}
        
        # Generate embeddings for all content
        embeddings = self.local_ml.embed_text(all_content)
        
        # Find clusters (patterns)
        if len(embeddings) >= 2:
            from sklearn.cluster import KMeans
            import numpy as np
            
            n_clusters = min(5, len(all_content))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            clusters = kmeans.fit_predict(embeddings)
            
            # Each cluster is a pattern
            for i in range(n_clusters):
                cluster_docs = [
                    all_content[j] for j in range(len(all_content))
                    if clusters[j] == i
                ]
                patterns.append({
                    'pattern_id': i,
                    'documents': len(cluster_docs),
                    'representative': cluster_docs[0][:200] if cluster_docs else ''
                })
        
        # Create functional block
        func_block = FunctionalBlock(
            name=name,
            domain=domain,
            knowledge_graph=knowledge_graph,
            patterns=patterns,
            confidence=0.8,  # Initial confidence
            source_blocks=source_block_ids,
            agent_id=self.agent_id
        )
        
        self.functional_blocks[name] = func_block
        
        return func_block
    
    def share_functional_block(
        self,
        block_name: str,
        target_agent_id: int,
        require_validation: bool = True
    ) -> bool:
        """
        Share a functional block with another agent.
        
        Args:
            block_name: Name of functional block to share
            target_agent_id: Target agent ID
            require_validation: If True, target agent must validate before use
        """
        if block_name not in self.functional_blocks:
            return False
        
        func_block = self.functional_blocks[block_name]
        
        # Load target agent
        target_agent = EnhancedAgent(agent_id=target_agent_id)
        
        if require_validation:
            # Target agent should validate this knowledge
            # (Implementation would test against their training blocks)
            pass
        
        # Transfer block
        target_agent.functional_blocks[block_name] = func_block
        
        return True
    
    def validate_functional_block(
        self,
        block_name: str,
        test_questions: List[str] = None
    ) -> Dict[str, Any]:
        """
        Validate a functional block's accuracy.
        
        Tests patterns against current training blocks.
        Can repair if inconsistencies found.
        """
        if block_name not in self.functional_blocks:
            return {'error': 'Block not found'}
        
        func_block = self.functional_blocks[block_name]
        
        # Get current knowledge from source blocks
        current_context = self.get_knowledge_context(include_functional=False)
        
        # Test patterns
        validation_results = {
            'block_name': block_name,
            'patterns_tested': len(func_block.patterns),
            'patterns_valid': 0,
            'patterns_invalid': 0,
            'needs_repair': False
        }
        
        # Simple validation: check if patterns still present in current data
        for pattern in func_block.patterns:
            if pattern['representative'] in current_context:
                validation_results['patterns_valid'] += 1
            else:
                validation_results['patterns_invalid'] += 1
        
        # Calculate validity
        validity_ratio = (
            validation_results['patterns_valid'] /
            max(len(func_block.patterns), 1)
        )
        
        func_block.confidence = validity_ratio
        validation_results['confidence'] = validity_ratio
        validation_results['needs_repair'] = validity_ratio < 0.7
        
        return validation_results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            'agent_id': self.agent_id,
            'name': self.name,
            'profile': self.profile.value,
            'training_blocks': len(self.training_block_ids),
            'enforce_binding': self.enforce_block_binding,
            'api_connections': len(self.api_connection_ids),
            'model_execution_mode': self.model_execution_mode.value,
            'parallel_enabled': self.enable_parallel,
            'functional_blocks': len(self.functional_blocks),
            'query_count': self.query_count,
            'success_rate': self.success_rate,
            'avg_response_time': self.avg_response_time
        }
