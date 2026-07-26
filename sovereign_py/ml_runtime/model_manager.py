"""
ML Model Manager for ML Filesystem v1.8
Handles downloading, caching, and loading ML models.
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

from core.config import Config
from core.exceptions import ModelDownloadError, ModelNotLoadedError
from ml_runtime.graceful import (
    SENTENCE_TRANSFORMERS_AVAILABLE, TRANSFORMERS_AVAILABLE, TORCH_AVAILABLE,
    MLBackendUnavailable
)

if SENTENCE_TRANSFORMERS_AVAILABLE:
    from sentence_transformers import SentenceTransformer
if TRANSFORMERS_AVAILABLE:
    from transformers import pipeline
if TORCH_AVAILABLE:
    import torch


class MLModelManager:
    """
    Manages ML model lifecycle:
    - Downloading models
    - Caching models
    - Loading models into memory
    - Model version tracking
    """
    
    # Model configurations
    MODEL_CONFIGS = {
        'minimal': {
            'embedder': {
                'name': 'all-MiniLM-L6-v2',
                'size_mb': 80,
                'task': 'sentence-transformers'
            }
        },
        'standard': {
            'embedder': {
                'name': 'all-MiniLM-L6-v2',
                'size_mb': 80,
                'task': 'sentence-transformers'
            },
            'qa': {
                'name': 'distilbert-base-uncased-distilled-squad',
                'size_mb': 250,
                'task': 'question-answering'
            }
        },
        'full': {
            'embedder': {
                'name': 'all-MiniLM-L6-v2',
                'size_mb': 80,
                'task': 'sentence-transformers'
            },
            'qa': {
                'name': 'distilbert-base-uncased-distilled-squad',
                'size_mb': 250,
                'task': 'question-answering'
            },
            'summarizer': {
                'name': 'facebook/bart-large-cnn',
                'size_mb': 1600,
                'task': 'summarization'
            }
        }
    }
    
    def __init__(self, profile: str = None):
        self.profile = profile or Config.ML_MODEL_PROFILE
        self.models_dir = Config.MODELS_DIR
        self.profile_dir = self.models_dir / self.profile
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Loaded models cache
        self._loaded_models = {}
        
        # Model metadata
        self.metadata_file = self.profile_dir / 'metadata.json'
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load model metadata."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_metadata(self):
        """Save model metadata."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def get_profile_config(self) -> Dict:
        """Get configuration for current profile."""
        return self.MODEL_CONFIGS.get(self.profile, self.MODEL_CONFIGS['standard'])
    
    def check_models_available(self) -> Dict[str, bool]:
        """Check which models are downloaded."""
        config = self.get_profile_config()
        available = {}
        
        for model_type, model_config in config.items():
            model_name = model_config['name']
            model_path = self.profile_dir / model_name.replace('/', '_')
            available[model_type] = model_path.exists()
        
        return available
    
    def download_models(self, force: bool = False, progress_callback=None):
        """
        Download all models for current profile.
        
        Args:
            force: Re-download even if already exists
            progress_callback: Function to call with progress updates
        """
        config = self.get_profile_config()
        total_models = len(config)
        
        print(f"\n📥 Downloading models for profile: {self.profile}")
        print(f"Total models: {total_models}")
        
        for idx, (model_type, model_config) in enumerate(config.items(), 1):
            model_name = model_config['name']
            task = model_config['task']
            size_mb = model_config['size_mb']
            
            # Progress update
            if progress_callback:
                progress_callback({
                    'current': idx,
                    'total': total_models,
                    'model_type': model_type,
                    'model_name': model_name,
                    'size_mb': size_mb
                })
            
            print(f"\n[{idx}/{total_models}] {model_type.upper()}")
            print(f"  Model: {model_name}")
            print(f"  Size: ~{size_mb}MB")
            
            try:
                if task == 'sentence-transformers':
                    self._download_sentence_transformer(model_name, force)
                else:
                    self._download_hf_model(model_name, task, force)
                
                # Update metadata
                self.metadata[model_type] = {
                    'name': model_name,
                    'task': task,
                    'downloaded_at': datetime.utcnow().isoformat(),
                    'size_mb': size_mb
                }
                self._save_metadata()
                
                print(f"  ✓ Downloaded successfully")
                
            except Exception as e:
                error_msg = f"Failed to download {model_name}: {str(e)}"
                print(f"  ✗ {error_msg}")
                raise ModelDownloadError(error_msg)
        
        print(f"\n✓ All models for '{self.profile}' profile downloaded successfully!")
        return True
    
    def _download_sentence_transformer(self, model_name: str, force: bool = False):
        """Download sentence transformer model."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise MLBackendUnavailable(
                "Downloading embedder models requires sentence-transformers to be installed."
            )

        model_path = self.profile_dir / model_name.replace('/', '_')

        if model_path.exists() and not force:
            print(f"  → Already exists, skipping")
            return

        print(f"  → Downloading...")
        model = SentenceTransformer(model_name, cache_folder=str(self.profile_dir))
        
        # Save to specific location
        model.save(str(model_path))
    
    def _download_hf_model(self, model_name: str, task: str, force: bool = False):
        """Download Hugging Face model."""
        if not TRANSFORMERS_AVAILABLE:
            raise MLBackendUnavailable(
                "Downloading Hugging Face models requires transformers to be installed."
            )

        model_path = self.profile_dir / model_name.replace('/', '_')

        if model_path.exists() and not force:
            print(f"  → Already exists, skipping")
            return
        
        print(f"  → Downloading...")
        
        # Download via pipeline (handles model + tokenizer)
        pipe = pipeline(task, model=model_name, model_kwargs={'cache_dir': str(self.profile_dir)})
        
        # Save
        model_path.mkdir(parents=True, exist_ok=True)
        pipe.save_pretrained(str(model_path))
    
    def load_model(self, model_type: str):
        """
        Load a model into memory.
        
        Args:
            model_type: Type of model ('embedder', 'qa', 'summarizer')
            
        Returns:
            Loaded model object
        """
        # Check if already loaded
        if model_type in self._loaded_models:
            return self._loaded_models[model_type]
        
        # Get model config
        config = self.get_profile_config()
        if model_type not in config:
            raise ModelNotLoadedError(f"Model type '{model_type}' not available in profile '{self.profile}'")
        
        model_config = config[model_type]
        model_name = model_config['name']
        task = model_config['task']

        if task == 'sentence-transformers' and not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise MLBackendUnavailable(
                f"Cannot load '{model_type}': sentence-transformers is not installed."
            )
        if task != 'sentence-transformers' and not TRANSFORMERS_AVAILABLE:
            raise MLBackendUnavailable(
                f"Cannot load '{model_type}': transformers is not installed."
            )

        model_path = self.profile_dir / model_name.replace('/', '_')

        if not model_path.exists():
            raise ModelNotLoadedError(f"Model '{model_name}' not downloaded. Run download_models() first.")

        print(f"Loading {model_type} model...")

        try:
            if task == 'sentence-transformers':
                model = SentenceTransformer(str(model_path))
            else:
                model = pipeline(task, model=str(model_path))
            
            # Cache
            self._loaded_models[model_type] = model
            
            print(f"✓ {model_type} model loaded")
            return model
            
        except Exception as e:
            raise ModelNotLoadedError(f"Failed to load {model_type}: {str(e)}")
    
    def unload_model(self, model_type: str):
        """Unload model from memory."""
        if model_type in self._loaded_models:
            del self._loaded_models[model_type]
            # Force garbage collection
            import gc
            gc.collect()
            if TORCH_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(f"✓ {model_type} model unloaded")
    
    def get_loaded_models(self) -> List[str]:
        """Get list of currently loaded models."""
        return list(self._loaded_models.keys())
    
    def get_model_info(self) -> Dict:
        """Get information about models."""
        config = self.get_profile_config()
        available = self.check_models_available()
        
        info = {
            'profile': self.profile,
            'models': {}
        }
        
        for model_type, model_config in config.items():
            info['models'][model_type] = {
                'name': model_config['name'],
                'task': model_config['task'],
                'size_mb': model_config['size_mb'],
                'downloaded': available.get(model_type, False),
                'loaded': model_type in self._loaded_models
            }
        
        # Calculate total size
        total_size = sum(m['size_mb'] for m in config.values())
        downloaded_size = sum(
            config[mt]['size_mb'] 
            for mt, is_available in available.items() 
            if is_available
        )
        
        info['total_size_mb'] = total_size
        info['downloaded_size_mb'] = downloaded_size
        info['download_complete'] = all(available.values())
        
        return info
    
    def clear_cache(self, model_type: str = None):
        """Clear downloaded models."""
        if model_type:
            # Clear specific model
            config = self.get_profile_config()
            if model_type in config:
                model_name = config[model_type]['name']
                model_path = self.profile_dir / model_name.replace('/', '_')
                if model_path.exists():
                    import shutil
                    shutil.rmtree(model_path)
                    print(f"✓ Cleared {model_type} cache")
        else:
            # Clear entire profile
            import shutil
            if self.profile_dir.exists():
                shutil.rmtree(self.profile_dir)
                self.profile_dir.mkdir(parents=True, exist_ok=True)
                print(f"✓ Cleared all model cache for profile '{self.profile}'")
        
        # Clear metadata
        self.metadata = {}
        self._save_metadata()
