"""
Enhanced FileChain System for ML Filesystem v1.8

FileChains group related files and provide:
- Automatic summarization
- Q&A over chain contents
- Related file suggestions
- Training block integration
"""

from typing import List, Dict, Optional, Any
from datetime import datetime

from core.database import db, FileChain, File
from core.exceptions import FileNotFoundError
from ml.local_backend import LocalMLBackend


class FileChainManager:
    """
    Manages file chains with ML enhancement.
    """
    
    def __init__(self, local_ml: LocalMLBackend = None):
        self.local_ml = local_ml or LocalMLBackend()
    
    def create_chain(
        self,
        name: str,
        description: str,
        owner_id: int,
        file_ids: List[int] = None
    ) -> FileChain:
        """Create a new file chain."""
        session = db.get_session()
        try:
            chain = FileChain(
                name=name,
                description=description,
                owner_id=owner_id
            )
            
            # Add files if provided
            if file_ids:
                files = session.query(File).filter(File.id.in_(file_ids)).all()
                chain.files.extend(files)
            
            session.add(chain)
            session.commit()
            session.refresh(chain)
            
            # Generate initial summary
            if chain.files:
                self.regenerate_summary(chain.id)
            
            print(f"✓ Created file chain: {name}")
            return chain
        finally:
            session.close()
    
    def add_file(self, chain_id: int, file_id: int) -> bool:
        """Add a file to a chain."""
        session = db.get_session()
        try:
            chain = session.query(FileChain).filter_by(id=chain_id).first()
            if not chain:
                return False
            
            file = session.query(File).filter_by(id=file_id).first()
            if not file:
                return False
            
            if file in chain.files:
                return False
            
            chain.files.append(file)
            chain.modified_at = datetime.utcnow()
            session.commit()
            
            # Regenerate summary
            self.regenerate_summary(chain_id)
            
            print(f"✓ Added {file.name} to chain {chain.name}")
            return True
        finally:
            session.close()
    
    def remove_file(self, chain_id: int, file_id: int) -> bool:
        """Remove a file from a chain."""
        session = db.get_session()
        try:
            chain = session.query(FileChain).filter_by(id=chain_id).first()
            if not chain:
                return False
            
            file = session.query(File).filter_by(id=file_id).first()
            if not file or file not in chain.files:
                return False
            
            chain.files.remove(file)
            chain.modified_at = datetime.utcnow()
            session.commit()
            
            # Regenerate summary
            self.regenerate_summary(chain_id)
            
            print(f"✓ Removed {file.name} from chain {chain.name}")
            return True
        finally:
            session.close()
    
    def regenerate_summary(self, chain_id: int) -> Optional[str]:
        """Generate/update chain summary."""
        session = db.get_session()
        try:
            chain = session.query(FileChain).filter_by(id=chain_id).first()
            if not chain:
                return None
            
            if not chain.files:
                chain.summary = "Empty chain"
                session.commit()
                return chain.summary
            
            # Collect file contents
            contents = []
            for file in chain.files:
                if file.content:
                    contents.append(f"File: {file.name}\n{file.content[:500]}")
            
            if not contents:
                chain.summary = "No content available"
                session.commit()
                return chain.summary
            
            # Combine and summarize
            combined = '\n\n'.join(contents)
            summary_result = self.local_ml.summarize_text(combined[:5000])  # Limit size
            
            chain.summary = summary_result.get('summary', '')
            chain.embedding_generated = False  # Need to regenerate embedding
            session.commit()
            
            return chain.summary
        finally:
            session.close()
    
    def query_chain(self, chain_id: int, question: str) -> Dict[str, Any]:
        """Ask a question about the chain."""
        session = db.get_session()
        try:
            chain = session.query(FileChain).filter_by(id=chain_id).first()
            if not chain:
                return {'error': 'Chain not found'}
            
            # Collect file contents
            context_parts = []
            for file in chain.files:
                if file.content:
                    context_parts.append(file.content)
            
            if not context_parts:
                return {'error': 'No content in chain'}
            
            # Combine context
            context = '\n\n'.join(context_parts)
            
            # Answer question
            answer = self.local_ml.answer_question(question, context)
            
            return {
                'chain_name': chain.name,
                'question': question,
                'answer': answer['answer'],
                'confidence': answer.get('score', 0),
                'sources': [f.name for f in chain.files],
                'method': answer.get('method', 'local')
            }
        finally:
            session.close()
    
    def find_related_files(self, chain_id: int, file_id: int, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Find if a file is related to a chain.
        
        Args:
            chain_id: Chain ID
            file_id: File to check
            threshold: Similarity threshold
            
        Returns:
            Suggestion with similarity score
        """
        session = db.get_session()
        try:
            chain = session.query(FileChain).filter_by(id=chain_id).first()
            if not chain or not chain.files:
                return []
            
            file = session.query(File).filter_by(id=file_id).first()
            if not file or not file.content:
                return []
            
            # Get chain file contents
            chain_contents = []
            for chain_file in chain.files:
                if chain_file.content:
                    chain_contents.append(chain_file.content[:500])
            
            if not chain_contents:
                return []
            
            # Check similarity
            similarities = self.local_ml.find_similar_texts(
                file.content[:500],
                chain_contents,
                top_k=5
            )
            
            # Filter by threshold
            related = [s for s in similarities if s['similarity'] > threshold]
            
            if related:
                return [{
                    'related': True,
                    'max_similarity': related[0]['similarity'],
                    'similar_to': related[0]['text'][:100],
                    'suggestion': f"Consider adding to chain '{chain.name}'"
                }]
            
            return []
        finally:
            session.close()
    
    def get_chain(self, chain_id: int) -> Optional[Dict[str, Any]]:
        """Get chain with full details."""
        session = db.get_session()
        try:
            chain = session.query(FileChain).filter_by(id=chain_id).first()
            if not chain:
                return None
            
            return {
                'id': chain.id,
                'name': chain.name,
                'description': chain.description,
                'summary': chain.summary,
                'file_count': len(chain.files),
                'files': [f.to_dict() for f in chain.files],
                'created_at': chain.created_at.isoformat() if chain.created_at else None,
                'modified_at': chain.modified_at.isoformat() if chain.modified_at else None,
                'training_blocks': [tb.name for tb in chain.training_blocks]
            }
        finally:
            session.close()
    
    def list_chains(self, owner_id: int = None) -> List[Dict[str, Any]]:
        """List all chains."""
        session = db.get_session()
        try:
            query = session.query(FileChain)
            
            if owner_id:
                query = query.filter_by(owner_id=owner_id)
            
            chains = query.all()
            return [chain.to_dict() for chain in chains]
        finally:
            session.close()
    
    def delete_chain(self, chain_id: int) -> bool:
        """Delete a chain (files are preserved)."""
        session = db.get_session()
        try:
            chain = session.query(FileChain).filter_by(id=chain_id).first()
            if not chain:
                return False
            
            chain_name = chain.name
            session.delete(chain)
            session.commit()
            
            print(f"✓ Deleted chain: {chain_name}")
            return True
        finally:
            session.close()
