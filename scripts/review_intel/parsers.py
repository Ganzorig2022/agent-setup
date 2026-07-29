"""Provider-specific transcript parsers."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
from dataclasses import dataclass


EDITABLE_REVIEWERS = {
    "code-reviewer",
    "typescript-reviewer",
    "react-reviewer",
    "flutter-reviewer",
    "security-reviewer",
    "database-reviewer",
    "silent-failure-hunter",
}
SEVERITY_ALIASES = {
    "blocker": "critical",
    "critical": "critical",
    "major": "high",
    "high": "high",
    "medium": "medium",
    "minor": "low",
    "low": "low",
    "nit": "low",
}
_SEVERITY_LINE = re.compile(
    r"(?im)^[ \t]*(?:#{1,4}[ \t]*)?(?:[-*][ \t]*)?(?:\d+\.[ \t]*)?"
    r"(?:\*\*)?\[?(BLOCKER|CRITICAL|MAJOR|HIGH|MEDIUM|MINOR|LOW|NIT)\]?"
    r"(?:\*\*)?[ \t]*(?:[-—:|][ \t]*|[ \t]+)(.+)$"
)
_BARE_HEADING = re.compile(
    r"(?i)^(?:issues?|findings?|review findings|summary|"
    r"review summary|notes?)[:.]?$"
)
_NON_FINDING_ABSTRACT = re.compile(
    r"(?i)^(?:none|none found|no issues?|no findings?|0)[:.]?$"
)
_SEVERITY_SECTION = re.compile(
    r"^[ \t]*#{2,4}[ \t]+"
    r"(BLOCKER|CRITICAL|MAJOR|HIGH|MEDIUM|MINOR|LOW|NIT)"
    r"(?:[ \t]+Issues?)?[ \t]*$",
    re.I,
)
_NUMBERED_SEVERITY_LINE = re.compile(
    r"^[ \t]*(?:[-*][ \t]*)?\*\*(?:\d+\.[ \t]*)?"
    r"(BLOCKER|CRITICAL|MAJOR|HIGH|MEDIUM|MINOR|LOW|NIT)"
    r"[ \t]*[-—:][ \t]*(.+?)\*\*[ \t]*$",
    re.I,
)
_SECTION_HEADING_FINDING = re.compile(
    r"^[ \t]*#{4}[ \t]+(?:\d+\.[ \t]*)?(.+?)[ \t]*$"
)
_SECTION_BOLD_FINDING = re.compile(
    r"^[ \t]*\*\*(.+?)\*\*[ \t]*$"
)
_NON_FINDING_PREFIX = re.compile(
    r"(?i)^(?:(?:approve|approved|pass|verdict|evidence|impact|fix|status)\b"
    r"|/[ \t]*notes?\b)"
)
_LEADING_SEVERITY_MARKER = re.compile(
    r"(?i)^\[?(?:BLOCKER|CRITICAL|MAJOR|HIGH|MEDIUM|MINOR|LOW|NIT)\]?"
    r"(?:[ \t]*[-—:][ \t]*|[ \t]+)"
)
_CLEAN = re.compile(
    r"(?im)^\s*(?:#{1,4}\s*)?(?:\*\*)?(?:✅\s*)?"
    r"(?:verdict:\s*)?(?:pass|approve|approved)\b"
    r"(?:\*\*)?(?:\s*[-—:]\s*|\.\s*|\s*$)"
    r".*$"
)
_NO_FINDINGS = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:no verified findings|"
    r"no actionable findings|no findings|found no (?:issues|defects))\.?\s*$"
)
_CLEAN_ASSERTION = re.compile(
    r"(?im)^[ \t]*(?:"
    r"no verified actionable findings\b|"
    r"no actionable (?:\w+[ \t]+){0,3}issues remain\b|"
    r"findings:[ \t]*none\b|"
    r"approve for\b|"
    r"approval:.*\bapproved\b|"
    r"reassessment:.*\bfindings are retracted\b|"
    r"revised verdict:[ \t]*\*\*no code blocker found\b"
    r").*$"
)
_QRI_TRAILER = re.compile(
    r"```qri-v1\s*(\[.*?\])\s*```",
    re.DOTALL | re.IGNORECASE,
)
_QRI_DECLARATION = re.compile(r"```qri-v1\b", re.IGNORECASE)
_QRI_CATEGORIES = {
    "ui-correctness",
    "data-integrity",
    "matching-correctness",
    "compatibility",
    "delivery-reliability",
    "feature-gating",
    "injection",
    "validation",
    "race-idempotency",
    "error-handling",
    "transaction-integrity",
    "secret-exposure",
    "authorization",
    "type-safety",
    "accessibility",
    "performance",
    "observability",
    "test-eval",
    "lifecycle-cleanup",
    "dependency-config",
    "uncategorized",
}
_QRI_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
_SEVERITY_TABLE_ROW = re.compile(
    r"(?im)^\s*\|\s*(BLOCKER|CRITICAL|MAJOR|HIGH|MEDIUM|MINOR|LOW|NIT)"
    r"\s*\|\s*(\d+)\s*\|"
)


@dataclass(frozen=True)
class CandidateRun:
    provider: str
    source_class: str
    reviewer_role: str
    session_id: str
    agent_id: str
    final_message_id: str
    parent_session_id: str
    cwd: str
    branch: str
    timestamp: str
    model: str
    goal: str
    output: str
    source_key: str


def declares_qri_v1(output: str) -> bool:
    return bool(_QRI_DECLARATION.search(output))


def _valid_qri_file(value: str) -> bool:
    if not value:
        return False
    if value.startswith(("/", "~")):
        return False
    if re.match(r"(?i)^[a-z][a-z0-9+.-]*:", value):
        return False
    path = pathlib.PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    return True


def _qri_abstract_word_count(value: str) -> int:
    return len(re.findall(r"\b[\w-]+\b", value))


def parse_timestamp(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def extract_findings(output: str) -> tuple[str, list[dict[str, str]]]:
    trailer_match = _QRI_TRAILER.search(output)
    if trailer_match:
        try:
            payload = json.loads(trailer_match.group(1))
        except json.JSONDecodeError:
            return "unparsed", []
        if not isinstance(payload, list):
            return "unparsed", []
        structured: list[dict[str, str]] = []
        for item in payload:
            if not isinstance(item, dict) or set(item) != {
                "severity",
                "category",
                "abstract",
                "file",
            }:
                return "unparsed", []
            if not all(
                isinstance(item[key], str)
                for key in ("severity", "category", "abstract", "file")
            ):
                return "unparsed", []
            raw_severity = str(item.get("severity") or "").strip()
            if raw_severity not in _QRI_SEVERITIES:
                return "unparsed", []
            severity = raw_severity.lower()
            abstract = str(item.get("abstract") or "").strip()
            category = str(item.get("category") or "").strip().lower()
            file_value = str(item.get("file") or "").strip()
            if (
                not abstract
                or _qri_abstract_word_count(abstract) < 5
                or not _valid_qri_file(file_value)
                or category not in _QRI_CATEGORIES
            ):
                return "unparsed", []
            structured.append(
                {
                    "severity": severity,
                    "abstract": abstract,
                    "reported_category": category,
                    "source_format": "qri-v1",
                }
            )
        return (
            ("parsed_findings", structured)
            if structured
            else ("parsed_clean", [])
        )
    findings = []
    for match in _SEVERITY_LINE.finditer(output):
        abstract = match.group(2).strip().strip("*_").strip()
        abstract = abstract.lstrip("#").strip()
        if (
            not abstract
            or _BARE_HEADING.fullmatch(abstract)
            or _NON_FINDING_ABSTRACT.fullmatch(abstract)
            or _NON_FINDING_PREFIX.match(abstract)
        ):
            continue
        findings.append(
            {
                "severity": SEVERITY_ALIASES[match.group(1).lower()],
                "abstract": abstract,
                "reported_category": "",
                "source_format": "severity_line",
            }
        )
    current_section_severity = ""
    for line in output.splitlines():
        section_match = _SEVERITY_SECTION.fullmatch(line)
        if section_match:
            current_section_severity = SEVERITY_ALIASES[
                section_match.group(1).lower()
            ]
            continue
        explicit_match = _NUMBERED_SEVERITY_LINE.fullmatch(line)
        if explicit_match:
            abstract = explicit_match.group(2).strip().strip("*_").strip()
            findings.append(
                {
                    "severity": SEVERITY_ALIASES[
                        explicit_match.group(1).lower()
                    ],
                    "abstract": abstract,
                    "reported_category": "",
                    "source_format": "numbered_severity_line",
                }
            )
            continue
        if line.strip() == "---":
            current_section_severity = ""
            continue
        if line.lstrip().startswith("#") and not line.lstrip().startswith("####"):
            current_section_severity = ""
            continue
        if not current_section_severity:
            continue
        title_match = _SECTION_HEADING_FINDING.fullmatch(line)
        if title_match is None:
            title_match = _SECTION_BOLD_FINDING.fullmatch(line)
        if title_match is None:
            continue
        abstract = title_match.group(1).strip().strip("*_").strip()
        if (
            not abstract
            or _NON_FINDING_ABSTRACT.fullmatch(abstract)
            or _NON_FINDING_PREFIX.match(abstract)
            or _LEADING_SEVERITY_MARKER.match(abstract)
        ):
            continue
        findings.append(
            {
                "severity": current_section_severity,
                "abstract": abstract,
                "reported_category": "",
                "source_format": "severity_section",
            }
        )
    unique_findings = []
    seen_findings: set[tuple[str, str]] = set()
    for finding in findings:
        key = (finding["severity"], finding["abstract"].casefold())
        if key in seen_findings:
            continue
        seen_findings.add(key)
        unique_findings.append(finding)
    findings = unique_findings
    table_counts: dict[str, int] = {}
    for match in _SEVERITY_TABLE_ROW.finditer(output):
        severity = SEVERITY_ALIASES[match.group(1).lower()]
        table_counts[severity] = table_counts.get(severity, 0) + int(
            match.group(2)
        )
    if table_counts:
        observed: dict[str, int] = {}
        for finding in findings:
            severity = finding["severity"]
            observed[severity] = observed.get(severity, 0) + 1
        for severity, declared_count in table_counts.items():
            missing = max(0, declared_count - observed.get(severity, 0))
            findings.extend(
                {
                    "severity": severity,
                    "abstract": f"Review summary reports a {severity} finding",
                    "reported_category": "",
                    "source_format": "severity_table_summary",
                }
                for _ in range(missing)
            )
    if findings:
        return "parsed_findings", findings
    if (
        _CLEAN.search(output)
        or _NO_FINDINGS.search(output)
        or _CLEAN_ASSERTION.search(output)
    ):
        return "parsed_clean", []
    return "unparsed", []


def _assistant_text(record: dict) -> str:
    content = (record.get("message") or {}).get("content") or []
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def parse_claude_candidate(meta_path: pathlib.Path) -> tuple[CandidateRun | None, str]:
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None, "invalid_metadata"
    role = meta.get("agentType") or ""
    if role not in EDITABLE_REVIEWERS:
        return None, "role_not_allowed"
    transcript = meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl"))
    if not transcript.exists():
        return None, "missing_transcript"
    final: dict | None = None
    try:
        for raw in transcript.read_text().splitlines():
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if record.get("type") == "assistant" and _assistant_text(record):
                final = record
    except OSError:
        return None, "unreadable_transcript"
    if final is None:
        return None, "no_final_assistant"
    return (
        CandidateRun(
            provider="claude",
            source_class="claude_editable",
            reviewer_role=role,
            session_id=str(final.get("sessionId") or ""),
            agent_id=str(final.get("agentId") or meta_path.stem),
            final_message_id=str(final.get("uuid") or ""),
            parent_session_id=str(final.get("sessionId") or ""),
            cwd=str(final.get("cwd") or ""),
            branch=str(final.get("gitBranch") or ""),
            timestamp=str(final.get("timestamp") or ""),
            model=str((final.get("message") or {}).get("model") or ""),
            goal=str(meta.get("description") or ""),
            output=_assistant_text(final),
            source_key=str(meta_path),
        ),
        "included",
    )


def parse_codex_candidates(
    rollout_path: pathlib.Path,
) -> tuple[list[CandidateRun], str]:
    try:
        records = [
            json.loads(raw)
            for raw in rollout_path.read_text().splitlines()
            if raw.strip()
        ]
    except (OSError, json.JSONDecodeError):
        return [], "invalid_rollout"
    meta = next(
        (
            record.get("payload") or {}
            for record in records
            if record.get("type") == "session_meta"
        ),
        None,
    )
    if not meta or meta.get("thread_source") != "subagent":
        return [], "not_subagent"
    subagent = ((meta.get("source") or {}).get("subagent") or {})
    if not isinstance(subagent, dict):
        return [], "unknown_subagent_union"
    spawn = subagent.get("thread_spawn")
    model = next(
        (
            str((record.get("payload") or {}).get("model") or "")
            for record in records
            if record.get("type") == "turn_context"
            and (record.get("payload") or {}).get("model")
        ),
        "",
    )
    completions = [
        record
        for record in records
        if record.get("type") == "event_msg"
        and (record.get("payload") or {}).get("type") == "task_complete"
        and (record.get("payload") or {}).get("last_agent_message")
    ]
    if not completions:
        return [], "no_task_complete"
    if subagent.get("other") == "guardian":
        final = completions[-1]
        payload = final.get("payload") or {}
        return (
            [
                CandidateRun(
                    provider="codex",
                    source_class="codex_guardian",
                    reviewer_role="codex-auto-review",
                    session_id=str(meta.get("session_id") or meta.get("id") or ""),
                    agent_id=str(meta.get("id") or rollout_path.stem),
                    final_message_id=str(payload.get("turn_id") or ""),
                    parent_session_id=str(meta.get("parent_thread_id") or ""),
                    cwd=str(meta.get("cwd") or ""),
                    branch="",
                    timestamp=str(
                        final.get("timestamp") or meta.get("timestamp") or ""
                    ),
                    model=model,
                    goal="",
                    output=str(payload.get("last_agent_message") or ""),
                    source_key=str(rollout_path),
                )
            ],
            "included",
        )
    if not isinstance(spawn, dict):
        return [], "unknown_subagent_union"
    role = spawn.get("agent_role") or meta.get("agent_role") or ""
    if role not in EDITABLE_REVIEWERS:
        return [], "role_not_allowed"
    final = completions[-1]
    payload = final.get("payload") or {}
    git = meta.get("git") or {}
    return (
        [
            CandidateRun(
                provider="codex",
                source_class="codex_editable",
                reviewer_role=str(role),
                session_id=str(meta.get("session_id") or meta.get("id") or ""),
                agent_id=str(meta.get("id") or rollout_path.stem),
                final_message_id=str(payload.get("turn_id") or ""),
                parent_session_id=str(
                    meta.get("parent_thread_id")
                    or spawn.get("parent_thread_id")
                    or ""
                ),
                cwd=str(meta.get("cwd") or ""),
                branch=str(git.get("branch") or ""),
                timestamp=str(final.get("timestamp") or meta.get("timestamp") or ""),
                model=model,
                goal="",
                output=str(payload.get("last_agent_message") or ""),
                source_key=str(rollout_path),
            )
        ],
        "included",
    )
