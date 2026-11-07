"""Custom exceptions for ResearchOS."""


class ResearchOSError(Exception):
    """Base exception for all ResearchOS errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class VaultNotFoundError(ResearchOSError):
    """Raised when the specified vault directory does not exist or is invalid."""


class EntityNotFoundError(ResearchOSError):
    """Raised when an entity with the specified ID or path is not found."""


class EntityAlreadyExistsError(ResearchOSError):
    """Raised when attempting to create an entity that already exists."""


class ValidationError(ResearchOSError):
    """Raised when entity validation or schema validation fails."""


class InvalidStateTransitionError(ResearchOSError):
    """Raised when an invalid state transition is attempted."""


class VersionConflictError(ResearchOSError):
    """Raised when concurrent modification is detected."""

    def __init__(self, message: str, file_path: str, expected_version: str | None = None, actual_version: str | None = None) -> None:
        super().__init__(message, {"file_path": file_path, "expected_version": expected_version, "actual_version": actual_version})
        self.file_path = file_path
        self.expected_version = expected_version
        self.actual_version = actual_version


class PathSecurityError(ResearchOSError):
    """Raised when a path traversal or insecure symlink attempt is detected."""


class LockAcquisitionError(ResearchOSError):
    """Raised when an exclusive file lock cannot be acquired."""


class PreflightCheckError(ResearchOSError):
    """Raised when an experiment preflight check fails."""


class DuplicateIdError(ResearchOSError):
    """Raised when an ID collision is detected."""
