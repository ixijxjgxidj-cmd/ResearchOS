"""Standard relative Markdown link resolution and extraction."""

import os
from pathlib import Path, PurePosixPath
import re
from typing import Final

from researchos.core.exceptions import PathSecurityError

# Regex to match [text](relative_path)
MD_LINK_PATTERN: Final[re.Pattern[str]] = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<target>[^\)]+)\)")


def compute_relative_link(source_file: Path | str, target_file: Path | str) -> str:
    """Computes a standard forward-slash relative path from source_file's parent directory to target_file."""
    src = Path(source_file).resolve()
    tgt = Path(target_file).resolve()

    src_dir = src.parent
    rel_path = os.path.relpath(tgt, src_dir)
    # Convert Windows backslashes to standard forward slashes for Markdown links
    return PurePosixPath(rel_path).as_posix()


def format_markdown_link(label: str, source_file: Path | str, target_file: Path | str) -> str:
    """Formats a standard Markdown link [label](relpath)."""
    rel = compute_relative_link(source_file, target_file)
    return f"[{label}]({rel})"


def extract_markdown_links(content: str) -> list[tuple[str, str]]:
    """Extracts all markdown links as a list of (label, target_url/path)."""
    return [(m.group("text"), m.group("target")) for m in MD_LINK_PATTERN.finditer(content)]


def validate_vault_path(vault_root: Path | str, target_path: Path | str) -> Path:
    """Ensures target_path is inside vault_root, preventing path traversal attacks.

    Raises:
        PathSecurityError: if target_path resolves outside of vault_root.
    """
    root = Path(vault_root).resolve()
    try:
        resolved = (root / target_path).resolve()
        resolved.relative_to(root)
        return resolved
    except (ValueError, RuntimeError) as exc:
        raise PathSecurityError(
            f"Access denied: Path '{target_path}' escapes vault root '{root}'."
        ) from exc
