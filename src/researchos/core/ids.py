"""Identifier generation and validation for ResearchOS entities."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Final

from researchos.core.enums import IdPrefix
from researchos.core.exceptions import ValidationError

ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<prefix>PRJ|EXP|RUN|PAPER|FIND|CLAIM|ART|DEC)-(?P<year>\d{4})-(?P<seq>\d{3,})$"
)


def validate_id(id_str: str) -> tuple[str, int, int]:
    """Validates an entity ID string and returns (prefix, year, seq).

    Raises:
        ValidationError: if the string does not match the valid ID format.
    """
    match = ID_PATTERN.match(id_str)
    if not match:
        raise ValidationError(
            f"Invalid ResearchOS ID format '{id_str}'. Must match '{ID_PATTERN.pattern}'."
        )
    return match.group("prefix"), int(match.group("year")), int(match.group("seq"))


def is_valid_id(id_str: str) -> bool:
    """Returns True if the ID matches the format, False otherwise."""
    return bool(ID_PATTERN.match(id_str))


class IdGenerator:
    """Thread- and process-safe monotonic ID generator backed by filesystem sequences."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve()
        self.meta_dir = self.vault_root / ".researchos"
        self.lock_dir = self.meta_dir / "locks"
        self.seq_file = self.meta_dir / "sequences.json"
        self.lock_file = self.lock_dir / "id_sequence.lock"

    def _ensure_meta_dirs(self) -> None:
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.lock_dir.mkdir(parents=True, exist_ok=True)

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
        from researchos.storage.atomic_writer import atomic_write_text
        atomic_write_text(self.seq_file, json.dumps(sequences, indent=2))

    def _scan_highest_sequence_on_disk(self, prefix: str, year: int) -> int:
        """Scans the vault directory for existing IDs to prevent reuse even if state file is lost."""
        highest = 0
        if not self.vault_root.exists():
            return 0

        target_pattern = re.compile(rf"{re.escape(prefix)}-{year}-(\d+)")
        for file_path in self.vault_root.rglob("*.md"):
            # Check filename
            for match in target_pattern.finditer(file_path.name):
                seq = int(match.group(1))
                if seq > highest:
                    highest = seq
        return highest

    def generate_id(self, prefix: IdPrefix | str, year: int | None = None) -> str:
        """Generates the next unique, collision-safe ID for the given prefix."""
        prefix_str = str(prefix)
        if year is None:
            year = datetime.now(timezone.utc).year

        key = f"{prefix_str}-{year}"
        self._ensure_meta_dirs()

        from researchos.storage.file_lock import file_lock

        with file_lock(self.lock_file, timeout=10.0):
            sequences = self._read_sequences()
            current_seq = sequences.get(key, 0)
            scanned_highest = self._scan_highest_sequence_on_disk(prefix_str, year)
            next_seq = max(current_seq, scanned_highest) + 1

            sequences[key] = next_seq
            self._write_sequences(sequences)

            return f"{prefix_str}-{year}-{next_seq:03d}"
