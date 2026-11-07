"""Sensitive data sanitization and credential redaction."""

import re
from typing import Any

DEFAULT_SENSITIVE_PATTERNS = [
    # Full multi-line private key blocks (RSA, OPENSSH, DSA, EC, PGP)
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
        re.MULTILINE,
    ),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.MULTILINE),
    # OpenAI API keys
    re.compile(r"\b(sk-[a-zA-Z0-9]{20,}|sk-proj-[a-zA-Z0-9_\-]{20,})\b"),
    # Anthropic API keys
    re.compile(r"\b(sk-ant-[a-zA-Z0-9_\-]{20,})\b"),
    # Hugging Face tokens
    re.compile(r"\b(hf_[a-zA-Z0-9]{20,})\b"),
    # GitHub personal access tokens
    re.compile(r"\b(ghp_[a-zA-Z0-9]{20,}|github_pat_[a-zA-Z0-9_\-]{20,})\b"),
    # AWS Access Key ID
    re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    # Bearer tokens in headers
    re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9_\-\.]{20,}\b"),
    # Key-value secret assignments: api_key, password, secret, token, access_token
    # Both quoted and unquoted: password: 'xxx' or password = "xxx" or password: xxx
    re.compile(
        r'(?i)\b(api[_-]?key|secret|password|passwd|auth[_-]?token|access[_-]?token|private[_-]?key)\b\s*[:=]\s*["\']?([^"\'\s\r\n]{6,})["\']?'
    ),
]

_custom_sensitive_patterns: list[re.Pattern] = []


def register_sensitive_pattern(pattern: re.Pattern | str) -> None:
    """Registers an additional regex pattern for secret redaction."""
    pat = re.compile(pattern) if isinstance(pattern, str) else pattern
    if pat not in _custom_sensitive_patterns:
        _custom_sensitive_patterns.append(pat)


def clear_custom_sensitive_patterns() -> None:
    """Clears dynamically registered patterns (useful for testing)."""
    _custom_sensitive_patterns.clear()


def get_all_sensitive_patterns() -> list[re.Pattern]:
    """Returns combined list of default and custom sensitive patterns."""
    return DEFAULT_SENSITIVE_PATTERNS + _custom_sensitive_patterns


def is_credential_key(key: str) -> bool:
    """Checks whether a dictionary key indicates an authentication secret."""
    k_lower = str(key).lower().strip()
    if any(s in k_lower for s in ("password", "private_key", "secret", "api_key", "api-key")):
        return True
    if k_lower in (
        "token",
        "access_token",
        "auth_token",
        "bearer_token",
        "refresh_token",
        "api_token",
        "session_token",
        "oauth_token",
    ):
        return True
    if ("_token" in k_lower or "-token" in k_lower) and not any(
        nlp in k_lower
        for nlp in ("max_", "num_", "total_", "target_", "input_", "output_", "pred_")
    ):
        return True
    return False


def sanitize_markdown_text(text: str) -> str:
    """Redacts sensitive credentials and secrets from raw markdown text."""
    if not text:
        return text

    sanitized = text
    # Apply all registered regex patterns
    for pat in get_all_sensitive_patterns():
        if pat.groups >= 2:
            # Key-value assignment match (e.g. key: secret) -> replace secret part with [REDACTED_CREDENTIAL]
            def _replace_kv(m: re.Match) -> str:
                prefix = m.group(1)
                # Keep the key label, redact the value
                return f"{prefix}: [REDACTED_CREDENTIAL]"

            sanitized = pat.sub(_replace_kv, sanitized)
        else:
            sanitized = pat.sub("[REDACTED_CREDENTIAL]", sanitized)

    return sanitized


def sanitize_sensitive_data(val: Any) -> Any:
    """Recursively redacts credential keys and sensitive strings."""
    if isinstance(val, str):
        return sanitize_markdown_text(val)
    elif isinstance(val, dict):
        new_dict = {}
        for k, v in val.items():
            if is_credential_key(str(k)):
                new_dict[k] = "[REDACTED_CREDENTIAL]"
            else:
                new_dict[k] = sanitize_sensitive_data(v)
        return new_dict
    elif isinstance(val, list):
        return [sanitize_sensitive_data(x) for x in val]
    return val
