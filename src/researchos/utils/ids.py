"""Identifier generation, validation, and slugification for ResearchOS Universal Memory."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from researchos.utils.exceptions import ValidationError

# Legacy memory pattern: MEM-YYYY-NNNN
LEGACY_MEMORY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^MEM-(?P<year>\d{4})-(?P<seq>\d{3,})$"
)

# Standard prefix memory pattern: DEC-001, OBS-001, etc.
PREFIX_MEMORY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<prefix>DEC|OBS|NEG|HYP|REF|KNO|HAN)-(?P<seq>\d{3,})$"
)

PROJECT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-zA-Z0-9_\-]+$"
)

# Type to standard prefix mapping
TYPE_PREFIX_MAP: Final[dict[str, str]] = {
    "decision": "DEC",
    "observation": "OBS",
    "negative": "NEG",
    "hypothesis": "HYP",
    "reference": "REF",
    "knowledge": "KNO",
    "handoff": "HAN",
}


def sanitize_filename_slug(title: str, max_length: int = 40) -> str:
    """Sanitizes a title into a cross-platform safe filename slug for Windows, Linux, and macOS."""
    if not title:
        return "record"
    # Replace characters forbidden on Windows/Linux/macOS: \ / : * ? " < > |
    s = re.sub(r'[\\/:*?"<>|]+', "_", title.strip())
    # Replace whitespace and repeated punctuation with single underscore
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("._")
    if not s:
        s = "record"
    return s[:max_length].rstrip("._")


def validate_memory_id(id_str: str) -> tuple[int | str, int]:
    """Validates a memory ID string and returns (year_or_prefix, seq).

    Supports:
        - Standard format: DEC-001, OBS-001, NEG-001, HYP-001, REF-001, KNO-001, HAN-001
        - Legacy format: MEM-YYYY-NNNN

    Raises:
        ValidationError: if the string does not match any valid memory ID format.
    """
    if not id_str or not isinstance(id_str, str):
        raise ValidationError(f"Invalid Memory ID: '{id_str}'. Must be a non-empty string.")

    cleaned = id_str.strip()
    legacy_match = LEGACY_MEMORY_ID_PATTERN.match(cleaned)
    if legacy_match:
        return int(legacy_match.group("year")), int(legacy_match.group("seq"))

    prefix_match = PREFIX_MEMORY_ID_PATTERN.match(cleaned)
    if prefix_match:
        return prefix_match.group("prefix"), int(prefix_match.group("seq"))

    raise ValidationError(
        f"Invalid Memory ID format '{id_str}'. Must match standard (DEC-001, OBS-001, ...) or legacy (MEM-YYYY-NNNN)."
    )


def is_valid_memory_id(id_str: str) -> bool:
    """Returns True if the string is a valid standard or legacy memory ID."""
    if not id_str or not isinstance(id_str, str):
        return False
    cleaned = id_str.strip()
    return bool(LEGACY_MEMORY_ID_PATTERN.match(cleaned) or PREFIX_MEMORY_ID_PATTERN.match(cleaned))


def slugify_project_id(name: str) -> str:
    """Converts a human-readable project title to a clean directory slug."""
    s = name.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    if not s:
        s = "research-project"
    return s


class MemoryIdGenerator:
    """Project-isolated, process-safe monotonic ID generator for memories."""

    def __init__(self, project_dir: Path | str) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.meta_dir = self.project_dir / ".researchos"
        self.seq_file = self.meta_dir / "sequences.json"
        self.lock_file = self.meta_dir / "id_sequence.lock"

    def _ensure_meta_dir(self) -> None:
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    def _read_sequences(self) -> dict[str, int]:
        if not self.seq_file.exists():
            return {}
        try:
            with open(self.seq_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {str(k): int(v) for k, v in data.items()}
        except Exception:
            return {}

    def _write_sequences(self, sequences: dict[str, int]) -> None:
        from researchos.core.storage_service import atomic_write_text
        atomic_write_text(self.seq_file, json.dumps(sequences, indent=2))

    def _scan_highest_sequence_on_disk(self, key_prefix: str) -> int:
        """Scans project directory for existing files matching prefix to prevent collisions."""
        highest = 0
        if not self.project_dir.exists():
            return 0

        if key_prefix.startswith("MEM-"):
            # Scanning MEM-YYYY-(\d+)
            target_pattern = re.compile(rf"{re.escape(key_prefix)}-(\d+)")
        else:
            # Scanning PREFIX-(\d+)
            target_pattern = re.compile(rf"{re.escape(key_prefix)}-(\d+)")

        for file_path in self.project_dir.rglob("*.md"):
            for match in target_pattern.finditer(file_path.name):
                try:
                    seq = int(match.group(1))
                    highest = max(highest, seq)
                except ValueError:
                    pass
        return highest

    def next_memory_id(
        self,
        type: str | None = None,
        legacy: bool = False,
        year: int | None = None,
    ) -> str:
        """Generates the next unique, collision-safe ID.

        If `type` is specified (e.g. 'observation', 'decision') and `legacy` is False and `year` is None,
        generates standard prefix format (e.g. OBS-001, DEC-001).
        Otherwise generates legacy format (MEM-YYYY-NNNN).
        """
        self._ensure_meta_dir()

        # Resolve prefix
        prefix: str | None = None
        if not legacy and year is None and type:
            type_str = str(getattr(type, "value", type)).lower().strip()
            prefix = TYPE_PREFIX_MAP.get(type_str)

        from researchos.core.storage_service import file_lock

        with file_lock(self.lock_file, timeout=10.0):
            sequences = self._read_sequences()

            if prefix:
                key = prefix
                current_seq = sequences.get(key, 0)
                scanned_highest = self._scan_highest_sequence_on_disk(prefix)
                next_seq = max(current_seq, scanned_highest) + 1
                sequences[key] = next_seq
                self._write_sequences(sequences)
                return f"{prefix}-{next_seq:03d}"
            else:
                if year is None:
                    year = datetime.now(UTC).year
                key = f"MEM-{year}"
                current_seq = sequences.get(key, 0)
                scanned_highest = self._scan_highest_sequence_on_disk(key)
                next_seq = max(current_seq, scanned_highest) + 1
                sequences[key] = next_seq
                self._write_sequences(sequences)
                return f"MEM-{year}-{next_seq:04d}"
