"""
ML Filesystem - Filesystem Manager
Handles all file operations with sandboxing and security.
"""

import os
import shutil
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import magic
from models import File, User, Tag, FileChain, ActivityLog, Database


class FileSystemManager:
    """
    Manages filesystem operations with sandboxing and security.
    All file operations are restricted to the sandbox directory.
    """
    
    def __init__(self, sandbox_root: str = './sandbox', db: Database = None):
        """
        Initialize filesystem manager.
        
        Args:
            sandbox_root: Root directory for sandboxed filesystem
            db: Database instance
        """
        self.sandbox_root = Path(sandbox_root).resolve()
        self.db = db or Database()
        
        # Create sandbox if it doesn't exist
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        
        # Initialize mime type detection
        mimetypes.init()
        
    def _get_real_path(self, virtual_path: str) -> Path:
        """
        Convert virtual path to real sandboxed path.
        
        Args:
            virtual_path: Virtual path in the system
            
        Returns:
            Real filesystem path within sandbox
            
        Raises:
            SecurityError: If path escapes sandbox
        """
        # Normalize the virtual path
        virtual_path = virtual_path.lstrip('/')
        
        # Construct real path
        real_path = (self.sandbox_root / virtual_path).resolve()
        
        # Security check - ensure path is within sandbox
        if not str(real_path).startswith(str(self.sandbox_root)):
            raise SecurityError(f"Path escape attempt detected: {virtual_path}")
        
        return real_path
    
    def _detect_mime_type(self, file_path: Path) -> str:
        """
        Detect MIME type of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            MIME type string
        """
        try:
            # Try python-magic first (more accurate)
            mime = magic.Magic(mime=True)
            return mime.from_file(str(file_path))
        except:
            # Fallback to mimetypes
            mime_type, _ = mimetypes.guess_type(str(file_path))
            return mime_type or 'application/octet-stream'
    
    def _determine_file_type(self, mime_type: str, file_name: str) -> str:
        """
        Determine high-level file type from MIME type.
        
        Args:
            mime_type: MIME type string
            file_name: Name of the file
            
        Returns:
            File type category
        """
        extension = Path(file_name).suffix.lower()
        
        # Text files
        if mime_type.startswith('text/') or extension in ['.txt', '.md', '.rst']:
            return 'text'
        
        # Code files
        code_extensions = [
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.h',
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
            '.sh', '.bash', '.zsh', '.fish', '.html', '.css', '.scss', '.sass',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.conf'
        ]
        if extension in code_extensions:
            return 'code'
        
        # Documents
        if mime_type in ['application/pdf'] or extension == '.pdf':
            return 'pdf'
        if extension in ['.doc', '.docx', '.odt']:
            return 'document'
        if extension in ['.xls', '.xlsx', '.ods']:
            return 'spreadsheet'
        if extension in ['.ppt', '.pptx', '.odp']:
            return 'presentation'
        
        # Images
        if mime_type.startswith('image/'):
            return 'image'
        
        # Audio
        if mime_type.startswith('audio/'):
            return 'audio'
        
        # Video
        if mime_type.startswith('video/'):
            return 'video'
        
        # Archives
        if extension in ['.zip', '.tar', '.gz', '.bz2', '.7z', '.rar']:
            return 'archive'
        
        return 'other'
    
    def create_file(self, virtual_path: str, content: str, user_id: int,
                   tags: List[str] = None, metadata: Dict = None) -> File:
        """
        Create a new file.
        
        Args:
            virtual_path: Virtual path for the file
            content: File content
            user_id: Owner user ID
            tags: Optional list of tag names
            metadata: Optional metadata dictionary
            
        Returns:
            Created File object
        """
        session = self.db.get_session()
        
        try:
            # Check if file already exists
            existing = session.query(File).filter_by(path=virtual_path).first()
            if existing:
                raise FileExistsError(f"File already exists: {virtual_path}")
            
            # Create real file
            real_path = self._get_real_path(virtual_path)
            real_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Detect MIME type and file type
            mime_type = self._detect_mime_type(real_path)
            file_type = self._determine_file_type(mime_type, virtual_path)
            
            # Get parent directory
            parent_path = str(Path(virtual_path).parent)
            if parent_path == '.':
                parent_path = '/'
            parent = session.query(File).filter_by(path=parent_path, is_directory=True).first()
            
            # Create file record
            file_obj = File(
                name=Path(virtual_path).name,
                path=virtual_path,
                file_type=file_type,
                mime_type=mime_type,
                size=len(content),
                content=content if len(content) < 1000000 else None,  # Store in DB if < 1MB
                storage_path=str(real_path) if len(content) >= 1000000 else None,
                owner_id=user_id,
                parent_id=parent.id if parent else None,
                ml_metadata=metadata or {}
            )
            
            file_obj.update_hash()
            
            # Add tags
            if tags:
                for tag_name in tags:
                    tag = session.query(Tag).filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        session.add(tag)
                    file_obj.tags.append(tag)
            
            session.add(file_obj)
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                file_id=file_obj.id,
                action='create_file',
                details={'path': virtual_path, 'size': file_obj.size}
            )
            session.add(log)
            
            session.commit()
            return file_obj
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_directory(self, virtual_path: str, user_id: int) -> File:
        """
        Create a new directory.
        
        Args:
            virtual_path: Virtual path for the directory
            user_id: Owner user ID
            
        Returns:
            Created File object (directory)
        """
        session = self.db.get_session()
        
        try:
            # Check if directory already exists
            existing = session.query(File).filter_by(path=virtual_path).first()
            if existing:
                raise FileExistsError(f"Directory already exists: {virtual_path}")
            
            # Create real directory
            real_path = self._get_real_path(virtual_path)
            real_path.mkdir(parents=True, exist_ok=True)
            
            # Get parent directory
            parent_path = str(Path(virtual_path).parent)
            if parent_path == '.':
                parent_path = '/'
            parent = session.query(File).filter_by(path=parent_path, is_directory=True).first()
            
            # Create directory record
            dir_obj = File(
                name=Path(virtual_path).name,
                path=virtual_path,
                file_type='directory',
                is_directory=True,
                owner_id=user_id,
                parent_id=parent.id if parent else None
            )
            
            session.add(dir_obj)
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                file_id=dir_obj.id,
                action='create_directory',
                details={'path': virtual_path}
            )
            session.add(log)
            
            session.commit()
            return dir_obj
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def read_file(self, virtual_path: str, user_id: int) -> str:
        """
        Read file content.
        
        Args:
            virtual_path: Virtual path to the file
            user_id: User ID requesting access
            
        Returns:
            File content as string
        """
        session = self.db.get_session()
        
        try:
            # Get file record
            file_obj = session.query(File).filter_by(path=virtual_path).first()
            if not file_obj:
                raise FileNotFoundError(f"File not found: {virtual_path}")
            
            if file_obj.is_directory:
                raise IsADirectoryError(f"Path is a directory: {virtual_path}")
            
            # Update access time
            file_obj.accessed_at = datetime.utcnow()
            
            # Get content
            if file_obj.content:
                content = file_obj.content
            else:
                real_path = self._get_real_path(virtual_path)
                with open(real_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            session.commit()
            return content
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def update_file(self, virtual_path: str, content: str, user_id: int) -> File:
        """
        Update file content.
        
        Args:
            virtual_path: Virtual path to the file
            content: New content
            user_id: User ID making the update
            
        Returns:
            Updated File object
        """
        session = self.db.get_session()
        
        try:
            # Get file record
            file_obj = session.query(File).filter_by(path=virtual_path).first()
            if not file_obj:
                raise FileNotFoundError(f"File not found: {virtual_path}")
            
            if file_obj.is_directory:
                raise IsADirectoryError(f"Path is a directory: {virtual_path}")
            
            # Update real file
            real_path = self._get_real_path(virtual_path)
            with open(real_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update file record
            file_obj.content = content if len(content) < 1000000 else None
            file_obj.size = len(content)
            file_obj.modified_at = datetime.utcnow()
            file_obj.update_hash()
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                file_id=file_obj.id,
                action='update_file',
                details={'path': virtual_path, 'size': file_obj.size}
            )
            session.add(log)
            
            session.commit()
            return file_obj
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def delete_file(self, virtual_path: str, user_id: int) -> bool:
        """
        Delete a file or directory.
        
        Args:
            virtual_path: Virtual path to delete
            user_id: User ID performing deletion
            
        Returns:
            True if successful
        """
        session = self.db.get_session()
        
        try:
            # Get file record
            file_obj = session.query(File).filter_by(path=virtual_path).first()
            if not file_obj:
                raise FileNotFoundError(f"File not found: {virtual_path}")
            
            # Delete real file/directory
            real_path = self._get_real_path(virtual_path)
            if real_path.is_dir():
                shutil.rmtree(real_path)
            else:
                real_path.unlink()
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                file_id=file_obj.id,
                action='delete_file',
                details={'path': virtual_path, 'was_directory': file_obj.is_directory}
            )
            session.add(log)
            
            # Delete file record (cascade will handle relationships)
            session.delete(file_obj)
            session.commit()
            
            return True
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def move_file(self, source_path: str, dest_path: str, user_id: int) -> File:
        """
        Move/rename a file or directory.
        
        Args:
            source_path: Source virtual path
            dest_path: Destination virtual path
            user_id: User ID performing move
            
        Returns:
            Updated File object
        """
        session = self.db.get_session()
        
        try:
            # Get source file record
            file_obj = session.query(File).filter_by(path=source_path).first()
            if not file_obj:
                raise FileNotFoundError(f"File not found: {source_path}")
            
            # Check if destination exists
            existing = session.query(File).filter_by(path=dest_path).first()
            if existing:
                raise FileExistsError(f"Destination already exists: {dest_path}")
            
            # Move real file/directory
            source_real = self._get_real_path(source_path)
            dest_real = self._get_real_path(dest_path)
            dest_real.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(source_real), str(dest_real))
            
            # Update file record
            file_obj.path = dest_path
            file_obj.name = Path(dest_path).name
            file_obj.modified_at = datetime.utcnow()
            
            # Update parent
            parent_path = str(Path(dest_path).parent)
            if parent_path == '.':
                parent_path = '/'
            parent = session.query(File).filter_by(path=parent_path, is_directory=True).first()
            file_obj.parent_id = parent.id if parent else None
            
            # Log activity
            log = ActivityLog(
                user_id=user_id,
                file_id=file_obj.id,
                action='move_file',
                details={'source': source_path, 'destination': dest_path}
            )
            session.add(log)
            
            session.commit()
            return file_obj
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def list_directory(self, virtual_path: str, user_id: int,
                      show_hidden: bool = False) -> List[File]:
        """
        List contents of a directory.
        
        Args:
            virtual_path: Virtual path to directory
            user_id: User ID requesting listing
            show_hidden: Whether to show hidden files
            
        Returns:
            List of File objects
        """
        session = self.db.get_session()
        
        try:
            # Get directory record
            dir_obj = session.query(File).filter_by(path=virtual_path, is_directory=True).first()
            if not dir_obj:
                raise NotADirectoryError(f"Not a directory: {virtual_path}")
            
            # Query children
            query = session.query(File).filter_by(parent_id=dir_obj.id)
            
            if not show_hidden:
                query = query.filter_by(is_hidden=False)
            
            files = query.all()
            
            # Update access time
            dir_obj.accessed_at = datetime.utcnow()
            session.commit()
            
            return files
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def search_files(self, query: str, user_id: int, file_type: str = None,
                    tags: List[str] = None, path_prefix: str = None) -> List[File]:
        """
        Search for files.
        
        Args:
            query: Search query (searches name and content)
            user_id: User ID performing search
            file_type: Filter by file type
            tags: Filter by tags
            path_prefix: Filter by path prefix
            
        Returns:
            List of matching File objects
        """
        session = self.db.get_session()
        
        try:
            # Build query
            db_query = session.query(File).filter_by(owner_id=user_id)
            
            # Search in name and content
            if query:
                db_query = db_query.filter(
                    (File.name.contains(query)) | (File.content.contains(query))
                )
            
            # Filter by file type
            if file_type:
                db_query = db_query.filter_by(file_type=file_type)
            
            # Filter by path prefix
            if path_prefix:
                db_query = db_query.filter(File.path.startswith(path_prefix))
            
            # Filter by tags
            if tags:
                for tag_name in tags:
                    tag = session.query(Tag).filter_by(name=tag_name).first()
                    if tag:
                        db_query = db_query.filter(File.tags.contains(tag))
            
            files = db_query.all()
            return files
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_file_info(self, virtual_path: str) -> Optional[File]:
        """
        Get file information.
        
        Args:
            virtual_path: Virtual path to file
            
        Returns:
            File object or None
        """
        session = self.db.get_session()
        
        try:
            file_obj = session.query(File).filter_by(path=virtual_path).first()
            return file_obj
        finally:
            session.close()


class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass


if __name__ == '__main__':
    # Test filesystem manager
    db = Database()
    db.create_all()
    db.init_default_data()
    
    fsm = FileSystemManager(db=db)
    
    # Test operations
    print("Testing FileSystemManager...")
    
    # Create a test file
    session = db.get_session()
    user = session.query(User).first()
    session.close()
    
    if user:
        try:
            file = fsm.create_file(
                '/Documents/test.txt',
                'This is a test file.',
                user.id,
                tags=['Test']
            )
            print(f"Created file: {file.path}")
            
            # Read file
            content = fsm.read_file('/Documents/test.txt', user.id)
            print(f"Read content: {content}")
            
            # List directory
            files = fsm.list_directory('/Documents', user.id)
            print(f"Files in /Documents: {[f.name for f in files]}")
            
            print("FileSystemManager tests passed!")
        except Exception as e:
            print(f"Test failed: {e}")
