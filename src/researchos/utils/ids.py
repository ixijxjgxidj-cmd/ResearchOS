"""Identifier generation and validation for ResearchOS Universal Memory."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from researchos.utils.exceptions import ValidationError

MEMORY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^MEM-(?P<year>\d{4})-(?P<seq>\d{3,})$"
)

PROJECT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-zA-Z0-9_\-]+$"
)


def validate_memory_id(id_str: str) -> tuple[int, int]:
    """Validates a memory ID string and returns (year, seq).

    Raises:
        ValidationError: if the string does not match MEM-YYYY-NNN.
    """
    match = MEMORY_ID_PATTERN.match(id_str)
    if not match:
        raise ValidationError(
            f"Invalid Memory ID format '{id_str}'. Must match '{MEMORY_ID_PATTERN.pattern}'."
        )
    return int(match.group("year")), int(match.group("seq"))


def is_valid_memory_id(id_str: str) -> bool:
    """Returns True if the string is a valid MEM-YYYY-NNN format."""
    return bool(MEMORY_ID_PATTERN.match(id_str))


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

    def _scan_highest_sequence_on_disk(self, year: int) -> int:
        """Scans project directory for existing MEM-YYYY-NNN files to ensure zero collisions."""
        highest = 0
        if not self.project_dir.exists():
            return 0

        target_pattern = re.compile(rf"MEM-{year}-(\d+)")
        for file_path in self.project_dir.rglob("*.md"):
            for match in target_pattern.finditer(file_path.name):
                seq = int(match.group(1))
                highest = max(highest, seq)
        return highest

    def next_memory_id(self, year: int | None = None) -> str:
        """Generates the next unique, collision-safe ID in format MEM-YYYY-NNN."""
        if year is None:
            year = datetime.now(UTC).year

        key = f"MEM-{year}"
        self._ensure_meta_dir()

        from researchos.core.storage_service import file_lock

        with file_lock(self.lock_file, timeout=10.0):
            sequences = self._read_sequences()
            current_seq = sequences.get(key, 0)
            scanned_highest = self._scan_highest_sequence_on_disk(year)
            next_seq = max(current_seq, scanned_highest) + 1

            sequences[key] = next_seq
            self._write_sequences(sequences)

            return f"MEM-{year}-{next_seq:04d}"
