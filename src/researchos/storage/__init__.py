"""Storage layer for ResearchOS: Markdown persistence, atomic writes, and locks."""

from researchos.storage.atomic_writer import atomic_write_bytes, atomic_write_text
from researchos.storage.file_lock import file_lock
from researchos.storage.frontmatter import dump_frontmatter, parse_frontmatter
from researchos.storage.link_resolver import (
    compute_relative_link,
    extract_markdown_links,
    format_markdown_link,
    validate_vault_path,
)
from researchos.storage.markdown_store import MarkdownStore

__all__ = [
    "MarkdownStore",
    "atomic_write_bytes",
    "atomic_write_text",
    "compute_relative_link",
    "dump_frontmatter",
    "extract_markdown_links",
    "file_lock",
    "format_markdown_link",
    "parse_frontmatter",
    "validate_vault_path",
]
