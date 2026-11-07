"""Sensitive data sanitization and credential redaction."""

import re
from typing import Any

SENSITIVE_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.MULTILINE),
    re.compile(r'(?i)("?password"?\s*[:=]\s*")[^"]+(")'),
    re.compile(r'(?i)("?api[_-]?key"?\s*[:=]\s*")[^"]+(")'),
    re.compile(r'(?i)("?secret"?\s*[:=]\s*")[^"]+(")'),
    re.compile(r'(?i)("?token"?\s*[:=]\s*")[^"]+(")'),
]


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


def sanitize_sensitive_data(val: Any) -> Any:
    """Recursively redacts credential keys and sensitive strings."""
    if isinstance(val, str):
        sanitized = val
        for pat in SENSITIVE_PATTERNS:
            sanitized = pat.sub("[REDACTED_CREDENTIAL]", sanitized)
        return sanitized
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
