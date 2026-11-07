"""Claim management service for scientific claims and evidence traceability."""

from pathlib import Path
from typing import Any

from researchos.core.enums import (
    ClaimStatus,
    IdPrefix,
)
from researchos.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
)
from researchos.core.ids import IdGenerator
from researchos.core.models import (
    Claim,
    Project,
    utc_now,
)
from researchos.storage.markdown_store import MarkdownStore


class ClaimService:
    """Manages paper-ready scientific claims with rigorous evidence and contradiction tracking."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)
        self.id_gen = IdGenerator(self.vault_root)

    def create_claim(
        self,
        project_id: str,
        text: str,
        status: ClaimStatus = ClaimStatus.UNVERIFIED,
        supporting_experiments: list[str] | None = None,
        supporting_runs: list[str] | None = None,
        contradicting_experiments: list[str] | None = None,
        literature: list[str] | None = None,
        artifacts: list[str] | None = None,
        limitations: list[str] | None = None,
        scope: str | None = None,
        manuscript_section: str | None = None,
    ) -> Claim:
        if not text or not text.strip():
            raise ValidationError("Claim text cannot be empty.")

        proj_path = self.store.resolve_entity_path(project_id)
        if not proj_path.exists():
            raise EntityNotFoundError(f"Project {project_id} not found.")

        proj, proj_body = self.store.load_entity(proj_path, Project)

        claim_id = self.id_gen.generate_id(IdPrefix.CLAIM)
        claim = Claim(
            id=claim_id,
            project_id=project_id,
            text=text.strip(),
            status=status,
            supporting_experiments=supporting_experiments or [],
            supporting_runs=supporting_runs or [],
            contradicting_experiments=contradicting_experiments or [],
            literature=literature or [],
            artifacts=artifacts or [],
            limitations=limitations or [],
            scope=scope,
            manuscript_section=manuscript_section,
        )

        tpl_path = self.vault_root / "90-Templates" / "claim.md"
        body = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else "# {id} {text}\n\n## Formulation & Scope\n"
        body = body.replace("{id}", claim.id).replace("{text}", claim.text)

        claim_path = self.store.resolve_entity_path(claim.id, project_id=project_id)
        self.store.save_entity(claim, body, path=claim_path)

        # Update project's claims
        if claim.id not in proj.claims:
            proj.claims.append(claim.id)
            self.store.save_entity(proj, proj_body, path=proj_path)

        return claim

    def get_claim(self, claim_id: str) -> tuple[Claim, str]:
        path = self.store.resolve_entity_path(claim_id)
        if not path.exists():
            raise EntityNotFoundError(f"Claim {claim_id} not found.")
        return self.store.load_entity(path, Claim)
