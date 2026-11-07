"""Enumerations for ResearchOS entities and lifecycle states."""

from enum import Enum


class StrEnum(str, Enum):
    """String enum for serialization compatibility."""

    def __str__(self) -> str:
        return self.value


class IdPrefix(StrEnum):
    PROJECT = "PRJ"
    EXPERIMENT = "EXP"
    RUN = "RUN"
    PAPER = "PAPER"
    FINDING = "FIND"
    CLAIM = "CLAIM"
    ARTIFACT = "ART"
    DECISION = "DEC"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ExperimentStatus(StrEnum):
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ExperimentOutcome(StrEnum):
    PENDING = "pending"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"
    INVALID = "invalid"


class RunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    NEEDS_REVIEW = "needs_review"
    REVIEWED = "reviewed"


class PaperReadingStatus(StrEnum):
    TO_READ = "to_read"
    READING = "reading"
    READ = "read"
    SYNTHESIZED = "synthesized"
    PARTIAL = "partial"


class FindingStatus(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ClaimStatus(StrEnum):
    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    PARTIALLY_SUPPORTED = "partially_supported"
    ABANDONED = "abandoned"


class ArtifactRole(StrEnum):
    RAW_DATA = "raw_data"
    DATASET = "dataset"
    CONFIG = "config"
    SOURCE_CODE = "source_code"
    LOG = "log"
    METRICS = "metrics"
    FIGURE = "figure"
    CHECKPOINT = "checkpoint"
    REPORT = "report"
