"""
Core configuration management for ML Filesystem v1.8
Handles environment variables, defaults, and validation.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """
    Central configuration class.
    All settings accessible as class attributes.
    """
    
    # Base Paths
    BASE_DIR = Path(__file__).parent.parent
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{BASE_DIR}/data/database.db')
    
    # ML Configuration
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', None)
    ML_MODEL_PROFILE = os.getenv('ML_MODEL_PROFILE', 'standard')  # minimal, standard, full
    MODELS_DIR = Path(os.getenv('MODELS_DIR', BASE_DIR / 'models'))
    
    # Vector Database
    VECTOR_STORE_PATH = Path(os.getenv('VECTOR_STORE_PATH', BASE_DIR / 'data' / 'vector_store'))
    
    # File Storage
    SANDBOX_ROOT = Path(os.getenv('SANDBOX_ROOT', BASE_DIR / 'sandbox'))
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 104857600))  # 100MB
    
    # Server
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # External API
    EXTERNAL_API_ENABLED = os.getenv('EXTERNAL_API_ENABLED', 'True').lower() == 'true'
    EXTERNAL_API_PORT = int(os.getenv('EXTERNAL_API_PORT', 5001))
    EXTERNAL_API_KEY = os.getenv('EXTERNAL_API_KEY', None)
    
    # Plugin System
    PLUGINS_ENABLED = os.getenv('PLUGINS_ENABLED', 'True').lower() == 'true'
    PLUGINS_DIR = Path(os.getenv('PLUGINS_DIR', BASE_DIR / 'plugins'))
    
    # Widgets & Integration
    SYSTEM_TRAY_ENABLED = os.getenv('SYSTEM_TRAY_ENABLED', 'True').lower() == 'true'
    GLOBAL_HOTKEYS_ENABLED = os.getenv('GLOBAL_HOTKEYS_ENABLED', 'True').lower() == 'true'
    
    # Performance
    EMBEDDING_BATCH_SIZE = int(os.getenv('EMBEDDING_BATCH_SIZE', 32))
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', 4))
    
    # Training Blocks
    TRAINING_BLOCKS_DIR = Path(os.getenv('TRAINING_BLOCKS_DIR', BASE_DIR / 'data' / 'training_blocks'))
    AUTO_SAVE_TRAINING_BLOCKS = os.getenv('AUTO_SAVE_TRAINING_BLOCKS', 'True').lower() == 'true'
    
    # Model Profiles
    MODEL_PROFILES = {
        'minimal': {
            'embedder': 'all-MiniLM-L6-v2',
            'size': '80MB',
            'features': ['embeddings', 'search', 'similarity']
        },
        'standard': {
            'embedder': 'all-MiniLM-L6-v2',
            'qa_model': 'distilbert-base-uncased-distilled-squad',
            'size': '330MB',
            'features': ['embeddings', 'search', 'similarity', 'qa']
        },
        'full': {
            'embedder': 'all-MiniLM-L6-v2',
            'qa_model': 'distilbert-base-uncased-distilled-squad',
            'summarizer': 'facebook/bart-large-cnn',
            'size': '2GB',
            'features': ['embeddings', 'search', 'similarity', 'qa', 'summarization']
        }
    }
    
    @classmethod
    def get_model_profile(cls) -> dict:
        """Get current model profile configuration."""
        return cls.MODEL_PROFILES.get(cls.ML_MODEL_PROFILE, cls.MODEL_PROFILES['standard'])
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        directories = [
            cls.MODELS_DIR,
            cls.VECTOR_STORE_PATH,
            cls.SANDBOX_ROOT,
            cls.TRAINING_BLOCKS_DIR,
            cls.PLUGINS_DIR,
            cls.BASE_DIR / 'data'
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration."""
        errors = []
        
        # Check ML model profile
        if cls.ML_MODEL_PROFILE not in cls.MODEL_PROFILES:
            errors.append(f"Invalid ML_MODEL_PROFILE: {cls.ML_MODEL_PROFILE}")
        
        # Check file size limit
        if cls.MAX_FILE_SIZE < 1024:
            errors.append(f"MAX_FILE_SIZE too small: {cls.MAX_FILE_SIZE}")
        
        # Warn if no API key for advanced features
        if not cls.ANTHROPIC_API_KEY:
            print("⚠️  No ANTHROPIC_API_KEY set - advanced features will be limited to local ML")
        
        # Warn if external API enabled but no key
        if cls.EXTERNAL_API_ENABLED and not cls.EXTERNAL_API_KEY:
            print("⚠️  External API enabled but no EXTERNAL_API_KEY set - generating random key")
            import secrets
            cls.EXTERNAL_API_KEY = secrets.token_urlsafe(32)
        
        if errors:
            print("❌ Configuration errors:")
            for error in errors:
                print(f"   - {error}")
            return False
        
        return True
    
    @classmethod
    def print_config(cls):
        """Print current configuration."""
        print("\n" + "="*50)
        print("ML Filesystem v1.8 - Configuration")
        print("="*50)
        print(f"ML Model Profile: {cls.ML_MODEL_PROFILE} ({cls.get_model_profile()['size']})")
        print(f"Features: {', '.join(cls.get_model_profile()['features'])}")
        print(f"Database: {cls.DATABASE_URL}")
        print(f"Sandbox Root: {cls.SANDBOX_ROOT}")
        print(f"API Key Set: {'Yes' if cls.ANTHROPIC_API_KEY else 'No'}")
        print(f"External API: {'Enabled' if cls.EXTERNAL_API_ENABLED else 'Disabled'}")
        print(f"Plugins: {'Enabled' if cls.PLUGINS_ENABLED else 'Disabled'}")
        print(f"System Tray: {'Enabled' if cls.SYSTEM_TRAY_ENABLED else 'Disabled'}")
        print("="*50 + "\n")


# Initialize configuration
Config.ensure_directories()
Config.validate()
