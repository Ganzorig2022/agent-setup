"""Public Stage 0A collection interface."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from collections import Counter
from dataclasses import dataclass

from . import PARSER_VERSION, SCHEMA_VERSION
from .parsers import (
    extract_findings,
    parse_claude_candidate,
    parse_codex_candidates,
    parse_timestamp,
)
from .redact import digest, privacy_violations, redact_text
from .taxonomy import categorize_finding, finding_usability
from .usage import reconcile_usage_logs


@dataclass
class CollectionResult:
    traces: list[dict]
    ledger: list[dict]
    summary: dict


def _apply_parse_gates(traces: list[dict]) -> dict:
    by_class: dict[str, list[dict]] = {}
    for trace in traces:
        by_class.setdefault(trace["source_class"], []).append(trace)
    parse_rates: dict[str, float] = {}
    usable_finding_rates: dict[str, float | None] = {}
    for source_class, records in sorted(by_class.items()):
        parsed = sum(
            trace["parse_status"] in {"parsed_clean", "parsed_findings"}
            for trace in records
        )
        rate = round(parsed / len(records), 3) if records else 0.0
        parse_rates[source_class] = rate
        if rate < 0.90:
            reason = f"{source_class}_parse_rate_below_0.90"
            if source_class == "codex_guardian":
                reason = "guardian_parse_rate_below_0.90"
            for trace in records:
                trace["theme_eligible"] = False
                trace["theme_exclusion_reason"] = reason
        findings = [
            finding
            for trace in records
            for finding in trace.get("findings", [])
        ]
        usable_count = sum(bool(finding.get("usable")) for finding in findings)
        usable_rate = (
            round(usable_count / len(findings), 3) if findings else None
        )
        usable_finding_rates[source_class] = usable_rate
        if (
            source_class.endswith("_editable")
            and (usable_rate is None or usable_rate < 0.90)
        ):
            reason = (
                f"{source_class}_usable_finding_rate_below_0.90"
                if usable_rate is not None
                else f"{source_class}_has_no_findings_to_assess"
            )
            for trace in records:
                trace["theme_eligible"] = False
                trace["theme_exclusion_reason"] = reason
        if source_class == "codex_guardian" and rate >= 0.90:
            for trace in records:
                trace["theme_eligible"] = False
                trace["theme_exclusion_reason"] = (
                    "guardian_session_counts_only"
                )
    guardian_rate = parse_rates.get("codex_guardian")
    editable_rates = [
        rate
        for source_class, rate in parse_rates.items()
        if source_class.endswith("_editable")
    ]
    editable_usable_rates = [
        rate
        for source_class, rate in usable_finding_rates.items()
        if source_class.endswith("_editable")
    ]
    return {
        "parse_rates": parse_rates,
        "usable_finding_rates": usable_finding_rates,
        "guardian_mode": (
            "run_only"
            if guardian_rate is not None
            else "no_data"
        ),
        "editable_parse_gate_passed": bool(editable_rates)
        and all(rate >= 0.90 for rate in editable_rates),
        "editable_usable_gate_passed": bool(editable_usable_rates)
        and all(rate is not None and rate >= 0.90 for rate in editable_usable_rates),
    }


def _run_id(candidate) -> str:
    if candidate.source_class == "codex_guardian":
        guardian_session_id = (
            candidate.parent_session_id or candidate.session_id
        )
        return digest(
            candidate.provider,
            candidate.source_class,
            guardian_session_id,
        )
    return digest(
        candidate.provider,
        candidate.session_id,
        candidate.agent_id,
        candidate.final_message_id,
    )


def _trace(candidate, *, salt: bytes) -> dict:
    run_id = _run_id(candidate)
    normalized_session_id = candidate.session_id
    if candidate.source_class == "codex_guardian":
        normalized_session_id = (
            candidate.parent_session_id or candidate.session_id
        )
    parse_status, raw_findings = extract_findings(candidate.output)
    findings = []
    for index, finding in enumerate(raw_findings):
        source_format = str(finding.get("source_format") or "unknown")
        category = str(finding.get("reported_category") or "")
        if not category:
            category = categorize_finding(finding["abstract"])
        abstract = redact_text(finding["abstract"])
        if privacy_violations(
            {"findings": [{"abstract": abstract}]}
        ):
            abstract = "[sensitive finding removed]"
        usable, unusable_reason = finding_usability(
            abstract=abstract,
            category=category,
            source_format=source_format,
        )
        findings.append(
            {
                "finding_id": digest(
                    run_id,
                    PARSER_VERSION,
                    str(index),
                    abstract,
                ),
                "severity": finding["severity"],
                "abstract": abstract,
                "reported_category": category,
                "source_format": source_format,
                "usable": usable,
                "unusable_reason": unusable_reason,
            }
        )
    severity_counts: dict[str, int] = {}
    for finding in findings:
        severity = finding["severity"]
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "record_id": digest(run_id, PARSER_VERSION),
        "run_id": run_id,
        "provider": candidate.provider,
        "source_class": candidate.source_class,
        "reviewer_role": candidate.reviewer_role,
        "session_hash": digest(normalized_session_id, salt=salt),
        "parent_session_hash": digest(candidate.parent_session_id, salt=salt),
        "repo_hash": digest(candidate.cwd, salt=salt),
        "branch_hash": digest(candidate.branch, salt=salt),
        "timestamp": candidate.timestamp,
        "model": redact_text(candidate.model, limit=80),
        # Free-form task descriptions proved too identifying in the first
        # real-data inspection and are not required for Stage 0A accounting.
        "goal_abstract": "",
        "parse_status": parse_status,
        "finding_count": len(findings),
        "severity_counts": severity_counts,
        "theme_eligible": parse_status == "parsed_findings"
        and any(finding["usable"] for finding in findings),
        "findings": findings,
    }


def collect_review_traces(
    *,
    home: pathlib.Path,
    since_days: int,
    now: dt.datetime,
    salt: bytes,
) -> CollectionResult:
    if not 1 <= since_days <= 30:
        raise ValueError("since_days must be between 1 and 30")
    cutoff = now.astimezone(dt.timezone.utc) - dt.timedelta(days=since_days)
    traces: list[dict] = []
    ledger: list[dict] = []
    claude_source_ids: set[str] = set()
    codex_editable_source_ids: set[str] = set()
    guardian_rollout_count = 0
    guardian_session_ids: set[str] = set()
    pattern = ".claude/projects/*/*/subagents/*.meta.json"
    for meta_path in sorted(home.glob(pattern)):
        candidate, reason = parse_claude_candidate(meta_path)
        source_hash = digest(str(meta_path), salt=salt)
        if candidate is None:
            ledger.append(
                {
                    "provider": "claude",
                    "source_hash": source_hash,
                    "status": "skipped",
                    "reason": reason,
                }
            )
            continue
        timestamp = parse_timestamp(candidate.timestamp)
        if timestamp is None:
            ledger.append(
                {
                    "provider": "claude",
                    "source_hash": source_hash,
                    "status": "skipped",
                    "reason": "invalid_timestamp",
                }
            )
            continue
        if timestamp < cutoff:
            ledger.append(
                {
                    "provider": "claude",
                    "source_hash": source_hash,
                    "run_id": _run_id(candidate),
                    "status": "skipped",
                    "reason": "outside_window",
                }
            )
            continue
        claude_source_ids.add(candidate.agent_id)
        trace = _trace(candidate, salt=salt)
        traces.append(trace)
        ledger.append(
            {
                "provider": "claude",
                "source_hash": source_hash,
                "run_id": trace["run_id"],
                "status": "included",
                "reason": "included",
            }
        )
    codex_pattern = ".codex/sessions/*/*/*/rollout-*.jsonl"
    guardian_candidates: dict[str, list[tuple[dt.datetime, object, str]]] = {}
    for rollout_path in sorted(home.glob(codex_pattern)):
        candidates, reason = parse_codex_candidates(rollout_path)
        source_hash = digest(str(rollout_path), salt=salt)
        if not candidates:
            ledger.append(
                {
                    "provider": "codex",
                    "source_hash": source_hash,
                    "status": "skipped",
                    "reason": reason,
                }
            )
            continue
        for candidate in candidates:
            timestamp = parse_timestamp(candidate.timestamp)
            if timestamp is None:
                ledger.append(
                    {
                        "provider": "codex",
                        "source_hash": source_hash,
                        "run_id": _run_id(candidate),
                        "status": "skipped",
                        "reason": "invalid_timestamp",
                    }
                )
                continue
            if timestamp < cutoff:
                ledger.append(
                    {
                        "provider": "codex",
                        "source_hash": source_hash,
                        "run_id": _run_id(candidate),
                        "status": "skipped",
                        "reason": "outside_window",
                    }
                )
                continue
            if candidate.source_class == "codex_guardian":
                guardian_session_id = (
                    candidate.parent_session_id or candidate.session_id
                )
                guardian_rollout_count += 1
                guardian_session_ids.add(guardian_session_id)
                guardian_candidates.setdefault(
                    guardian_session_id,
                    [],
                ).append((timestamp, candidate, source_hash))
                continue
            codex_editable_source_ids.add(candidate.agent_id)
            trace = _trace(candidate, salt=salt)
            traces.append(trace)
            ledger.append(
                {
                    "provider": "codex",
                    "source_hash": source_hash,
                    "run_id": trace["run_id"],
                    "status": "included",
                    "reason": "included",
                }
            )
    for session_candidates in guardian_candidates.values():
        ordered = sorted(session_candidates, key=lambda item: item[0])
        _, candidate, source_hash = ordered[-1]
        trace = _trace(candidate, salt=salt)
        traces.append(trace)
        ledger.append(
            {
                "provider": "codex",
                "source_hash": source_hash,
                "run_id": trace["run_id"],
                "status": "included",
                "reason": "included",
            }
        )
        for _, duplicate, duplicate_source_hash in ordered[:-1]:
            ledger.append(
                {
                    "provider": "codex",
                    "source_hash": duplicate_source_hash,
                    "run_id": _run_id(duplicate),
                    "status": "skipped",
                    "reason": "duplicate_guardian_session",
                }
            )
    summary = _apply_parse_gates(traces)
    normalized_trace_counts = {
        source_class: sum(
            trace["source_class"] == source_class for trace in traces
        )
        for source_class in (
            "claude_editable",
            "codex_editable",
            "codex_guardian",
        )
    }
    source_counts_match = (
        normalized_trace_counts["claude_editable"] == len(claude_source_ids)
        and normalized_trace_counts["codex_editable"]
        == len(codex_editable_source_ids)
        and normalized_trace_counts["codex_guardian"]
        == len(guardian_session_ids)
    )
    summary["source_reconciliation"] = {
        "status": (
            "exact_source_identity_match"
            if source_counts_match
            else "source_identity_delta"
        ),
        "claude_editable_source_ids": len(claude_source_ids),
        "codex_editable_source_ids": len(codex_editable_source_ids),
        "codex_guardian_rollouts": guardian_rollout_count,
        "codex_guardian_session_ids": len(guardian_session_ids),
        "normalized_trace_counts": normalized_trace_counts,
    }
    trace_by_run_id = {trace["run_id"]: trace for trace in traces}
    for entry in ledger:
        trace = trace_by_run_id.get(entry.get("run_id"))
        if trace is None:
            continue
        if trace["theme_eligible"]:
            entry["theme_status"] = "eligible"
        else:
            entry["theme_status"] = "excluded"
            entry["theme_exclusion_reason"] = trace.get(
                "theme_exclusion_reason",
                "unparsed",
            )
    privacy_findings = [
        {
            "record_id": trace["record_id"],
            "violations": privacy_violations(trace),
        }
        for trace in traces
        if privacy_violations(trace)
    ]
    summary.update(
        discovered_runs=len(traces),
        included_ledger_records=sum(
            entry["status"] == "included" for entry in ledger
        ),
        skipped_ledger_records=sum(
            entry["status"] == "skipped" for entry in ledger
        ),
        privacy_gate_passed=not privacy_findings,
        privacy_violations=privacy_findings,
    )
    summary["usage_reconciliation"] = reconcile_usage_logs(
        home=home,
        traces=traces,
        cutoff_date=cutoff.date(),
    )
    summary["ledger_accounted"] = (
        summary["included_ledger_records"] == len(traces)
    )
    summary["skip_reasons"] = dict(
        sorted(
            Counter(
                entry["reason"]
                for entry in ledger
                if entry["status"] == "skipped"
            ).items()
        )
    )
    summary["stage1_start_gate_passed"] = (
        summary["editable_parse_gate_passed"]
        and summary["editable_usable_gate_passed"]
        and summary["privacy_gate_passed"]
        and summary["ledger_accounted"]
        and summary["source_reconciliation"]["status"]
        == "exact_source_identity_match"
    )
    for entry in ledger:
        entry["schema_version"] = "qri-ledger-v1"
        entry["parser_version"] = PARSER_VERSION
        entry["ledger_id"] = digest(
            entry["provider"],
            entry["source_hash"],
            str(entry.get("run_id") or ""),
            entry["status"],
            entry["reason"],
            PARSER_VERSION,
        )
    return CollectionResult(traces=traces, ledger=ledger, summary=summary)
