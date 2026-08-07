"""
Local ML Backend for ML Filesystem v1.8
Provides offline ML capabilities using local models.
"""

import numpy as np
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from core.config import Config
from core.exceptions import InferenceError, EmbeddingError
from ml.model_manager import MLModelManager


class LocalMLBackend:
    """
    Local ML backend providing offline inference.
    
    Features:
    - Text embeddings (always available)
    - Question answering (standard/full profiles)
    - Summarization (full profile only)
    - Fast, private, no API costs
    """
    
    def __init__(self, model_manager: MLModelManager = None):
        self.model_manager = model_manager or MLModelManager()
        self.profile = self.model_manager.profile
        
        # Lazy-loaded models
        self._embedder = None
        self._qa_model = None
        self._summarizer = None
    
    @property
    def embedder(self):
        """Lazy load embedder."""
        if self._embedder is None:
            self._embedder = self.model_manager.load_model('embedder')
        return self._embedder
    
    @property
    def qa_model(self):
        """Lazy load QA model."""
        if self._qa_model is None and self.profile in ['standard', 'full']:
            self._qa_model = self.model_manager.load_model('qa')
        return self._qa_model
    
    @property
    def summarizer(self):
        """Lazy load summarizer."""
        if self._summarizer is None and self.profile == 'full':
            self._summarizer = self.model_manager.load_model('summarizer')
        return self._summarizer
    
    def embed_text(self, text: Union[str, List[str]], batch_size: int = None) -> np.ndarray:
        """
        Generate embeddings for text.
        
        Args:
            text: Single text or list of texts
            batch_size: Batch size for encoding
            
        Returns:
            Numpy array of embeddings
        """
        if not text:
            raise EmbeddingError("No text provided")
        
        batch_size = batch_size or Config.EMBEDDING_BATCH_SIZE
        
        try:
            if isinstance(text, str):
                embedding = self.embedder.encode([text], batch_size=batch_size, show_progress_bar=False)
                return embedding[0]
            else:
                embeddings = self.embedder.encode(text, batch_size=batch_size, show_progress_bar=False)
                return embeddings
        except Exception as e:
            raise EmbeddingError(f"Failed to generate embeddings: {str(e)}")
    
    def semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts.
        
        Returns:
            Similarity score (0-1)
        """
        try:
            emb1 = self.embed_text(text1)
            emb2 = self.embed_text(text2)
            
            # Cosine similarity
            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            return float(similarity)
        except Exception as e:
            raise InferenceError(f"Failed to calculate similarity: {str(e)}")
    
    def answer_question(self, question: str, context: str, max_answer_length: int = 100) -> Dict[str, Any]:
        """
        Answer a question based on context.
        
        Args:
            question: Question to answer
            context: Context containing the answer
            max_answer_length: Maximum answer length
            
        Returns:
            Dict with answer, score, start, end positions
        """
        if self.qa_model is None:
            return {
                'error': 'QA model not available',
                'suggestion': 'Upgrade to standard or full profile',
                'answer': None,
                'score': 0.0
            }
        
        if not question or not context:
            raise InferenceError("Question and context required")
        
        # Truncate context if too long (model limitation)
        max_context_length = 512
        if len(context) > max_context_length * 4:  # Rough char to token estimate
            context = context[:max_context_length * 4]
        
        try:
            result = self.qa_model(
                question=question,
                context=context,
                max_answer_len=max_answer_length
            )
            
            return {
                'answer': result['answer'],
                'score': float(result['score']),
                'start': result.get('start'),
                'end': result.get('end'),
                'method': 'local_qa',
                'model': 'distilbert-squad'
            }
        except Exception as e:
            raise InferenceError(f"QA failed: {str(e)}")
    
    def summarize_text(self, text: str, max_length: int = 130, min_length: int = 30) -> Dict[str, Any]:
        """
        Summarize text.
        
        Args:
            text: Text to summarize
            max_length: Maximum summary length
            min_length: Minimum summary length
            
        Returns:
            Dict with summary and metadata
        """
        if self.summarizer is None:
            return {
                'error': 'Summarizer not available',
                'suggestion': 'Upgrade to full profile',
                'summary': None
            }
        
        if not text:
            return {'summary': '', 'method': 'empty'}
        
        # Too short to summarize
        if len(text.split()) < 50:
            return {
                'summary': text,
                'method': 'too_short',
                'note': 'Text too short to summarize'
            }
        
        try:
            # Chunk if necessary
            max_input_length = 1024
            if len(text.split()) > max_input_length:
                chunks = self._chunk_text(text, max_input_length)
                summaries = []
                
                for chunk in chunks:
                    result = self.summarizer(
                        chunk,
                        max_length=max_length,
                        min_length=min_length,
                        do_sample=False
                    )
                    summaries.append(result[0]['summary_text'])
                
                # If multiple summaries, combine them
                if len(summaries) == 1:
                    final_summary = summaries[0]
                else:
                    combined = ' '.join(summaries)
                    # Summarize the summaries if needed
                    if len(combined.split()) > max_length:
                        result = self.summarizer(
                            combined,
                            max_length=max_length,
                            min_length=min_length,
                            do_sample=False
                        )
                        final_summary = result[0]['summary_text']
                    else:
                        final_summary = combined
                
                return {
                    'summary': final_summary,
                    'method': 'local_chunked',
                    'chunks': len(chunks),
                    'model': 'bart-cnn'
                }
            else:
                result = self.summarizer(
                    text,
                    max_length=max_length,
                    min_length=min_length,
                    do_sample=False
                )
                
                return {
                    'summary': result[0]['summary_text'],
                    'method': 'local',
                    'model': 'bart-cnn'
                }
        except Exception as e:
            raise InferenceError(f"Summarization failed: {str(e)}")
    
    def _chunk_text(self, text: str, max_words: int) -> List[str]:
        """Chunk text into smaller pieces."""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), max_words):
            chunk = ' '.join(words[i:i + max_words])
            chunks.append(chunk)
        
        return chunks
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Extract keywords using embeddings.
        Simple approach: find words with highest embedding norm.
        """
        try:
            # Split into sentences
            sentences = text.split('.')
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if not sentences:
                return []
            
            # Get embeddings for sentences
            embeddings = self.embed_text(sentences)
            
            # Calculate importance (simplified: use embedding magnitude)
            importance = np.linalg.norm(embeddings, axis=1)
            
            # Get top sentences
            top_indices = np.argsort(importance)[-top_k:][::-1]
            
            keywords = []
            for idx in top_indices:
                keywords.append({
                    'text': sentences[idx],
                    'importance': float(importance[idx]),
                    'index': int(idx)
                })
            
            return keywords
        except Exception as e:
            raise InferenceError(f"Keyword extraction failed: {str(e)}")
    
    def classify_text_type(self, text: str) -> Dict[str, float]:
        """
        Classify text type using embedding similarity.
        
        Returns probabilities for: code, prose, data, mixed
        """
        try:
            # Reference texts for each type
            reference_texts = {
                'code': 'def function(): return value',
                'prose': 'This is a well-written sentence with proper grammar.',
                'data': '123, 456, 789, name, value, key',
                'technical': 'algorithm implementation using data structures'
            }
            
            # Get text embedding
            text_emb = self.embed_text(text)
            
            # Get reference embeddings
            ref_embeddings = self.embed_text(list(reference_texts.values()))
            
            # Calculate similarities
            similarities = {}
            for i, (label, _) in enumerate(reference_texts.items()):
                sim = np.dot(text_emb, ref_embeddings[i]) / (
                    np.linalg.norm(text_emb) * np.linalg.norm(ref_embeddings[i])
                )
                similarities[label] = float(sim)
            
            # Normalize to probabilities
            total = sum(similarities.values())
            if total > 0:
                probabilities = {k: v/total for k, v in similarities.items()}
            else:
                probabilities = similarities
            
            return probabilities
        except Exception as e:
            return {'error': str(e)}
    
    def find_similar_texts(self, query: str, texts: List[str], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find most similar texts to query.
        
        Args:
            query: Query text
            texts: List of texts to search
            top_k: Number of results to return
            
        Returns:
            List of dicts with text and similarity score
        """
        if not texts:
            return []
        
        try:
            # Get query embedding
            query_emb = self.embed_text(query)
            
            # Get text embeddings
            text_embeddings = self.embed_text(texts)
            
            # Calculate similarities
            similarities = []
            for i, text_emb in enumerate(text_embeddings):
                sim = np.dot(query_emb, text_emb) / (
                    np.linalg.norm(query_emb) * np.linalg.norm(text_emb)
                )
                similarities.append({
                    'text': texts[i],
                    'similarity': float(sim),
                    'index': i
                })
            
            # Sort by similarity
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            
            return similarities[:top_k]
        except Exception as e:
            raise InferenceError(f"Similarity search failed: {str(e)}")
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get available capabilities for current profile."""
        return {
            'embeddings': True,  # Always available
            'semantic_search': True,  # Always available
            'similarity': True,  # Always available
            'qa': self.profile in ['standard', 'full'],
            'summarization': self.profile == 'full',
            'offline': True
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get backend statistics."""
        return {
            'profile': self.profile,
            'capabilities': self.get_capabilities(),
            'models_loaded': self.model_manager.get_loaded_models(),
            'model_info': self.model_manager.get_model_info()
        }
