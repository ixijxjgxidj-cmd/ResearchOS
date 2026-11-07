"""Security tests for sensitive credential redaction across Frontmatter and Markdown body."""

from pathlib import Path

from researchos.core.memory_service import MemoryService
from researchos.core.project_service import ProjectService
from researchos.utils.sanitizer import (
    clear_custom_sensitive_patterns,
    register_sensitive_pattern,
    sanitize_markdown_text,
)


def test_markdown_body_credential_redaction(tmp_path: Path):
    vault = tmp_path / "vault"
    ps = ProjectService(vault)
    ps.create_project("Security Project", project_id="sec-proj")
    ms = MemoryService(vault)

    # Content with OpenAI API key, Anthropic API key, SSH private key, password
    leaked_content = (
        "Here are the experiment keys:\n"
        "OpenAI: sk-proj-1234567890abcdef1234567890abcdef\n"
        "Anthropic: sk-ant-api03-abcdef1234567890abcdef123456\n"
        "HuggingFace: hf_abcdefghijklmnopqrstuvwxyz012345\n"
        "Database password: my_super_secret_db_pass_1234\n"
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABlwAAAAdzc2gtcn\n"
        "-----END OPENSSH PRIVATE KEY-----\n"
    )

    mem = ms.add_memory(
        project_id="sec-proj",
        type="knowledge",
        title="Infrastructure Setup Secrets",
        content=leaked_content,
        tags=["security"],
    )

    # Read raw file from disk
    p_dir = ps.get_project_dir("sec-proj")
    raw_disk_text = (p_dir / mem.file_path).read_text(encoding="utf-8")

    # Verify sensitive tokens are NOT present on disk
    assert "sk-proj-" not in raw_disk_text
    assert "sk-ant-api03-" not in raw_disk_text
    assert "hf_abcdefgh" not in raw_disk_text
    assert "my_super_secret_db_pass_1234" not in raw_disk_text
    assert "b3BlbnNzaC1rZXktdjE" not in raw_disk_text
    assert "[REDACTED_CREDENTIAL]" in raw_disk_text


def test_custom_sensitive_pattern_registration():
    try:
        custom_token = "COMPANY_CONFIDENTIAL_TOKEN_XYZ_9999"
        text = f"The internal token is {custom_token}."

        # Before registering, not redacted
        assert custom_token in sanitize_markdown_text(text)

        # Register custom pattern
        register_sensitive_pattern(r"COMPANY_CONFIDENTIAL_[A-Z0-9_]+")

        sanitized = sanitize_markdown_text(text)
        assert custom_token not in sanitized
        assert "[REDACTED_CREDENTIAL]" in sanitized
    finally:
        clear_custom_sensitive_patterns()
