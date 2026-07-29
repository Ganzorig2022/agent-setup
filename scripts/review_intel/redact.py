"""Fail-closed redaction helpers for derived reviewer traces."""

from __future__ import annotations

import hashlib
import re


_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_QUOTED_VALUE = re.compile(r"""(?:"[^"\n]{2,}"|'[^'\n]{2,}')""")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_ABS_PATH = re.compile(r"(?<!\w)(?:/Users/|/home/|/private/|/var/|/tmp/)\S+")
_WIN_PATH = re.compile(r"\b[A-Z]:\\[^\s]+", re.IGNORECASE)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|token|secret|password|authorization)\b"
    r"\s*[:=]\s*[^\s,;]+"
)
_BEARER_SECRET = re.compile(
    r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{12,}"
)
_LABELED_SECRET = re.compile(
    r"(?i)\b(?:api[_ -]?key|token|secret|password|authorization)\b"
    r"\s+(?:is\s+)?[A-Za-z0-9._~+/-]{8,}"
)
_HIGH_ENTROPY_TOKEN = re.compile(
    r"\b(?=[A-Za-z0-9_-]{24,}\b)"
    r"(?=[A-Za-z0-9_-]*[A-Za-z])"
    r"(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]+\b"
)
_LONG_HASH = re.compile(r"\b[0-9a-f]{20,}\b", re.IGNORECASE)
_SNAKE_CASE = re.compile(r"\b[A-Za-z]+_[A-Za-z0-9_]{2,}\b")
_KEBAB_IDENTIFIER = re.compile(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b")
_DOTTED_IDENTIFIER = re.compile(r"\b[A-Za-z_$][\w$]*\.[A-Za-z_$][\w$]*\b")
_MIXED_IDENTIFIER = re.compile(
    r"\b(?:[A-Z]{2,}[A-Za-z0-9]*|"
    r"[A-Z][a-z]+(?:[A-Z][A-Za-z0-9]+)+|"
    r"[a-z]+(?:[A-Z][A-Za-z0-9]+)+)\b"
)
_FILE_PATH = re.compile(
    r"(?<!\w)(?:[\w.-]+/)*[\w.-]+\."
    r"(?:json|jsx|tsx|toml|yaml|dart|sql|js|ts|py|yml|md)(?!\w)"
)


def digest(*parts: str, salt: bytes = b"") -> str:
    material = "\x1f".join(parts).encode("utf-8", "replace")
    return hashlib.sha256(salt + material).hexdigest()


def redact_text(value: str, *, limit: int = 240) -> str:
    text = _CODE_FENCE.sub("[code removed]", value)
    text = _INLINE_CODE.sub("[inline code]", text)
    text = _QUOTED_VALUE.sub("[quoted value]", text)
    text = _BEARER_SECRET.sub("[secret removed]", text)
    text = _LABELED_SECRET.sub("[secret removed]", text)
    text = _SECRET_ASSIGNMENT.sub("[secret removed]", text)
    text = _URL.sub("[url]", text)
    text = _EMAIL.sub("[email]", text)
    text = _IP.sub("[ip]", text)
    text = _ABS_PATH.sub("[path]", text)
    text = _WIN_PATH.sub("[path]", text)
    text = _FILE_PATH.sub("[file]", text)
    text = _LONG_HASH.sub("[hash]", text)
    text = _SNAKE_CASE.sub("[identifier]", text)
    text = _KEBAB_IDENTIFIER.sub("[identifier]", text)
    text = _DOTTED_IDENTIFIER.sub("[identifier]", text)
    text = _HIGH_ENTROPY_TOKEN.sub("[secret removed]", text)
    text = _MIXED_IDENTIFIER.sub("[identifier]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    if limit <= 1:
        return "…"[:limit]
    raw_prefix = text[: limit - 1]
    prefix = raw_prefix.rstrip()
    if raw_prefix and not raw_prefix[-1].isspace() and " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0]
    return f"{prefix}…"


def privacy_violations(record: dict) -> list[dict[str, str]]:
    """Return residual sensitive-value matches in human-derived text fields."""
    checks = (
        ("absolute_path", _ABS_PATH),
        ("windows_path", _WIN_PATH),
        ("url", _URL),
        ("email", _EMAIL),
        ("ip_address", _IP),
        ("secret_assignment", _SECRET_ASSIGNMENT),
        ("bearer_secret", _BEARER_SECRET),
        ("labeled_secret", _LABELED_SECRET),
        ("high_entropy_token", _HIGH_ENTROPY_TOKEN),
        ("long_hash", _LONG_HASH),
        ("snake_case_identifier", _SNAKE_CASE),
        ("kebab_identifier", _KEBAB_IDENTIFIER),
        ("dotted_identifier", _DOTTED_IDENTIFIER),
        ("mixed_identifier", _MIXED_IDENTIFIER),
        ("file_path", _FILE_PATH),
    )
    values: list[tuple[str, str]] = []
    goal = record.get("goal_abstract")
    if isinstance(goal, str):
        values.append(("goal_abstract", goal))
    for index, finding in enumerate(record.get("findings") or []):
        if not isinstance(finding, dict):
            continue
        abstract = finding.get("abstract")
        if isinstance(abstract, str):
            values.append((f"findings.{index}.abstract", abstract))
    violations: list[dict[str, str]] = []
    for field, value in values:
        for kind, pattern in checks:
            if pattern.search(value):
                violations.append({"field": field, "kind": kind})
    return violations
