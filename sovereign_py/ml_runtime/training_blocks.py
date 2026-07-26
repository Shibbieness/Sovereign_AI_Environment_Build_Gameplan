"""
Training Blocks System for ML Filesystem v1.8

Training blocks allow selective exposure of files to ML models.
Users can:
- Group files/filechains into training blocks
- Enable/disable blocks at will
- Designate blocks as 'rote' (facts) or 'process' (patterns)
- Train ML agents on specific blocks
"""

from typing import List, Dict, Optional, Set, Any
from datetime import datetime
import json
from pathlib import Path

from core.database import db, TrainingBlock, File, FileChain, MLAgent
from core.config import Config
from core.exceptions import TrainingBlockException, TrainingBlockNotFoundError
from ml.local_backend import LocalMLBackend


class TrainingBlockManager:
    """
    Manages training blocks and their relationship to ML models.
    """
    
    def __init__(self, local_ml: LocalMLBackend = None):
        self.local_ml = local_ml or LocalMLBackend()
        self.blocks_dir = Config.TRAINING_BLOCKS_DIR
        self.blocks_dir.mkdir(parents=True, exist_ok=True)
    
    def create_block(
        self,
        name: str,
        description: str,
        block_type: str,
        owner_id: int,
        enabled: bool = True
    ) -> TrainingBlock:
        """
        Create a new training block.
        
        Args:
            name: Block name
            description: Block description
            block_type: 'rote' or 'process'
            owner_id: User ID
            enabled: Start enabled or disabled
            
        Returns:
            Created TrainingBlock
        """
        if block_type not in ['rote', 'process']:
            raise TrainingBlockException(f"Invalid block_type: {block_type}. Must be 'rote' or 'process'")
        
        session = db.get_session()
        try:
            block = TrainingBlock(
                name=name,
                description=description,
                block_type=block_type,
                owner_id=owner_id,
                enabled=enabled
            )
            session.add(block)
            session.commit()
            session.refresh(block)
            
            print(f"✓ Created training block: {name} ({block_type})")
            return block
        finally:
            session.close()
    
    def get_block(self, block_id: int) -> TrainingBlock:
        """Get training block by ID."""
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                raise TrainingBlockNotFoundError(f"Training block {block_id} not found")
            return block
        finally:
            session.close()
    
    def list_blocks(self, owner_id: int = None, enabled_only: bool = False) -> List[TrainingBlock]:
        """List all training blocks."""
        session = db.get_session()
        try:
            query = session.query(TrainingBlock)
            
            if owner_id:
                query = query.filter_by(owner_id=owner_id)
            
            if enabled_only:
                query = query.filter_by(enabled=True)
            
            return query.all()
        finally:
            session.close()
    
    def add_file_to_block(self, block_id: int, file_id: int) -> bool:
        """Add a file to a training block."""
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                raise TrainingBlockNotFoundError(f"Block {block_id} not found")
            
            file = session.query(File).filter_by(id=file_id).first()
            if not file:
                raise TrainingBlockException(f"File {file_id} not found")
            
            # Check if already in block
            if file in block.files:
                print(f"File {file.name} already in block {block.name}")
                return False
            
            # Add file
            block.files.append(file)
            file.in_training_blocks = True
            block.update_counts()
            session.commit()
            
            print(f"✓ Added {file.name} to block {block.name}")
            return True
        finally:
            session.close()
    
    def remove_file_from_block(self, block_id: int, file_id: int) -> bool:
        """Remove a file from a training block."""
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                raise TrainingBlockNotFoundError(f"Block {block_id} not found")
            
            file = session.query(File).filter_by(id=file_id).first()
            if not file:
                return False
            
            if file not in block.files:
                return False
            
            # Remove file
            block.files.remove(file)
            
            # Check if file is in any other blocks
            if not session.query(TrainingBlock).join(TrainingBlock.files).filter(
                File.id == file_id
            ).first():
                file.in_training_blocks = False
            
            block.update_counts()
            session.commit()
            
            print(f"✓ Removed {file.name} from block {block.name}")
            return True
        finally:
            session.close()
    
    def add_filechain_to_block(self, block_id: int, filechain_id: int) -> bool:
        """Add an entire filechain to a training block."""
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                raise TrainingBlockNotFoundError(f"Block {block_id} not found")
            
            filechain = session.query(FileChain).filter_by(id=filechain_id).first()
            if not filechain:
                raise TrainingBlockException(f"FileChain {filechain_id} not found")
            
            # Check if already in block
            if filechain in block.filechains:
                print(f"FileChain {filechain.name} already in block {block.name}")
                return False
            
            # Add filechain
            block.filechains.append(filechain)
            block.update_counts()
            session.commit()
            
            print(f"✓ Added filechain {filechain.name} to block {block.name}")
            return True
        finally:
            session.close()
    
    def remove_filechain_from_block(self, block_id: int, filechain_id: int) -> bool:
        """Remove a filechain from a training block."""
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                raise TrainingBlockNotFoundError(f"Block {block_id} not found")
            
            filechain = session.query(FileChain).filter_by(id=filechain_id).first()
            if not filechain:
                return False
            
            if filechain not in block.filechains:
                return False
            
            # Remove filechain
            block.filechains.remove(filechain)
            block.update_counts()
            session.commit()
            
            print(f"✓ Removed filechain {filechain.name} from block {block.name}")
            return True
        finally:
            session.close()
    
    def toggle_block(self, block_id: int, enabled: bool = None) -> bool:
        """Enable or disable a training block."""
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                raise TrainingBlockNotFoundError(f"Block {block_id} not found")
            
            if enabled is None:
                # Toggle
                block.enabled = not block.enabled
            else:
                block.enabled = enabled
            
            session.commit()
            
            status = "enabled" if block.enabled else "disabled"
            print(f"✓ Training block '{block.name}' {status}")
            return block.enabled
        finally:
            session.close()
    
    def get_block_contents(self, block_id: int) -> Dict[str, Any]:
        """Get all content from a training block (for training)."""
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                raise TrainingBlockNotFoundError(f"Block {block_id} not found")
            
            # Collect all files (including those in filechains)
            all_files = block.get_all_files()
            
            # Extract content
            contents = []
            for file in all_files:
                if file.content:
                    contents.append({
                        'file_id': file.id,
                        'file_name': file.name,
                        'content': file.content,
                        'file_type': file.file_type,
                        'mime_type': file.mime_type
                    })
            
            return {
                'block_id': block.id,
                'block_name': block.name,
                'block_type': block.block_type,
                'enabled': block.enabled,
                'file_count': len(all_files),
                'contents': contents,
                'total_chars': sum(len(c['content']) for c in contents)
            }
        finally:
            session.close()
    
    def train_on_block(self, block_id: int, agent_id: int = None) -> Dict[str, Any]:
        """
        Train ML models on a training block.
        
        Args:
            block_id: Training block to train on
            agent_id: Specific agent to train (optional)
            
        Returns:
            Training results
        """
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                raise TrainingBlockNotFoundError(f"Block {block_id} not found")
            
            if not block.enabled:
                raise TrainingBlockException(f"Block '{block.name}' is disabled")
            
            # Get block contents
            block_data = self.get_block_contents(block_id)
            
            if not block_data['contents']:
                return {
                    'success': False,
                    'message': 'No content in training block',
                    'files_processed': 0
                }
            
            # Generate embeddings for all content
            embeddings_created = 0
            
            for content_item in block_data['contents']:
                if content_item['content']:
                    try:
                        # Generate embedding
                        embedding = self.local_ml.embed_text(content_item['content'])
                        
                        # Store embedding (this would go to vector DB)
                        # For now, just count
                        embeddings_created += 1
                    except Exception as e:
                        print(f"⚠️  Failed to embed {content_item['file_name']}: {e}")
            
            # Update block metadata
            block.last_trained = datetime.utcnow()
            block.total_tokens = block_data['total_chars'] // 4  # Rough estimate
            session.commit()
            
            return {
                'success': True,
                'block_name': block.name,
                'block_type': block.block_type,
                'files_processed': len(block_data['contents']),
                'embeddings_created': embeddings_created,
                'total_chars': block_data['total_chars'],
                'estimated_tokens': block.total_tokens
            }
        finally:
            session.close()
    
    def get_enabled_blocks(self, owner_id: int = None, block_type: str = None) -> List[TrainingBlock]:
        """Get all enabled training blocks."""
        session = db.get_session()
        try:
            query = session.query(TrainingBlock).filter_by(enabled=True)
            
            if owner_id:
                query = query.filter_by(owner_id=owner_id)
            
            if block_type:
                query = query.filter_by(block_type=block_type)
            
            return query.all()
        finally:
            session.close()
    
    def get_block_stats(self, block_id: int) -> Dict[str, Any]:
        """Get statistics for a training block."""
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                raise TrainingBlockNotFoundError(f"Block {block_id} not found")
            
            # Get all files
            all_files = block.get_all_files()
            
            # Calculate stats
            total_size = sum(f.size for f in all_files if f.size)
            file_types = {}
            for f in all_files:
                ft = f.file_type or 'unknown'
                file_types[ft] = file_types.get(ft, 0) + 1
            
            return {
                'block_id': block.id,
                'block_name': block.name,
                'block_type': block.block_type,
                'enabled': block.enabled,
                'direct_files': len(block.files),
                'filechains': len(block.filechains),
                'total_files': len(all_files),
                'total_size_bytes': total_size,
                'file_types': file_types,
                'last_trained': block.last_trained.isoformat() if block.last_trained else None,
                'estimated_tokens': block.total_tokens
            }
        finally:
            session.close()
    
    def export_block(self, block_id: int, output_path: Path = None) -> Path:
        """Export training block to JSON file."""
        block_data = self.get_block_contents(block_id)
        
        if output_path is None:
            output_path = self.blocks_dir / f"block_{block_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_path, 'w') as f:
            json.dump(block_data, f, indent=2)
        
        print(f"✓ Exported training block to {output_path}")
        return output_path
    
    def delete_block(self, block_id: int) -> bool:
        """Delete a training block."""
        session = db.get_session()
        try:
            block = session.query(TrainingBlock).filter_by(id=block_id).first()
            if not block:
                return False
            
            block_name = block.name
            session.delete(block)
            session.commit()
            
            print(f"✓ Deleted training block: {block_name}")
            return True
        finally:
            session.close()
