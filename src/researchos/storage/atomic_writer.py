"""Atomic and durable file writing utilities."""

import os
from pathlib import Path
import tempfile


def atomic_write_text(path: Path | str, content: str, encoding: str = "utf-8") -> Path:
    """Atomically writes text content to target path using a temp file and fsync."""
    target_path = Path(path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Use target directory for temp file to ensure it's on the same filesystem
    fd, temp_file_path = tempfile.mkstemp(
        prefix=f".{target_path.name}.",
        suffix=".tmp",
        dir=str(target_path.parent),
    )
    temp_path = Path(temp_file_path)

    try:
        with open(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        # Atomic replace
        os.replace(temp_path, target_path)
        return target_path
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_bytes(path: Path | str, content: bytes) -> Path:
    """Atomically writes binary content to target path using a temp file and fsync."""
    target_path = Path(path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_file_path = tempfile.mkstemp(
        prefix=f".{target_path.name}.",
        suffix=".tmp",
        dir=str(target_path.parent),
    )
    temp_path = Path(temp_file_path)

    try:
        with open(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, target_path)
        return target_path
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
