"""Domain models and schemas for ResearchOS entities."""

from datetime import datetime, timezone
import re
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from researchos.core.enums import (
    ArtifactRole,
    ClaimStatus,
    ExperimentOutcome,
    ExperimentStatus,
    FindingStatus,
    PaperReadingStatus,
    ProjectStatus,
    RunStatus,
)
from researchos.core.exceptions import ValidationError

# Patterns for sensitive credentials that must never be committed to markdown vaults
SENSITIVE_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.MULTILINE),
    re.compile(r'(?i)("?password"?\s*[:=]\s*")[^"]+(")'),
    re.compile(r'(?i)("?api[_-]?key"?\s*[:=]\s*")[^"]+(")'),
    re.compile(r'(?i)("?secret"?\s*[:=]\s*")[^"]+(")'),
    re.compile(r'(?i)("?token"?\s*[:=]\s*")[^"]+(")'),
]


def is_credential_key(key: str) -> bool:
    k_lower = str(key).lower().strip()
    if any(s in k_lower for s in ("password", "private_key", "secret", "api_key", "api-key")):
        return True
    # For token: only match auth/bearer/access token or exact token; exclude NLP concepts (tokens, num_tokens, max_tokens, etc.)
    if k_lower in ("token", "access_token", "auth_token", "bearer_token", "refresh_token", "api_token", "session_token", "oauth_token"):
        return True
    if ("_token" in k_lower or "-token" in k_lower) and not any(nlp in k_lower for nlp in ("max_", "num_", "total_", "target_", "input_", "output_", "pred_")):
        return True
    return False


def sanitize_sensitive_data(val: Any) -> Any:
    """Recursively inspects and redacts credentials from strings, dicts, and lists."""
    if isinstance(val, str):
        sanitized = val
        for pat in SENSITIVE_PATTERNS:
            sanitized = pat.sub("[REDACTED_CREDENTIAL]", sanitized)
        return sanitized
    elif isinstance(val, dict):
        new_dict = {}
        for k, v in val.items():
            if is_credential_key(str(k)):
                new_dict[k] = "[REDACTED_CREDENTIAL]"
            else:
                new_dict[k] = sanitize_sensitive_data(v)
        return new_dict
    elif isinstance(val, list):
        return [sanitize_sensitive_data(x) for x in val]
    return val


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseResearchEntity(BaseModel):
    """Base model for all ResearchOS persistent entities."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    schema_version: int = Field(default=1, description="Schema version")
    id: str = Field(description="Unique entity identifier")
    kind: str = Field(description="Entity kind discriminator")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("*", mode="before")
    @classmethod
    def sanitize_field(cls, v: Any) -> Any:
        return sanitize_sensitive_data(v)


class Project(BaseResearchEntity):
    kind: Literal["project"] = "project"
    name: str = Field(description="Project title")
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    research_question: str | None = None
    objectives: list[str] = Field(default_factory=list)
    scope: str | None = None
    members: list[str] = Field(default_factory=list)
    repositories: list[str] = Field(default_factory=list)
    literature: list[str] = Field(default_factory=list, description="Referenced Paper IDs")
    experiments: list[str] = Field(default_factory=list, description="Child Experiment IDs")
    claims: list[str] = Field(default_factory=list, description="Project Claim IDs")


class Experiment(BaseResearchEntity):
    kind: Literal["experiment"] = "experiment"
    project_id: str = Field(description="Parent Project ID")
    title: str = Field(description="Experiment title")
    status: ExperimentStatus = Field(default=ExperimentStatus.PLANNED)
    outcome: ExperimentOutcome = Field(default=ExperimentOutcome.PENDING)
    is_exploratory: bool = Field(default=False, description="Flag for exploratory experiments with partial specs")
    objective: str | None = None
    research_question: str | None = None
    hypothesis: str | None = None
    rationale: str | None = None
    literature: list[str] = Field(default_factory=list, description="Referenced Paper IDs")
    execution: dict[str, Any] = Field(default_factory=dict, description="Execution environment/scripts")
    method: str | None = None
    planned_parameters: dict[str, Any] = Field(default_factory=dict)
    expected_result: str | None = None
    success_criteria: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    planned_outputs: list[str] = Field(default_factory=list)
    runs: list[str] = Field(default_factory=list, description="Run IDs")
    findings: list[str] = Field(default_factory=list, description="Finding IDs")


class Run(BaseResearchEntity):
    kind: Literal["run"] = "run"
    project_id: str = Field(description="Parent Project ID")
    experiment_id: str = Field(description="Parent Experiment ID")
    status: RunStatus = Field(default=RunStatus.CREATED)
    agent_name: str = Field(description="Identifier of executing agent")
    session_id: str | None = None
    executor_type: str = Field(default="local", description="'local' or 'dsh'")
    server_id: str | None = None
    server_task_id: str | None = None
    infrastructure_provider: str | None = None
    working_directory: str | None = None
    dataset_locations: list[str] = Field(default_factory=list)
    environment_fingerprint: dict[str, Any] = Field(default_factory=dict)
    backup_reference: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    actual_parameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None
    code_repository: str | None = None
    code_commit: str | None = None
    environment: dict[str, Any] = Field(default_factory=dict)
    inputs: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list, description="Artifact IDs")
    metrics: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    deviations: list[str] = Field(default_factory=list)
    result_summary: str | None = None


class Paper(BaseResearchEntity):
    kind: Literal["paper"] = "paper"
    citekey: str = Field(description="BibTeX style unique citekey")
    title: str = Field(description="Paper title")
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    journal: str | None = None
    doi: str | None = None
    url: str | None = None
    pdf_path: str | None = None
    abstract: str | None = None
    reading_status: PaperReadingStatus = Field(default=PaperReadingStatus.TO_READ)
    projects: list[str] = Field(default_factory=list, description="Project IDs")
    related_experiments: list[str] = Field(default_factory=list, description="Experiment IDs")
    tags: list[str] = Field(default_factory=list)


class Finding(BaseResearchEntity):
    kind: Literal["finding"] = "finding"
    project_id: str = Field(description="Parent Project ID")
    experiment_id: str = Field(description="Originating Experiment ID")
    run_id: str | None = None
    title: str = Field(description="Finding concise statement")
    status: FindingStatus = Field(default=FindingStatus.CANDIDATE)
    evidence_artifacts: list[str] = Field(default_factory=list, description="Artifact IDs")
    literature: list[str] = Field(default_factory=list, description="Paper IDs")
    research_question: str | None = None


class Claim(BaseResearchEntity):
    kind: Literal["claim"] = "claim"
    project_id: str = Field(description="Parent Project ID")
    text: str = Field(description="Scientific claim statement")
    status: ClaimStatus = Field(default=ClaimStatus.UNVERIFIED)
    supporting_experiments: list[str] = Field(default_factory=list)
    supporting_runs: list[str] = Field(default_factory=list)
    contradicting_experiments: list[str] = Field(default_factory=list)
    literature: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    scope: str | None = None
    manuscript_section: str | None = None


class Artifact(BaseResearchEntity):
    kind: Literal["artifact"] = "artifact"
    run_id: str = Field(description="Originating Run ID")
    name: str = Field(description="Artifact name or filename")
    role: ArtifactRole = Field(description="Role classification")
    storage_backend: str = Field(default="local", description="Storage backend: local, dsh, gdrive, etc.")
    path: str = Field(description="Relative or external path")
    server_id: str | None = None
    media_type: str | None = None
    size_bytes: int = Field(default=0)
    sha256: str = Field(description="SHA-256 cryptographic hash")
    immutable: bool = Field(default=True)


class Decision(BaseResearchEntity):
    kind: Literal["decision"] = "decision"
    project_id: str = Field(description="Parent Project ID")
    title: str = Field(description="Decision title")
    date: datetime = Field(default_factory=utc_now)
    author: str = Field(default="agent")
