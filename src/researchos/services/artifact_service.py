"""Artifact registration, cryptographic hashing, and integrity verification."""

import hashlib
import mimetypes
from pathlib import Path
from typing import Any

from researchos.core.enums import (
    ArtifactRole,
    IdPrefix,
)
from researchos.core.exceptions import (
    EntityNotFoundError,
    ValidationError,
)
from researchos.core.ids import IdGenerator
from researchos.core.models import (
    Artifact,
    Run,
    utc_now,
)
from researchos.storage.markdown_store import MarkdownStore


def compute_file_sha256(file_path: Path | str) -> tuple[str, int]:
    """Computes the SHA-256 hash and byte size of a local file."""
    p = Path(file_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Artifact file not found: {p}")

    hasher = hashlib.sha256()
    size = 0
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


class ArtifactService:
    """Manages artifact metadata, SHA-256 immutability, and external dataset linkage."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.store = MarkdownStore(self.vault_root)
        self.id_gen = IdGenerator(self.vault_root)

    def register_artifact(
        self,
        run_id: str,
        path: str,
        role: ArtifactRole | str,
        name: str | None = None,
        storage_backend: str = "local",
        server_id: str | None = None,
        media_type: str | None = None,
        sha256: str | None = None,
        size_bytes: int | None = None,
    ) -> Artifact:
        """Registers an artifact produced by or used in a Run."""
        run_path = self.store.resolve_entity_path(run_id)
        if not run_path.exists():
            raise EntityNotFoundError(f"Run {run_id} not found.")

        run, run_body = self.store.load_entity(run_path, Run)

        role_enum = ArtifactRole(role) if isinstance(role, str) else role
        art_name = name or Path(path).name

        computed_sha256 = sha256 or ""
        computed_size = size_bytes or 0

        # If local file, compute sha256 and size directly
        local_candidate = Path(path)
        if storage_backend == "local" or local_candidate.is_file():
            if local_candidate.is_file():
                computed_sha256, computed_size = compute_file_sha256(local_candidate)
                if not media_type:
                    media_type, _ = mimetypes.guess_type(str(local_candidate))

        if not computed_sha256:
            computed_sha256 = "external_remote_unhashed"

        art_id = self.id_gen.generate_id(IdPrefix.ARTIFACT)
        artifact = Artifact(
            id=art_id,
            run_id=run_id,
            name=art_name,
            role=role_enum,
            storage_backend=storage_backend,
            path=path,
            server_id=server_id,
            media_type=media_type,
            size_bytes=computed_size,
            sha256=computed_sha256,
            immutable=True,
        )

        tpl_path = self.vault_root / "90-Templates" / "artifact.md"
        body = tpl_path.read_text(encoding="utf-8") if tpl_path.exists() else "# {id} {name}\n\n## Artifact Overview\n"
        body = body.replace("{id}", artifact.id).replace("{name}", artifact.name)

        art_path = self.store.resolve_entity_path(artifact.id, project_id=run.project_id)
        self.store.save_entity(artifact, body, path=art_path)

        # Attach artifact to Run
        if artifact.id not in run.artifacts:
            run.artifacts.append(artifact.id)
            self.store.save_entity(run, run_body, path=run_path)

        return artifact

    def get_artifact(self, artifact_id: str) -> tuple[Artifact, str]:
        path = self.store.resolve_entity_path(artifact_id)
        if not path.exists():
            raise EntityNotFoundError(f"Artifact {artifact_id} not found.")
        return self.store.load_entity(path, Artifact)

    def verify_artifact(self, artifact_id: str) -> dict[str, Any]:
        """Verifies local artifact file integrity against recorded SHA-256."""
        artifact, _ = self.get_artifact(artifact_id)
        file_path = Path(artifact.path)

        if not file_path.exists():
            return {
                "artifact_id": artifact.id,
                "status": "missing_file",
                "path": str(file_path),
                "recorded_sha256": artifact.sha256,
            }

        curr_hash, curr_size = compute_file_sha256(file_path)
        is_valid = curr_hash == artifact.sha256 and curr_size == artifact.size_bytes
        return {
            "artifact_id": artifact.id,
            "status": "valid" if is_valid else "corrupted",
            "path": str(file_path),
            "match": is_valid,
            "recorded_sha256": artifact.sha256,
            "current_sha256": curr_hash,
            "recorded_size": artifact.size_bytes,
            "current_size": curr_size,
        }
