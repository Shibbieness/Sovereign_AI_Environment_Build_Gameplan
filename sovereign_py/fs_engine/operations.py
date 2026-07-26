"""
Semantic Filesystem Operations for ML Filesystem v1.8

Provides file operations with semantic understanding:
- CRUD operations
- Sandboxed storage
- Semantic search
- Automatic tagging
"""

import os
import shutil
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

from core.config import Config
from core.database import db, File, User, Tag
from core.exceptions import (
    FileNotFoundError, FileAlreadyExistsError, 
    InvalidPathError, FileSizeLimitExceeded, SandboxViolation
)
from ml.local_backend import LocalMLBackend


class SemanticFileSystem:
    """
    Semantic filesystem with ML integration.
    All file operations are sandboxed and tracked.
    """
    
    def __init__(self, local_ml: LocalMLBackend = None, chroma_manager=None):
        self.sandbox_root = Config.SANDBOX_ROOT
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self.local_ml = local_ml or LocalMLBackend()
        # Optional vector store. When present, semantic search is served from
        # ChromaDB's index instead of brute-force in-process similarity.
        self.chroma_manager = chroma_manager
    
    def _get_real_path(self, virtual_path: str) -> Path:
        """Convert virtual path to real sandboxed path."""
        # Remove leading slash
        virtual_path = virtual_path.lstrip('/')
        
        # Construct real path
        real_path = (self.sandbox_root / virtual_path).resolve()
        
        # Ensure within sandbox
        try:
            real_path.relative_to(self.sandbox_root)
        except ValueError:
            raise SandboxViolation(f"Path outside sandbox: {virtual_path}")
        
        return real_path
    
    def _get_virtual_path(self, real_path: Path) -> str:
        """Convert real path to virtual path."""
        try:
            rel_path = real_path.relative_to(self.sandbox_root)
            return '/' + str(rel_path)
        except ValueError:
            raise SandboxViolation("Path outside sandbox")
    
    def create_file(
        self,
        path: str,
        content: str,
        owner_id: int,
        mime_type: str = None,
        tags: List[str] = None
    ) -> File:
        """
        Create a new file.
        
        Args:
            path: Virtual file path
            content: File content
            owner_id: Owner user ID
            mime_type: MIME type (auto-detected if not provided)
            tags: List of tag names
            
        Returns:
            Created File object
        """
        real_path = self._get_real_path(path)
        
        # Check if exists
        if real_path.exists():
            raise FileAlreadyExistsError(f"File already exists: {path}")
        
        # Check size
        content_size = len(content.encode('utf-8'))
        if content_size > Config.MAX_FILE_SIZE:
            raise FileSizeLimitExceeded(f"File too large: {content_size} bytes")
        
        # Create parent directories
        real_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Detect MIME type
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(path)
            mime_type = mime_type or 'text/plain'
        
        # Determine file type
        file_type = self._categorize_file(mime_type, content)
        
        # Write file
        real_path.write_text(content, encoding='utf-8')
        
        # Create database entry
        session = db.get_session()
        try:
            file = File(
                name=real_path.name,
                path=path,
                content=content,
                size=content_size,
                mime_type=mime_type,
                file_type=file_type,
                owner_id=owner_id
            )
            
            # Generate hash
            file.generate_hash()
            
            # Add tags
            if tags:
                for tag_name in tags:
                    tag = session.query(Tag).filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        session.add(tag)
                    file.tags.append(tag)
            
            session.add(file)
            session.commit()
            session.refresh(file)
            
            print(f"✓ Created file: {path}")
            return file
        finally:
            session.close()
    
    def read_file(self, file_id: int) -> Dict[str, Any]:
        """Read file content and metadata."""
        session = db.get_session()
        try:
            file = session.query(File).filter_by(id=file_id).first()
            if not file:
                raise FileNotFoundError(f"File {file_id} not found")
            
            # Update access time
            file.accessed_at = datetime.utcnow()
            session.commit()
            
            return {
                'id': file.id,
                'name': file.name,
                'path': file.path,
                'content': file.content,
                'size': file.size,
                'mime_type': file.mime_type,
                'file_type': file.file_type,
                'tags': [tag.name for tag in file.tags],
                'created_at': file.created_at.isoformat() if file.created_at else None,
                'modified_at': file.modified_at.isoformat() if file.modified_at else None
            }
        finally:
            session.close()
    
    def update_file(self, file_id: int, content: str) -> File:
        """Update file content."""
        session = db.get_session()
        try:
            file = session.query(File).filter_by(id=file_id).first()
            if not file:
                raise FileNotFoundError(f"File {file_id} not found")
            
            # Check size
            content_size = len(content.encode('utf-8'))
            if content_size > Config.MAX_FILE_SIZE:
                raise FileSizeLimitExceeded(f"File too large: {content_size} bytes")
            
            # Update file on disk
            real_path = self._get_real_path(file.path)
            real_path.write_text(content, encoding='utf-8')
            
            # Update database
            file.content = content
            file.size = content_size
            file.generate_hash()
            file.modified_at = datetime.utcnow()
            file.embedding_generated = False  # Need to regenerate
            
            session.commit()
            
            print(f"✓ Updated file: {file.path}")
            return file
        finally:
            session.close()
    
    def delete_file(self, file_id: int) -> bool:
        """Delete a file."""
        session = db.get_session()
        try:
            file = session.query(File).filter_by(id=file_id).first()
            if not file:
                return False
            
            # Delete from disk
            real_path = self._get_real_path(file.path)
            if real_path.exists():
                real_path.unlink()
            
            # Delete from database
            session.delete(file)
            session.commit()
            
            print(f"✓ Deleted file: {file.path}")
            return True
        finally:
            session.close()
    
    def move_file(self, file_id: int, new_path: str) -> File:
        """Move/rename a file."""
        session = db.get_session()
        try:
            file = session.query(File).filter_by(id=file_id).first()
            if not file:
                raise FileNotFoundError(f"File {file_id} not found")
            
            old_real_path = self._get_real_path(file.path)
            new_real_path = self._get_real_path(new_path)
            
            # Check if target exists
            if new_real_path.exists():
                raise FileAlreadyExistsError(f"Target already exists: {new_path}")
            
            # Create parent directories
            new_real_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            shutil.move(str(old_real_path), str(new_real_path))
            
            # Update database
            file.path = new_path
            file.name = new_real_path.name
            file.modified_at = datetime.utcnow()
            
            session.commit()
            
            print(f"✓ Moved file: {file.path} → {new_path}")
            return file
        finally:
            session.close()
    
    def list_directory(self, path: str = '/') -> List[Dict[str, Any]]:
        """List files in a directory."""
        real_path = self._get_real_path(path)
        
        if not real_path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        
        if not real_path.is_dir():
            raise InvalidPathError(f"Not a directory: {path}")
        
        # List files from database
        session = db.get_session()
        try:
            # Get all files under this path
            pattern = path.rstrip('/') + '/%'
            files = session.query(File).filter(File.path.like(pattern)).all()
            
            return [file.to_dict() for file in files]
        finally:
            session.close()
    
    def search_files(
        self,
        query: str,
        semantic: bool = True,
        owner_id: int = None,
        file_type: str = None,
        tags: List[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search files with semantic understanding.
        
        Args:
            query: Search query
            semantic: Use semantic search (True) or keyword (False)
            owner_id: Filter by owner
            file_type: Filter by file type
            tags: Filter by tags
            limit: Max results
            
        Returns:
            List of matching files
        """
        session = db.get_session()
        try:
            if semantic:
                # Semantic search using embeddings
                return self._semantic_search(query, owner_id, file_type, tags, limit, session)
            else:
                # Simple keyword search
                return self._keyword_search(query, owner_id, file_type, tags, limit, session)
        finally:
            session.close()
    
    def _semantic_search(
        self,
        query: str,
        owner_id: int,
        file_type: str,
        tags: List[str],
        limit: int,
        session
    ) -> List[Dict[str, Any]]:
        """Semantic search using embeddings."""
        if self.chroma_manager is not None:
            return self._chroma_search(query, owner_id, file_type, tags, limit, session)
        return self._brute_force_semantic_search(query, owner_id, file_type, tags, limit, session)

    def _chroma_search(
        self,
        query: str,
        owner_id: int,
        file_type: str,
        tags: List[str],
        limit: int,
        session
    ) -> List[Dict[str, Any]]:
        """Semantic search served from the ChromaDB vector index."""
        filter_metadata = {}
        if owner_id:
            filter_metadata['owner_id'] = owner_id
        if file_type:
            filter_metadata['file_type'] = file_type

        matches = self.chroma_manager.search_similar_files(
            query, n_results=limit, filter_metadata=filter_metadata or None
        )

        results = []
        for match in matches:
            file = session.query(File).filter_by(id=match['file_id']).first()
            if not file:
                continue
            if tags and not ({t.name for t in file.tags} & set(tags)):
                continue
            result = file.to_dict()
            result['similarity'] = 1.0 - match['distance'] if match.get('distance') is not None else None
            result['match_reason'] = 'semantic_vector'
            results.append(result)

        return results

    def _brute_force_semantic_search(
        self,
        query: str,
        owner_id: int,
        file_type: str,
        tags: List[str],
        limit: int,
        session
    ) -> List[Dict[str, Any]]:
        """Semantic search using in-process embedding similarity (no vector store)."""
        # Get all files (with filters)
        query_obj = session.query(File)
        
        if owner_id:
            query_obj = query_obj.filter_by(owner_id=owner_id)
        
        if file_type:
            query_obj = query_obj.filter_by(file_type=file_type)
        
        if tags:
            query_obj = query_obj.join(File.tags).filter(Tag.name.in_(tags))
        
        files = query_obj.all()
        
        if not files:
            return []
        
        # Get file contents
        texts = []
        file_map = {}
        for file in files:
            if file.content:
                texts.append(file.content[:1000])  # First 1000 chars
                file_map[len(texts)-1] = file
        
        if not texts:
            return []
        
        # Find similar using local ML
        similar = self.local_ml.find_similar_texts(query, texts, top_k=limit)
        
        # Map back to files
        results = []
        for item in similar:
            file = file_map[item['index']]
            result = file.to_dict()
            result['similarity'] = item['similarity']
            result['match_reason'] = 'semantic'
            results.append(result)
        
        return results
    
    def _keyword_search(
        self,
        query: str,
        owner_id: int,
        file_type: str,
        tags: List[str],
        limit: int,
        session
    ) -> List[Dict[str, Any]]:
        """Simple keyword search."""
        query_obj = session.query(File).filter(
            File.content.contains(query) | File.name.contains(query)
        )
        
        if owner_id:
            query_obj = query_obj.filter_by(owner_id=owner_id)
        
        if file_type:
            query_obj = query_obj.filter_by(file_type=file_type)
        
        if tags:
            query_obj = query_obj.join(File.tags).filter(Tag.name.in_(tags))
        
        files = query_obj.limit(limit).all()
        return [file.to_dict() for file in files]
    
    def _categorize_file(self, mime_type: str, content: str = None) -> str:
        """Categorize file into type."""
        if mime_type.startswith('text/'):
            if content:
                # Use ML to detect if it's code
                classification = self.local_ml.classify_text_type(content)
                if classification.get('code', 0) > 0.5:
                    return 'code'
            return 'document'
        elif mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif mime_type.startswith('application/'):
            if 'pdf' in mime_type:
                return 'document'
            elif 'json' in mime_type or 'xml' in mime_type:
                return 'data'
            else:
                return 'binary'
        else:
            return 'other'
    
    def generate_embedding(self, file_id: int) -> bool:
        """Generate embedding for a file."""
        session = db.get_session()
        try:
            file = session.query(File).filter_by(id=file_id).first()
            if not file or not file.content:
                return False
            
            # Generate embedding
            embedding = self.local_ml.embed_text(file.content)
            
            # Store in FileEmbedding table
            from core.database import FileEmbedding
            import pickle
            
            file_embedding = FileEmbedding(
                file_id=file.id,
                model_name='all-MiniLM-L6-v2',
                embedding=pickle.dumps(embedding),
                dimension=len(embedding)
            )
            
            session.add(file_embedding)
            file.embedding_generated = True
            file.last_embedded = datetime.utcnow()
            session.commit()
            
            return True
        finally:
            session.close()
