"""
Graceful-degradation layer for ml_runtime.

sentence-transformers, transformers, torch and chromadb are heavy, optional
dependencies. Detect their availability once here so the rest of ml_runtime
can degrade honestly (raise a clear MLBackendUnavailable from the specific
call that needed the missing library) instead of failing to import at all.
"""

try:
    import sentence_transformers  # noqa: F401
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import transformers  # noqa: F401
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import torch  # noqa: F401
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import chromadb  # noqa: F401
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

ML_BACKEND_AVAILABLE = SENTENCE_TRANSFORMERS_AVAILABLE and TRANSFORMERS_AVAILABLE and TORCH_AVAILABLE


class MLBackendUnavailable(Exception):
    """Raised when an operation needs a heavy ML dependency that isn't installed."""


def require(flag: bool, feature: str, package_hint: str):
    if not flag:
        raise MLBackendUnavailable(
            f"{feature} is unavailable: install {package_hint} to enable it."
        )
