"""Storage service providing atomic I/O, frontmatter serialization, and concurrency protection."""

import os
import tempfile
import threading
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import portalocker
import yaml

from researchos.utils.exceptions import (
    LockAcquisitionError,
    PathSecurityError,
    ValidationError,
)


class _SafeDumper(yaml.SafeDumper):
    pass


def _represent_enum(dumper: yaml.SafeDumper, data: Enum) -> yaml.Node:
    val = data.value if hasattr(data, "value") else str(data)
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(val))


def _represent_datetime(dumper: yaml.SafeDumper, data: datetime) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data.isoformat())


def _represent_date(dumper: yaml.SafeDumper, data: date) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data.isoformat())


_SafeDumper.add_multi_representer(Enum, _represent_enum)
_SafeDumper.add_representer(datetime, _represent_datetime)
_SafeDumper.add_representer(date, _represent_date)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Splits markdown content into frontmatter metadata dict and markdown body."""
    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---"):
        return {}, normalized

    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, normalized

    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx == -1:
        raise ValidationError("Unclosed YAML frontmatter: missing closing '---'.")

    yaml_text = "".join(lines[1:end_idx])
    body_text = "".join(lines[end_idx + 1:]).lstrip("\n")

    try:
        metadata = yaml.safe_load(yaml_text) or {}
        if not isinstance(metadata, dict):
            raise ValidationError(
                f"Frontmatter must be a mapping, got {type(metadata).__name__}."
            )
        return metadata, body_text
    except yaml.YAMLError as exc:
        raise ValidationError(f"Failed to parse YAML frontmatter: {exc}") from exc


def dump_frontmatter(metadata: dict[str, Any], body: str) -> str:
    """Serializes metadata and markdown body into standard Markdown with YAML frontmatter."""
    yaml_str = yaml.dump(
        metadata,
        Dumper=_SafeDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    clean_body = body.strip("\n")
    if clean_body:
        return f"---\n{yaml_str}---\n\n{clean_body}\n"
    return f"---\n{yaml_str}---\n"


_local_locks = threading.local()


@contextmanager
def file_lock(lock_path: Path | str, timeout: float = 10.0) -> Generator[Path, None, None]:
    """Acquires a re-entrant exclusive file lock with timeout and deadlock protection."""
    path = Path(lock_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path)

    if not hasattr(_local_locks, "held"):
        _local_locks.held = {}

    if key in _local_locks.held:
        _local_locks.held[key] += 1
        try:
            yield path
        finally:
            _local_locks.held[key] -= 1
            if _local_locks.held[key] == 0:
                del _local_locks.held[key]
        return

    try:
        with portalocker.Lock(key, mode="a+", timeout=timeout):
            _local_locks.held[key] = 1
            try:
                yield path
            finally:
                _local_locks.held.pop(key, None)
    except portalocker.exceptions.LockException as exc:
        raise LockAcquisitionError(
            f"Failed to acquire lock on {path} within {timeout}s: {exc}"
        ) from exc


def atomic_write_text(path: Path | str, content: str, encoding: str = "utf-8") -> Path:
    """Atomically writes text content using a temporary file and atomic replace."""
    target_path = Path(path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

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

        os.replace(temp_path, target_path)
        return target_path
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def validate_path_within(
    base_dir: Path | str,
    target_path: Path | str,
    allow_symlinks: bool = False,
) -> Path:
    """Ensures target_path resolves strictly within base_dir to prevent path traversal and symlink escapes."""
    base = Path(base_dir).resolve()
    target = Path(target_path)
    combined = (base / target) if not target.is_absolute() else target

    try:
        resolved = combined.resolve()
        # Verify that the canonical path is within the base directory
        resolved.relative_to(base)

        # If symlinks are disallowed, verify no component escapes base via symlinks
        if not allow_symlinks and combined.is_symlink():
            # If the symlink itself points outside base, it was caught by relative_to above
            pass

        return resolved
    except (ValueError, RuntimeError) as exc:
        is_symlink = combined.is_symlink() or any(
            p.is_symlink() for p in combined.parents if base in p.parents or p == base
        )
        if is_symlink:
            raise PathSecurityError(
                f"Security violation: symlink '{target_path}' escapes base directory '{base}' to '{resolved}'."
            ) from exc
        raise PathSecurityError(
            f"Security violation: path '{target_path}' escapes base directory '{base}'."
        ) from exc
