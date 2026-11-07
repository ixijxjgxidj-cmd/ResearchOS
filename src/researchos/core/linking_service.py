"""Relative Markdown link resolution and extraction service."""

import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Final

MD_LINK_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\[(?P<text>[^\]]+)\]\((?P<target>[^\)]+)\)"
)


class LinkingService:
    """Manages relative cross-linking between memory documents."""

    @staticmethod
    def compute_relative_link(source_file: Path | str, target_file: Path | str) -> str:
        """Computes a standard forward-slash relative path from source_file's parent to target_file."""
        src = Path(source_file).resolve()
        tgt = Path(target_file).resolve()
        src_dir = src.parent
        rel_path = os.path.relpath(tgt, src_dir)
        return PurePosixPath(rel_path).as_posix()

    @staticmethod
    def format_markdown_link(label: str, source_file: Path | str, target_file: Path | str) -> str:
        """Formats a standard Markdown link [label](relpath)."""
        rel = LinkingService.compute_relative_link(source_file, target_file)
        return f"[{label}]({rel})"

    @staticmethod
    def extract_markdown_links(content: str) -> list[tuple[str, str]]:
        """Extracts all markdown links as a list of (label, target)."""
        return [(m.group("text"), m.group("target")) for m in MD_LINK_PATTERN.finditer(content)]

    @staticmethod
    def verify_internal_links(project_dir: Path | str, file_path: Path | str, content: str) -> list[str]:
        """Returns a list of broken internal links found in the content."""
        detailed = LinkingService.verify_internal_links_detailed(project_dir, file_path, content)
        return [d["message"] for d in detailed]

    @staticmethod
    def verify_internal_links_detailed(
        project_dir: Path | str, file_path: Path | str, content: str
    ) -> list[dict[str, Any]]:
        """Returns structured details of broken internal links found in the content."""
        p_dir = Path(project_dir).resolve()
        src_file = Path(file_path).resolve()
        src_dir = src_file.parent
        broken: list[dict[str, Any]] = []

        rel_src = src_file.relative_to(p_dir).as_posix() if src_file.is_relative_to(p_dir) else src_file.name

        for line_num, line in enumerate(content.splitlines(), start=1):
            for label, target in LinkingService.extract_markdown_links(line):
                if target.startswith("http://") or target.startswith("https://") or target.startswith("mailto:"):
                    continue
                target_clean = target.split("#")[0]
                if not target_clean:
                    continue

                target_path = (src_dir / target_clean).resolve()
                if not target_path.exists():
                    broken.append({
                        "source_file": rel_src,
                        "line_number": line_num,
                        "label": label,
                        "target": target,
                        "expected_path": target_path.as_posix(),
                        "message": f"{rel_src}:{line_num} -> [{label}]({target}) missing target {target_clean}",
                    })

        return broken
