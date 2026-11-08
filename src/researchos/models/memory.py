"""Universal Research Memory models and schemas."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from researchos.utils.sanitizer import sanitize_sensitive_data


def utc_now() -> datetime:
    """Returns the current UTC datetime."""
    return datetime.now(UTC)


class MemoryType(str, Enum):
    """The 7 universal memory types of ResearchOS."""

    KNOWLEDGE = "knowledge"          # Facts, concepts, distilled understanding
    DECISION = "decision"            # Architectural / scientific choices and rationales
    HYPOTHESIS = "hypothesis"        # Working hypotheses, assumptions, validation criteria
    OBSERVATION = "observation"      # Empirical observations, findings, metric summaries
    NEGATIVE = "negative"            # Validated negative outcomes, failed paths, pitfalls
    REFERENCE = "reference"          # External pointers (papers, datasets, repos, artifacts)
    HANDOFF = "handoff"              # Inter-agent state handoff notes


class MemoryStatus(str, Enum):
    """Status lifecycle for a memory record."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    PENDING = "pending"
    HYPOTHESIS = "hypothesis"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class SourceType(str, Enum):
    """Source classification for provenance and credibility."""

    AGENT = "agent"
    HUMAN = "human"
    EXPERIMENT = "experiment"
    IMPORTED = "imported"
    SYSTEM = "system"


class MemoryFrontmatter(BaseModel):
    """Standard YAML frontmatter for any universal memory markdown file."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    id: str = Field(description="Unique Memory Identifier, e.g. DEC-001 or MEM-2026-0001")
    project_id: str = Field(description="Parent Project Identifier")
    type: MemoryType = Field(description="Memory type classification")
    title: str = Field(description="Concise descriptive title of the memory")
    created_at: datetime = Field(default_factory=utc_now, description="ISO-8601 creation timestamp")
    updated_at: datetime = Field(default_factory=utc_now, description="ISO-8601 update timestamp")
    status: MemoryStatus | str = Field(default=MemoryStatus.ACTIVE, description="Lifecycle status")
    source_type: SourceType | str | None = Field(
        default=None,
        description="Origin classification: agent, human, experiment, imported, system",
    )
    source_agent: str | None = Field(default=None, description="Creating agent ID or name")
    source_skill: str | None = Field(default=None, description="Calling skill name")
    source_ref: list[str] | str | None = Field(
        default=None,
        description="Source provenance (run, commit, DOI, link, or list of experiment refs)",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0 (None if unrated)",
    )
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    related: list[str] = Field(default_factory=list, description="Related Memory IDs")
    supersedes: str | None = Field(
        default=None,
        description="ID of older memory that this record supersedes/replaces",
    )
    superseded_by: str | None = Field(
        default=None,
        description="ID of newer memory that superseded this record",
    )
    experiment_id: str | None = Field(
        default=None,
        description="Optional experiment run or trial identifier",
    )
    paper_section: str | None = Field(
        default=None,
        description="Target section in paper outline, e.g. '4.1 Main Results'",
    )
    metrics_summary: str | None = Field(
        default=None,
        description="Concise summary of quantitative metrics",
    )
    parent_experiment: str | None = Field(
        default=None,
        description="Memory ID or experiment ID of baseline/parent run",
    )
    artifact_paths: list[str] = Field(
        default_factory=list,
        description="Relative paths to raw artifacts or logs",
    )

    @field_validator("*", mode="before")
    @classmethod
    def sanitize_field(cls, v: Any) -> Any:
        return sanitize_sensitive_data(v)


class Memory(BaseModel):
    """Complete in-memory representation of a memory record (frontmatter + body)."""

    frontmatter: MemoryFrontmatter
    content: str = Field(default="", description="Markdown body content")
    file_path: str | None = Field(default=None, description="Relative or absolute path to markdown file")

    @property
    def id(self) -> str:
        return self.frontmatter.id

    @property
    def project_id(self) -> str:
        return self.frontmatter.project_id

    @property
    def type(self) -> MemoryType:
        return self.frontmatter.type

    @property
    def title(self) -> str:
        return self.frontmatter.title

    @property
    def status(self) -> MemoryStatus:
        return self.frontmatter.status

    @property
    def created_at(self) -> datetime:
        return self.frontmatter.created_at

    @property
    def updated_at(self) -> datetime:
        return self.frontmatter.updated_at

    @property
    def tags(self) -> list[str]:
        return self.frontmatter.tags

    @property
    def related(self) -> list[str]:
        return self.frontmatter.related

    @property
    def supersedes(self) -> str | None:
        return self.frontmatter.supersedes

    @property
    def superseded_by(self) -> str | None:
        return self.frontmatter.superseded_by

    @property
    def source_type(self) -> str | None:
        st = self.frontmatter.source_type
        return st.value if isinstance(st, SourceType) else st

    @property
    def experiment_id(self) -> str | None:
        return self.frontmatter.experiment_id

    @property
    def paper_section(self) -> str | None:
        return self.frontmatter.paper_section

    @property
    def metrics_summary(self) -> str | None:
        return self.frontmatter.metrics_summary

    @property
    def parent_experiment(self) -> str | None:
        return self.frontmatter.parent_experiment

    @property
    def artifact_paths(self) -> list[str]:
        return self.frontmatter.artifact_paths


class ProjectFrontmatter(BaseModel):
    """YAML Frontmatter for PROJECT.md."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    project_id: str = Field(description="Unique project directory identifier")
    project_name: str = Field(description="Human readable project name")
    description: str | None = Field(default=None, description="Short project summary")
    research_goal: str | None = Field(default=None, description="Primary research objective")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    status: str = Field(default="active", description="Project status: active, completed, archived")
    tags: list[str] = Field(default_factory=list)

    @field_validator("*", mode="before")
    @classmethod
    def sanitize_field(cls, v: Any) -> Any:
        return sanitize_sensitive_data(v)


class Project(BaseModel):
    """Complete representation of a research project."""

    frontmatter: ProjectFrontmatter
    body: str = Field(default="")
    project_dir: str = Field(description="Absolute path to the project folder")

    @property
    def project_id(self) -> str:
        return self.frontmatter.project_id

    @property
    def project_name(self) -> str:
        return self.frontmatter.project_name

    @property
    def status(self) -> str:
        return self.frontmatter.status

    @property
    def updated_at(self) -> datetime:
        return self.frontmatter.updated_at


class PaperExperimentItem(BaseModel):
    """Metadata item representing an experiment for Paper Writing Mode."""

    memory_id: str
    experiment_id: str | None = None
    title: str
    status: str
    paper_section: str | None = None
    metrics_summary: str | None = None
    related_literature: list[str] = Field(default_factory=list)
    parent_experiment: str | None = None
    artifact_paths: list[str] = Field(default_factory=list)
    created_at: str


class EvidenceCoverage(BaseModel):
    """Tracks evidence coverage progress for a specific paper section."""

    project_id: str
    paper_section: str
    target_memory_ids: list[str] = Field(default_factory=list)
    loaded_memory_ids: list[str] = Field(default_factory=list)
    pending_memory_ids: list[str] = Field(default_factory=list)
    excluded_memory_ids: dict[str, str] = Field(default_factory=dict)
    is_fully_covered: bool = False
    missing_evidence: list[str] = Field(default_factory=list)
    missing_artifacts: list[str] = Field(default_factory=list)


class ProjectMemoryFrontmatter(BaseModel):
    """Standard YAML frontmatter for Always-on Project Memory (MEMORY.md)."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    schema_version: int = Field(default=1, description="Schema version of MEMORY.md snapshot")
    project_id: str = Field(description="Parent Project Identifier")
    generated_at: datetime = Field(default_factory=utc_now, description="ISO-8601 generation timestamp")
    memory_version: int = Field(default=1, description="Monotonically increasing memory snapshot version")


