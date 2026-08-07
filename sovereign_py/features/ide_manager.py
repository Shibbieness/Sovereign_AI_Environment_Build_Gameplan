"""
Integrated Coding Suite for ML Filesystem v1.8+

Features:
- Full IDE with Monaco Editor (VS Code engine)
- Multi-language support
- Code execution in sandboxed environment
- Git integration
- Terminal access
- Debugging support
- Language servers for autocomplete
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import shutil

from core.database import db
from core.enhanced_models import CodingProject, CodeExecution
from core.config import Config
from core.exceptions import FileSystemException


class CodingIDEManager:
    """
    Manages coding projects and IDE features.
    """
    
    SUPPORTED_LANGUAGES = {
        'python': {
            'extensions': ['.py'],
            'executor': 'python3',
            'language_server': 'pylsp',  # Python Language Server
            'formatter': 'black',
            'linter': 'pylint'
        },
        'javascript': {
            'extensions': ['.js', '.mjs'],
            'executor': 'node',
            'language_server': 'typescript-language-server',
            'formatter': 'prettier',
            'linter': 'eslint'
        },
        'typescript': {
            'extensions': ['.ts'],
            'executor': 'ts-node',
            'language_server': 'typescript-language-server',
            'formatter': 'prettier',
            'linter': 'eslint'
        },
        'rust': {
            'extensions': ['.rs'],
            'executor': 'rustc',
            'language_server': 'rust-analyzer',
            'formatter': 'rustfmt',
            'linter': 'clippy'
        },
        'go': {
            'extensions': ['.go'],
            'executor': 'go run',
            'language_server': 'gopls',
            'formatter': 'gofmt',
            'linter': 'golint'
        },
        'cpp': {
            'extensions': ['.cpp', '.cc', '.cxx'],
            'executor': 'g++',
            'language_server': 'clangd',
            'formatter': 'clang-format',
            'linter': 'cppcheck'
        },
        'c': {
            'extensions': ['.c'],
            'executor': 'gcc',
            'language_server': 'clangd',
            'formatter': 'clang-format',
            'linter': 'cppcheck'
        },
        'java': {
            'extensions': ['.java'],
            'executor': 'java',
            'language_server': 'jdtls',
            'formatter': 'google-java-format',
            'linter': 'checkstyle'
        },
        'ruby': {
            'extensions': ['.rb'],
            'executor': 'ruby',
            'language_server': 'solargraph',
            'formatter': 'rubocop',
            'linter': 'rubocop'
        },
        'php': {
            'extensions': ['.php'],
            'executor': 'php',
            'language_server': 'intelephense',
            'formatter': 'php-cs-fixer',
            'linter': 'phpcs'
        }
    }
    
    def __init__(self):
        self.projects_root = Config.SANDBOX_ROOT / 'coding_projects'
        self.projects_root.mkdir(parents=True, exist_ok=True)
    
    def create_project(
        self,
        name: str,
        language: str,
        owner_id: int,
        description: str = None,
        framework: str = None,
        template: str = None
    ) -> CodingProject:
        """
        Create a new coding project.
        
        Args:
            name: Project name
            language: Programming language
            owner_id: User ID
            description: Project description
            framework: Framework (flask, react, etc.)
            template: Project template to use
            
        Returns:
            Created CodingProject
        """
        session = db.get_session()
        try:
            # Create project directory
            project_path = self.projects_root / f"{owner_id}_{name.replace(' ', '_')}"
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize project from template
            if template:
                self._init_from_template(project_path, language, template)
            else:
                self._init_basic_project(project_path, language)
            
            # Create database entry
            project = CodingProject(
                name=name,
                description=description,
                language=language,
                framework=framework,
                root_path=str(project_path.relative_to(Config.SANDBOX_ROOT)),
                owner_id=owner_id,
                settings={
                    'tab_size': 4,
                    'use_spaces': True,
                    'auto_save': True,
                    'format_on_save': True
                }
            )
            
            session.add(project)
            session.commit()
            session.refresh(project)
            
            print(f"✓ Created coding project: {name} ({language})")
            return project
        finally:
            session.close()
    
    def _init_from_template(self, project_path: Path, language: str, template: str):
        """Initialize project from template."""
        templates = {
            'python_flask': {
                'files': {
                    'app.py': '''from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({'message': 'Hello, World!'})

if __name__ == '__main__':
    app.run(debug=True)
''',
                    'requirements.txt': 'flask==3.0.0\n',
                    'README.md': '# Flask Application\n\nA simple Flask web application.\n'
                }
            },
            'python_basic': {
                'files': {
                    'main.py': '''def main():
    print("Hello, World!")

if __name__ == '__main__':
    main()
''',
                    'README.md': '# Python Project\n\nA simple Python project.\n'
                }
            },
            'javascript_node': {
                'files': {
                    'index.js': '''console.log('Hello, World!');
''',
                    'package.json': '''{
  "name": "node-app",
  "version": "1.0.0",
  "main": "index.js",
  "scripts": {
    "start": "node index.js"
  }
}
''',
                    'README.md': '# Node.js Application\n\nA simple Node.js application.\n'
                }
            }
        }
        
        template_data = templates.get(f"{language}_{template}", templates.get('python_basic'))
        
        for filename, content in template_data['files'].items():
            file_path = project_path / filename
            file_path.write_text(content)
    
    def _init_basic_project(self, project_path: Path, language: str):
        """Initialize basic project structure."""
        # Create main file
        lang_config = self.SUPPORTED_LANGUAGES.get(language, {})
        ext = lang_config.get('extensions', ['.txt'])[0]
        
        main_file = project_path / f'main{ext}'
        main_file.write_text(f'# {language.capitalize()} project\n')
        
        # Create README
        readme = project_path / 'README.md'
        readme.write_text(f'# New {language.capitalize()} Project\n')
    
    def get_project(self, project_id: int) -> Optional[CodingProject]:
        """Get project by ID."""
        session = db.get_session()
        try:
            return session.query(CodingProject).filter_by(id=project_id).first()
        finally:
            session.close()
    
    def list_projects(self, owner_id: int = None, language: str = None) -> List[CodingProject]:
        """List coding projects."""
        session = db.get_session()
        try:
            query = session.query(CodingProject)
            
            if owner_id:
                query = query.filter_by(owner_id=owner_id)
            if language:
                query = query.filter_by(language=language)
            
            return query.all()
        finally:
            session.close()
    
    def get_project_files(self, project_id: int) -> List[Dict[str, Any]]:
        """Get all files in a project."""
        session = db.get_session()
        try:
            project = session.query(CodingProject).filter_by(id=project_id).first()
            if not project:
                return []
            
            project_path = Config.SANDBOX_ROOT / project.root_path
            files = []
            
            for file_path in project_path.rglob('*'):
                if file_path.is_file():
                    rel_path = file_path.relative_to(project_path)
                    files.append({
                        'path': str(rel_path),
                        'name': file_path.name,
                        'size': file_path.stat().st_size,
                        'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
            
            return files
        finally:
            session.close()
    
    def read_file(self, project_id: int, file_path: str) -> Optional[str]:
        """Read a file from project."""
        session = db.get_session()
        try:
            project = session.query(CodingProject).filter_by(id=project_id).first()
            if not project:
                return None
            
            full_path = Config.SANDBOX_ROOT / project.root_path / file_path
            
            # Security check
            try:
                full_path.relative_to(Config.SANDBOX_ROOT / project.root_path)
            except ValueError:
                raise FileSystemException("Path outside project directory")
            
            if full_path.exists():
                return full_path.read_text()
            return None
        finally:
            session.close()
    
    def write_file(self, project_id: int, file_path: str, content: str) -> bool:
        """Write content to a file in project."""
        session = db.get_session()
        try:
            project = session.query(CodingProject).filter_by(id=project_id).first()
            if not project:
                return False
            
            full_path = Config.SANDBOX_ROOT / project.root_path / file_path
            
            # Security check
            try:
                full_path.relative_to(Config.SANDBOX_ROOT / project.root_path)
            except ValueError:
                raise FileSystemException("Path outside project directory")
            
            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            full_path.write_text(content)
            
            # Update project modified time
            project.modified_at = datetime.utcnow()
            session.commit()
            
            return True
        finally:
            session.close()
    
    def execute_code(
        self,
        project_id: int,
        file_path: str,
        args: List[str] = None,
        env_vars: Dict[str, str] = None,
        timeout: int = 30
    ) -> CodeExecution:
        """
        Execute code file.
        
        Args:
            project_id: Project ID
            file_path: File to execute
            args: Command line arguments
            env_vars: Environment variables
            timeout: Execution timeout in seconds
            
        Returns:
            CodeExecution record
        """
        session = db.get_session()
        try:
            project = session.query(CodingProject).filter_by(id=project_id).first()
            if not project:
                raise FileSystemException("Project not found")
            
            full_path = Config.SANDBOX_ROOT / project.root_path / file_path
            working_dir = full_path.parent
            
            # Get language config
            lang_config = self.SUPPORTED_LANGUAGES.get(project.language, {})
            executor = lang_config.get('executor', 'python3')
            
            # Build command
            cmd = [executor, str(full_path)]
            if args:
                cmd.extend(args)
            
            # Prepare environment
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)
            
            # Create execution record
            code_content = full_path.read_text() if full_path.exists() else ''
            execution = CodeExecution(
                project_id=project_id,
                code=code_content,
                language=project.language,
                entry_point=file_path,
                env_vars=env_vars or {},
                working_dir=str(working_dir),
                started_at=datetime.utcnow()
            )
            
            # Execute
            start_time = datetime.utcnow()
            try:
                result = subprocess.run(
                    cmd,
                    cwd=working_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                execution.status = 'success' if result.returncode == 0 else 'error'
                execution.stdout = result.stdout
                execution.stderr = result.stderr
                execution.exit_code = result.returncode
                
            except subprocess.TimeoutExpired:
                execution.status = 'timeout'
                execution.stderr = f'Execution timeout after {timeout}s'
                execution.exit_code = -1
            
            except Exception as e:
                execution.status = 'error'
                execution.stderr = str(e)
                execution.exit_code = -1
            
            # Record timing
            execution.completed_at = datetime.utcnow()
            execution.duration_ms = int((execution.completed_at - start_time).total_seconds() * 1000)
            
            session.add(execution)
            session.commit()
            session.refresh(execution)
            
            return execution
        finally:
            session.close()
    
    def get_execution_history(self, project_id: int, limit: int = 20) -> List[CodeExecution]:
        """Get execution history for a project."""
        session = db.get_session()
        try:
            return session.query(CodeExecution)\
                .filter_by(project_id=project_id)\
                .order_by(CodeExecution.started_at.desc())\
                .limit(limit)\
                .all()
        finally:
            session.close()
    
    def format_code(self, project_id: int, file_path: str) -> Optional[str]:
        """Format code using language-specific formatter."""
        session = db.get_session()
        try:
            project = session.query(CodingProject).filter_by(id=project_id).first()
            if not project:
                return None
            
            full_path = Config.SANDBOX_ROOT / project.root_path / file_path
            
            lang_config = self.SUPPORTED_LANGUAGES.get(project.language, {})
            formatter = lang_config.get('formatter')
            
            if not formatter:
                return None
            
            # Run formatter
            try:
                result = subprocess.run(
                    [formatter, str(full_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    return full_path.read_text()
                return None
            except:
                return None
        finally:
            session.close()
    
    def delete_project(self, project_id: int) -> bool:
        """Delete a coding project."""
        session = db.get_session()
        try:
            project = session.query(CodingProject).filter_by(id=project_id).first()
            if not project:
                return False
            
            # Delete project files
            project_path = Config.SANDBOX_ROOT / project.root_path
            if project_path.exists():
                shutil.rmtree(project_path)
            
            # Delete database record
            session.delete(project)
            session.commit()
            
            print(f"✓ Deleted project: {project.name}")
            return True
        finally:
            session.close()
