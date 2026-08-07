"""
ML Module for ML Filesystem v1.8

Provides complete ML capabilities:
- Local model management
- Hybrid local/API inference
- Training blocks system
- Embeddings and vector search

Lazy-loaded (PEP 562 module __getattr__) so importing this package never
eagerly pulls sentence-transformers/transformers/torch. Real loading happens
the first time a name below is actually accessed.
"""

__all__ = [
    'MLModelManager',
    'LocalMLBackend',
    'TrainingBlockManager',
    'HybridMLAgent',
]

_LAZY = {
    'MLModelManager': ('.model_manager', 'MLModelManager'),
    'LocalMLBackend': ('.local_backend', 'LocalMLBackend'),
    'TrainingBlockManager': ('.training_blocks', 'TrainingBlockManager'),
    # Real file is hybrid_agent_GHOST_BONE.py, not hybrid_agent.py.
    'HybridMLAgent': ('.hybrid_agent_GHOST_BONE', 'HybridMLAgent'),
}


def __getattr__(name):
    if name in _LAZY:
        import importlib
        module_name, attr = _LAZY[name]
        module = importlib.import_module(module_name, __name__)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)
