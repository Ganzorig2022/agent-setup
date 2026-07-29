"""Deterministic Stage 0A finding categories and usability checks."""

from __future__ import annotations

import re


_CATEGORY_PATTERNS = (
    (
        "ui-correctness",
        re.compile(
            r"\b(?:off-screen|render\w*|layout|logo|key\s+prop|heading\s+order|"
            r"printable|widths?|stamp|signature|terminology|state\s+combination|"
            r"overflow\s+guard|collision)\b",
            re.I,
        ),
    ),
    (
        "data-integrity",
        re.compile(
            r"\b(?:audit\s+trail|correlation|inconsistent(?:\s+escalation)?\s+"
            r"(?:recording|data)|"
            r"numeric\s+range|column|embedding\w*|composite\s+index|cascade|"
            r"data\s+integrity)\b",
            re.I,
        ),
    ),
    (
        "matching-correctness",
        re.compile(
            r"\b(?:substring\s+matching|entity\s+decod\w*|false[- ]positive\s+"
            r"(?:match|escalation)|exact\s+match|typo|letter\s+class)\b",
            re.I,
        ),
    ),
    (
        "compatibility",
        re.compile(
            r"\b(?:narrower|legacy\s+data|backward\s+compatib\w*|"
            r"breaking\s+change)\b",
            re.I,
        ),
    ),
    (
        "delivery-reliability",
        re.compile(
            r"\b(?:weekly\s+generation|offline\s+(?:run|launch)|handoff|"
            r"operator\s+never\s+notified|delivery)\b",
            re.I,
        ),
    ),
    (
        "feature-gating",
        re.compile(
            r"\b(?:scanning|explicitly\s+enabled|feature\s+gate|kill\s+switch)\b",
            re.I,
        ),
    ),
    ("injection", re.compile(r"\b(?:sql\s*injection|injection|interpolat\w*)\b", re.I)),
    (
        "validation",
        re.compile(
            r"\b(?:validat\w*|unvalidat\w*|schema|unsafe\s+(?:request|input)|"
            r"unchecked\s+input)\b",
            re.I,
        ),
    ),
    (
        "race-idempotency",
        re.compile(
            r"\b(?:race|re-entr\w*|idempoten\w*|duplicat\w*|retry|double[- ]"
            r"(?:charge|credit|write)|dedup\w*)\b",
            re.I,
        ),
    ),
    (
        "error-handling",
        re.compile(
            r"\b(?:swallow\w*|silent(?:ly)?|empty\s+catch|exception|rethrow|"
            r"fallback|failure|error\s+handling|unhandled)\b",
            re.I,
        ),
    ),
    (
        "transaction-integrity",
        re.compile(
            r"\b(?:transaction|rollback|foreign\s+key|migration|data\s+loss|"
            r"atomic\w*|lost\s+update)\b",
            re.I,
        ),
    ),
    (
        "secret-exposure",
        re.compile(
            r"\b(?:secret|credential|password|api\s+key|bearer|pii|expos\w*|"
            r"(?:absolute|local)\s+(?:source\s+)?paths?|path\s+leak\w*)\b",
            re.I,
        ),
    ),
    (
        "authorization",
        re.compile(r"\b(?:authoriz\w*|permission|access\s+control|authn|authz)\b", re.I),
    ),
    (
        "type-safety",
        re.compile(
            r"\b(?:type\s+safety|unsafe\s+cast|signature\s+mismatch|null|undefined)\b",
            re.I,
        ),
    ),
    (
        "accessibility",
        re.compile(
            r"\b(?:accessib\w*|assistive|aria|heading\s+order|screen\s+reader)\b",
            re.I,
        ),
    ),
    (
        "performance",
        re.compile(r"\b(?:n\+1|unbounded|event\s+loop|hot\s+path|complexity)\b", re.I),
    ),
    (
        "observability",
        re.compile(
            r"\b(?:logging|log\s+context|diagnostic|metric|counter|observability)\b",
            re.I,
        ),
    ),
    (
        "test-eval",
        re.compile(
            r"\b(?:test|assertion|fixture|baseline|drill|eval(?:uation)?)\b",
            re.I,
        ),
    ),
    (
        "lifecycle-cleanup",
        re.compile(
            r"\b(?:stale\s+closure|hook|effect|interval|listener|cleanup|resource\s+leak)\b",
            re.I,
        ),
    ),
    (
        "dependency-config",
        re.compile(
            r"\b(?:dependency|package|configuration|config|runtime|node\s+baseline)\b",
            re.I,
        ),
    ),
)
_TOKEN = re.compile(r"\b[\w'-]+\b", re.UNICODE)
_DISMISSAL = re.compile(
    r"\b(?:informational|not a bug|not introduced|retracted|no code issue)\b",
    re.I,
)


def categorize_finding(abstract: str) -> str:
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(abstract):
            return category
    return ""


def finding_usability(
    *,
    abstract: str,
    category: str,
    source_format: str,
) -> tuple[bool, str]:
    if source_format == "severity_table_summary":
        return False, "summary-only-finding"
    if _DISMISSAL.search(abstract):
        return False, "dismissed-or-informational"
    if len(_TOKEN.findall(abstract)) < 5:
        return False, "abstract-too-short"
    if not category:
        return False, "missing-category"
    return True, ""
