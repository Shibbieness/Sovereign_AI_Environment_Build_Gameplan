"""
Hybrid ML Agent for ML Filesystem v1.8

Combines local ML models with optional API enhancement.
- Uses local models by default (fast, free, private)
- Falls back to API for complex tasks when available
- Learns from training blocks
- Respects enabled/disabled block state
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from core.config import Config
from core.database import db, MLAgent, TrainingBlock
from core.exceptions import MLException, InferenceError
from ml.local_backend import LocalMLBackend
from ml.training_blocks import TrainingBlockManager

# Optional: an LLM provider API. Which vendor, if any, is data — see
# core/providers.py. No SDK is imported here; it is loaded lazily at
# construction, so this module imports cleanly with no provider installed.
from core import providers

LLM_AVAILABLE = bool(Config.LLM_API_KEY)


class HybridMLAgent:
    """
    Hybrid ML Agent that uses local models + optional API.
    
    Agent Types:
    - organizer: Suggests file organization
    - learner: Learns from files, answers questions
    - analyzer: Analyzes patterns and relationships
    - custom: User-defined behavior
    """
    
    def __init__(
        self,
        agent_id: int = None,
        name: str = None,
        agent_type: str = 'learner',
        local_ml: LocalMLBackend = None,
        training_block_manager: TrainingBlockManager = None
    ):
        self.agent_id = agent_id
        self.name = name
        self.agent_type = agent_type
        
        # ML backends
        self.local_ml = local_ml or LocalMLBackend()
        self.training_block_manager = training_block_manager or TrainingBlockManager(self.local_ml)
        
        # API client (optional)
        self.llm_provider = providers.resolve()
        self.llm = None
        if LLM_AVAILABLE and providers.has_chat_adapter(self.llm_provider):
            try:
                self.llm = providers.load_client(
                    self.llm_provider, api_key=Config.LLM_API_KEY)
            except providers.ProviderError:
                # Absent SDK or bad key: stay on the local path, which is what
                # this agent is built to do. The bare `except:` this replaced
                # would also have swallowed KeyboardInterrupt.
                pass
        
        # Load agent from DB if ID provided
        if agent_id:
            self._load_agent()
    
    def _load_agent(self):
        """Load agent configuration from database."""
        session = db.get_session()
        try:
            agent = session.query(MLAgent).filter_by(id=self.agent_id).first()
            if agent:
                self.name = agent.name
                self.agent_type = agent.agent_type
                self.training_block_id = agent.training_block_id
        finally:
            session.close()
    
    def organize_files(self, file_ids: List[int], use_api: bool = False) -> Dict[str, Any]:
        """
        Suggest organization for files.
        
        Args:
            file_ids: Files to organize
            use_api: Use API for enhanced suggestions
            
        Returns:
            Organization suggestions
        """
        from core.database import File
        
        session = db.get_session()
        try:
            # Get files
            files = session.query(File).filter(File.id.in_(file_ids)).all()
            
            if not files:
                return {'error': 'No files found'}
            
            # Extract content for analysis
            texts = []
            file_info = []
            for file in files:
                if file.content:
                    texts.append(file.content[:1000])  # First 1000 chars
                    file_info.append({
                        'id': file.id,
                        'name': file.name,
                        'type': file.file_type
                    })
            
            if not texts:
                return {'error': 'No content to analyze'}
            
            # Local organization using embeddings
            embeddings = self.local_ml.embed_text(texts)
            
            # Simple clustering
            from sklearn.cluster import KMeans
            import numpy as np
            
            n_clusters = min(5, len(texts))
            if len(texts) >= 2:
                kmeans = KMeans(n_clusters=n_clusters, random_state=42)
                clusters = kmeans.fit_predict(embeddings)
                
                # Group files by cluster
                clustered_files = {}
                for i, cluster_id in enumerate(clusters):
                    cluster_id = int(cluster_id)
                    if cluster_id not in clustered_files:
                        clustered_files[cluster_id] = []
                    clustered_files[cluster_id].append(file_info[i])
                
                result = {
                    'method': 'local_clustering',
                    'clusters': clustered_files,
                    'n_clusters': n_clusters,
                    'suggestion': 'Group files by semantic similarity'
                }
                
                # Enhance with API if available and requested
                if use_api and self.llm:
                    try:
                        api_suggestion = self._api_organize_enhancement(file_info, clustered_files)
                        result['api_enhancement'] = api_suggestion
                        result['method'] = 'hybrid'
                    except Exception as e:
                        result['api_error'] = str(e)
                
                return result
            else:
                return {
                    'method': 'insufficient_data',
                    'message': 'Need at least 2 files to organize'
                }
        finally:
            session.close()
    
    def learn_from_training_block(self, block_id: int) -> Dict[str, Any]:
        """
        Learn from a training block.
        
        Args:
            block_id: Training block to learn from
            
        Returns:
            Learning results
        """
        # Use training block manager to train
        return self.training_block_manager.train_on_block(block_id, self.agent_id)
    
    def query_knowledge(
        self,
        question: str,
        use_training_blocks: bool = True,
        use_api: bool = False,
        owner_id: int = None
    ) -> Dict[str, Any]:
        """
        Answer a question using learned knowledge.
        
        Args:
            question: Question to answer
            use_training_blocks: Use enabled training blocks
            use_api: Use API if local confidence is low
            owner_id: Filter training blocks by owner
            
        Returns:
            Answer with metadata
        """
        if not question:
            return {'error': 'No question provided'}
        
        # Get context from enabled training blocks
        context_parts = []
        
        if use_training_blocks:
            enabled_blocks = self.training_block_manager.get_enabled_blocks(owner_id=owner_id)
            
            for block in enabled_blocks[:5]:  # Limit to 5 blocks to avoid huge context
                block_content = self.training_block_manager.get_block_contents(block.id)
                
                for content_item in block_content['contents'][:10]:  # Limit files per block
                    context_parts.append(content_item['content'][:500])  # First 500 chars
        
        if not context_parts:
            return {
                'answer': 'No knowledge available. Enable training blocks or add content.',
                'method': 'no_context',
                'confidence': 0.0
            }
        
        # Combine context
        context = '\n\n'.join(context_parts)
        
        # Try local QA first
        try:
            local_answer = self.local_ml.answer_question(question, context)
            
            # Check if we should enhance with API
            if use_api and self.llm and local_answer['score'] < 0.5:
                try:
                    api_answer = self._api_answer_question(question, context)
                    return {
                        'answer': api_answer,
                        'local_answer': local_answer['answer'],
                        'local_confidence': local_answer['score'],
                        'method': 'api_enhanced',
                        'reason': 'Low local confidence, used API'
                    }
                except Exception as e:
                    # API failed, return local answer with warning
                    local_answer['api_error'] = str(e)
                    local_answer['method'] = 'local_only'
                    return local_answer
            
            return local_answer
        except InferenceError as e:
            # Local QA failed, try API if available
            if use_api and self.llm:
                try:
                    api_answer = self._api_answer_question(question, context)
                    return {
                        'answer': api_answer,
                        'method': 'api_only',
                        'reason': f'Local QA failed: {str(e)}'
                    }
                except Exception as api_e:
                    return {
                        'error': f'Both local and API failed. Local: {str(e)}, API: {str(api_e)}'
                    }
            else:
                return {
                    'error': f'QA failed: {str(e)}',
                    'suggestion': 'Try upgrading to standard or full profile, or enable API'
                }
    
    def analyze_file_chain(self, filechain_id: int, use_api: bool = False) -> Dict[str, Any]:
        """
        Analyze a file chain for patterns and insights.
        
        Args:
            filechain_id: FileChain to analyze
            use_api: Use API for deeper analysis
            
        Returns:
            Analysis results
        """
        from core.database import FileChain
        
        session = db.get_session()
        try:
            chain = session.query(FileChain).filter_by(id=filechain_id).first()
            if not chain:
                return {'error': 'FileChain not found'}
            
            # Collect file contents
            texts = []
            for file in chain.files:
                if file.content:
                    texts.append(file.content)
            
            if not texts:
                return {'error': 'No content to analyze'}
            
            # Local analysis
            result = {
                'filechain_name': chain.name,
                'file_count': len(texts),
                'method': 'local'
            }
            
            # Generate chain summary
            if len(texts) == 1:
                summary = self.local_ml.summarize_text(texts[0])
                result['summary'] = summary.get('summary', '')
            else:
                # Combine and summarize
                combined = '\n\n'.join(texts)
                summary = self.local_ml.summarize_text(combined[:5000])  # Limit length
                result['summary'] = summary.get('summary', '')
            
            # Find patterns using embeddings
            if len(texts) >= 2:
                embeddings = self.local_ml.embed_text(texts)
                
                # Calculate average embedding
                import numpy as np
                avg_embedding = np.mean(embeddings, axis=0)
                
                # Find most representative file
                similarities = [
                    np.dot(emb, avg_embedding) / (np.linalg.norm(emb) * np.linalg.norm(avg_embedding))
                    for emb in embeddings
                ]
                most_representative_idx = int(np.argmax(similarities))
                
                result['most_representative_file'] = {
                    'index': most_representative_idx,
                    'name': chain.files[most_representative_idx].name,
                    'similarity': float(similarities[most_representative_idx])
                }
            
            # Enhance with API if requested
            if use_api and self.llm:
                try:
                    api_analysis = self._api_analyze_chain(chain, texts)
                    result['api_insights'] = api_analysis
                    result['method'] = 'hybrid'
                except Exception as e:
                    result['api_error'] = str(e)
            
            return result
        finally:
            session.close()
    
    def _api_call(self, prompt: str, max_tokens: int = 1000) -> str:
        """One place the provider is actually called.

        The three _api_* methods below each had their own inlined SDK call with
        the model name hardcoded three times. Routing them through the adapter
        means the vendor, the model and the call shape are all configuration
        rather than repetition."""
        text, _tokens = providers.chat(
            self.llm_provider, self.llm, prompt, max_tokens=max_tokens)
        return text

    def _api_answer_question(self, question: str, context: str) -> str:
        """Use the configured LLM provider to answer a question."""
        return self._api_call(
            f"Context:\n{context}\n\nQuestion: {question}\n\n"
            "Answer based only on the context provided:")
    
    def _api_organize_enhancement(self, file_info: List[Dict], clusters: Dict) -> str:
        """Use API to enhance organization suggestions."""
        prompt = f"Files to organize:\n"
        for info in file_info:
            prompt += f"- {info['name']} ({info['type']})\n"
        
        prompt += f"\nLocal clustering suggests {len(clusters)} groups. Provide better organization suggestions:"
        
        return self._api_call(prompt, max_tokens=500)
    
    def _api_analyze_chain(self, chain, texts: List[str]) -> str:
        """Use API to analyze file chain."""
        combined = '\n\n---\n\n'.join(texts[:5])  # Limit to 5 files
        
        prompt = f"Analyze this file chain '{chain.name}':\n\n{combined}\n\nProvide insights about patterns, themes, and relationships:"
        
        return self._api_call(prompt)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get agent capabilities."""
        local_caps = self.local_ml.get_capabilities()
        
        return {
            'agent_type': self.agent_type,
            'local_ml': local_caps,
            'api_available': self.llm is not None,
            'can_organize': True,
            'can_learn': True,
            'can_query': local_caps['qa'] or self.llm is not None,
            'can_analyze': True
        }
