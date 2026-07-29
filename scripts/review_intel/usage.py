"""Advisory completeness cross-check against existing usage logs."""

from __future__ import annotations

import collections
import datetime as dt
import pathlib
import re


_DATED_LINE = re.compile(r"^(20\d\d-\d\d-\d\d)\s+.*?◇\s+(.+)$")
_ROLE_PREFIXES = {
    "code-review": "code-reviewer",
    "typescript-review": "typescript-reviewer",
    "react-review": "react-reviewer",
    "flutter-review": "flutter-reviewer",
    "security-review": "security-reviewer",
    "database-review": "database-reviewer",
    "silent-failure": "silent-failure-hunter",
}


def _date_and_label(line: str) -> tuple[dt.date, str] | None:
    match = _DATED_LINE.match(line)
    if not match:
        return None
    try:
        date = dt.date.fromisoformat(match.group(1))
    except ValueError:
        return None
    return date, match.group(2).lower()


def _editable_role(label: str) -> str | None:
    normalized = re.sub(r"[_\s]+", "-", label)
    for prefix, role in _ROLE_PREFIXES.items():
        if prefix in normalized:
            return role
    return None


def _usage_counts(
    path: pathlib.Path,
    *,
    provider: str,
    cutoff_date: dt.date,
) -> collections.Counter[str]:
    counts: collections.Counter[str] = collections.Counter()
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return counts
    for line in lines:
        parsed = _date_and_label(line)
        if not parsed:
            continue
        date, label = parsed
        if date < cutoff_date:
            continue
        if provider == "codex" and "codex-auto-review" in label:
            counts["codex_guardian"] += 1
        elif _editable_role(label):
            counts[f"{provider}_editable"] += 1
    return counts


def reconcile_usage_logs(
    *,
    home: pathlib.Path,
    traces: list[dict],
    cutoff_date: dt.date,
) -> dict:
    usage = _usage_counts(
        home / ".claude/hooks/subagent-usage.log",
        provider="claude",
        cutoff_date=cutoff_date,
    )
    usage.update(
        _usage_counts(
            home / ".codex/log/subagent-usage.log",
            provider="codex",
            cutoff_date=cutoff_date,
        )
    )
    observed = collections.Counter(
        str(trace.get("source_class") or "") for trace in traces
    )
    classes = sorted(set(usage) | set(observed))
    deltas = {
        source_class: observed[source_class] - usage[source_class]
        for source_class in classes
    }
    event_surplus = {
        source_class: max(
            0,
            usage[source_class] - observed[source_class],
        )
        for source_class in classes
    }
    return {
        "status": (
            "exact_count_match"
            if all(delta == 0 for delta in deltas.values())
            else "count_delta_requires_explanation"
        ),
        "trace_counts": {
            source_class: observed[source_class] for source_class in classes
        },
        "usage_log_counts": {
            source_class: usage[source_class] for source_class in classes
        },
        "deltas_trace_minus_log": deltas,
        "usage_event_surplus_vs_traces": event_surplus,
        "comparison_unit": "normalized_trace_runs_vs_usage_log_events",
        "interpretation": (
            "Codex notify telemetry records cumulative token snapshots whenever "
            "a rollout changes; repeated events are not additional reviewer runs"
        ),
        "limitation": (
            "usage logs contain no stable run IDs and Codex may emit repeated "
            "cumulative events for one long-lived subagent; reconciliation is "
            "an advisory count cross-check, not a one-to-one join"
        ),
    }
