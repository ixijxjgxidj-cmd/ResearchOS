"""ResearchOS exception hierarchy."""

from typing import Any


class ResearchOSError(Exception):
    """Base exception for all ResearchOS errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(ResearchOSError):
    """Raised when schema validation or input format checking fails."""


class EntityNotFoundError(ResearchOSError):
    """Raised when an entity, memory, or file does not exist."""


class ProjectNotFoundError(EntityNotFoundError):
    """Raised when a specified project directory or project does not exist."""


class MemoryNotFoundError(EntityNotFoundError):
    """Raised when a specified memory record does not exist."""


class EntityAlreadyExistsError(ResearchOSError):
    """Raised when attempting to create an entity that already exists."""


class PathSecurityError(ResearchOSError):
    """Raised when a path escapes the project root or vault root (traversal attempt)."""


class LockAcquisitionError(ResearchOSError):
    """Raised when acquiring an exclusive file lock times out."""


class VersionConflictError(ResearchOSError):
    """Raised when optimistic concurrency check fails."""

    def __init__(
        self,
        message: str,
        file_path: str = "",
        expected_version: str = "",
        actual_version: str = "",
    ) -> None:
        super().__init__(
            message,
            details={
                "file_path": file_path,
                "expected_version": expected_version,
                "actual_version": actual_version,
            },
        )
