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


# Scientific and machine learning keys/values that must NEVER be redacted as credentials
SCIENTIFIC_KEY_WHITELIST = {
    "special_tokens",
    "pad_token",
    "pad_token_id",
    "bos_token",
    "bos_token_id",
    "eos_token",
    "eos_token_id",
    "mask_token",
    "mask_token_id",
    "cls_token",
    "cls_token_id",
    "sep_token",
    "sep_token_id",
    "unk_token",
    "unk_token_id",
    "token_type_ids",
    "token_embeddings",
    "token_stride",
    "token_length",
    "num_tokens",
    "max_tokens",
    "target_tokens",
    "input_tokens",
    "output_tokens",
    "used_tokens",
    "total_tokens",
    "tokens",
    "token_count",
    "tokenizer",
    "tokenizer_name",
    "tokenizer_type",
    "tokenizer_config",
    "hash",
    "file_hash",
    "file_hashes",
    "commit_hash",
    "model_hash",
    "dataset_hash",
    "sha256",
    "sha1",
    "sha512",
    "md5",
    "checksum",
    "checksums",
    "signature",
    "commit",
    "release_commit",
    "code_commit",
    "git_commit",
    "codevector",
    "codevectors",
    "tokens_per_group",
    "num_codevectors_per_group",
    "proj_codevector_dim",
}

SCIENTIFIC_TEXT_PROTECT_PATTERN = re.compile(
    r'(?i)\b(?:sha256|sha1|sha512|md5|checksum|git_commit|commit_hash|code_commit|release_commit|special_tokens|pad_token|mask_token)\s*[:=]\s*["\']?[0-9a-zA-Z_\-\.]{10,}["\']?'
)


def is_scientific_whitelisted_key(k_lower: str) -> bool:
    """Returns True if the key represents scientific/ML concepts rather than credentials."""
    if k_lower in SCIENTIFIC_KEY_WHITELIST:
        return True
    if any(k_lower.endswith(s) for s in ("_hash", "_hashes", "_checksum", "_checksums", "_commit")):
        return True
    if any(k_lower.startswith(s) for s in ("token_", "tokens_", "tokenizer_")):
        return True
    if any(term in k_lower for term in ("pad_token", "mask_token", "cls_token", "sep_token", "bos_token", "eos_token", "special_token")):
        return True
    return False


def is_credential_key(key: str) -> bool:
    """Checks whether a dictionary key indicates an authentication secret."""
    k_lower = str(key).lower().strip()

    # Explicit whitelist: never redact scientific/ML token definitions or checksum hashes
    if is_scientific_whitelisted_key(k_lower):
        return False

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
    """Redacts sensitive credentials and secrets from raw markdown text while preserving scientific data."""
    if not text:
        return text

    # Step 1: Temporarily protect scientific hashes and ML token definitions
    protected_spans: dict[str, str] = {}
    def _protect_match(m: re.Match) -> str:
        key = f"__SAFE_SCIENTIFIC_TOKEN_{len(protected_spans)}__"
        protected_spans[key] = m.group(0)
        return key

    masked_text = SCIENTIFIC_TEXT_PROTECT_PATTERN.sub(_protect_match, text)

    # Step 2: Apply all registered secret regex patterns
    sanitized = masked_text
    for pat in get_all_sensitive_patterns():
        if pat.groups >= 2:
            # Key-value assignment match (e.g. key: secret) -> replace secret part with [REDACTED_CREDENTIAL]
            def _replace_kv(m: re.Match) -> str:
                prefix = m.group(1)
                return f"{prefix}: [REDACTED_CREDENTIAL]"

            sanitized = pat.sub(_replace_kv, sanitized)
        else:
            sanitized = pat.sub("[REDACTED_CREDENTIAL]", sanitized)

    # Step 3: Restore protected scientific data
    for marker, original in protected_spans.items():
        sanitized = sanitized.replace(marker, original)

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
