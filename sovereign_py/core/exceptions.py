"""
Custom exceptions for ML Filesystem v1.8
Clear, specific exceptions for better error handling.
"""


class MLFilesystemException(Exception):
    """Base exception for all ML Filesystem errors."""
    pass


# File System Exceptions
class FileSystemException(MLFilesystemException):
    """Base exception for filesystem operations."""
    pass


class FileNotFoundError(FileSystemException):
    """File not found in semantic filesystem."""
    pass


class FileAlreadyExistsError(FileSystemException):
    """File already exists at target location."""
    pass


class InvalidPathError(FileSystemException):
    """Invalid or unsafe file path."""
    pass


class FileSizeLimitExceeded(FileSystemException):
    """File exceeds maximum allowed size."""
    pass


class SandboxViolation(FileSystemException):
    """Attempt to access file outside sandbox."""
    pass


# ML Exceptions
class MLException(MLFilesystemException):
    """Base exception for ML operations."""
    pass


class ModelNotLoadedError(MLException):
    """ML model not loaded or not available."""
    pass


class ModelDownloadError(MLException):
    """Error downloading ML model."""
    pass


class EmbeddingError(MLException):
    """Error generating embeddings."""
    pass


class InferenceError(MLException):
    """Error during model inference."""
    pass


class TrainingBlockException(MLException):
    """Base exception for training block operations."""
    pass


class TrainingBlockNotFoundError(TrainingBlockException):
    """Training block not found."""
    pass


class TrainingBlockConflictError(TrainingBlockException):
    """Conflicting training blocks."""
    pass


# Plugin Exceptions
class PluginException(MLFilesystemException):
    """Base exception for plugin system."""
    pass


class PluginLoadError(PluginException):
    """Error loading plugin."""
    pass


class PluginNotFoundError(PluginException):
    """Plugin not found."""
    pass


class PluginDependencyError(PluginException):
    """Plugin dependency not satisfied."""
    pass


# Workflow Exceptions
class WorkflowException(MLFilesystemException):
    """Base exception for workflow system."""
    pass


class WorkflowExecutionError(WorkflowException):
    """Error executing workflow."""
    pass


class TriggerError(WorkflowException):
    """Error in workflow trigger."""
    pass


class ActionError(WorkflowException):
    """Error in workflow action."""
    pass


# API Exceptions
class APIException(MLFilesystemException):
    """Base exception for API operations."""
    pass


class AuthenticationError(APIException):
    """Authentication failed."""
    pass


class AuthorizationError(APIException):
    """Not authorized for this operation."""
    pass


class RateLimitError(APIException):
    """Rate limit exceeded."""
    pass


# Database Exceptions
class DatabaseException(MLFilesystemException):
    """Base exception for database operations."""
    pass


class DatabaseConnectionError(DatabaseException):
    """Cannot connect to database."""
    pass


class IntegrityError(DatabaseException):
    """Database integrity constraint violated."""
    pass
