"""Strict YAML frontmatter parser and serializer for Markdown files."""

from datetime import date, datetime
from enum import Enum
from typing import Any
import yaml

from researchos.core.exceptions import ValidationError


class _SafeDumper(yaml.SafeDumper):
    """Custom safe YAML dumper for custom types."""
    pass


def _represent_enum(dumper: yaml.SafeDumper, data: Enum) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data.value if hasattr(data, "value") else data))


def _represent_datetime(dumper: yaml.SafeDumper, data: datetime) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data.isoformat())


def _represent_date(dumper: yaml.SafeDumper, data: date) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data.isoformat())


_SafeDumper.add_multi_representer(Enum, _represent_enum)
_SafeDumper.add_representer(datetime, _represent_datetime)
_SafeDumper.add_representer(date, _represent_date)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Splits markdown content into frontmatter metadata dict and markdown body.

    Args:
        content: The raw text of the markdown file.

    Returns:
        A tuple of (metadata, body).

    Raises:
        ValidationError: If the frontmatter delimiter is invalid or YAML parsing fails.
    """
    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---"):
        return {}, normalized

    # Find the closing delimiter
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
    """Serializes metadata and markdown body into standard Markdown format with YAML frontmatter.

    Args:
        metadata: Dictionary containing frontmatter properties.
        body: Markdown body text.

    Returns:
        Combined markdown text with '---' delimited YAML header.
    """
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
