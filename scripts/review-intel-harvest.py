#!/usr/bin/env python3
"""Harvest private reviewer traces without analysis, network, or model calls."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib

from review_intel.harvest import collect_review_traces
from review_intel.store import load_or_create_salt, persist_collection


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since-days",
        type=int,
        default=30,
        choices=range(1, 31),
        metavar="1..30",
        help="collection window; capped at Claude's 30-day retention",
    )
    parser.add_argument(
        "--home",
        type=pathlib.Path,
        default=pathlib.Path.home(),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=pathlib.Path.home() / ".review-intelligence",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write an inspection bundle only to an explicitly supplied output dir",
    )
    return parser


def _print_summary(summary: dict, output_dir: pathlib.Path) -> None:
    print(f"inspection_bundle: {output_dir}")
    print(f"traces: {summary['discovered_runs']}")
    print("parse_rates:")
    for source_class, rate in summary["parse_rates"].items():
        print(f"  {source_class}: {rate:.1%}")
    print("usable_finding_rates:")
    for source_class, rate in summary["usable_finding_rates"].items():
        rendered = "n/a" if rate is None else f"{rate:.1%}"
        print(f"  {source_class}: {rendered}")
    print(f"guardian_mode: {summary['guardian_mode']}")
    print(f"privacy_gate_passed: {summary['privacy_gate_passed']}")
    print(f"ledger_accounted: {summary['ledger_accounted']}")
    reconciliation = summary["usage_reconciliation"]
    print(f"usage_reconciliation: {reconciliation['status']}")
    for source_class in reconciliation["trace_counts"]:
        trace_count = reconciliation["trace_counts"][source_class]
        usage_count = reconciliation["usage_log_counts"][source_class]
        delta = reconciliation["deltas_trace_minus_log"][source_class]
        print(
            f"  {source_class}: traces={trace_count} usage_events={usage_count} "
            f"delta={delta:+d}"
        )
    source_reconciliation = summary["source_reconciliation"]
    print(f"source_reconciliation: {source_reconciliation['status']}")
    print(
        "  codex_guardian: "
        f"rollouts={source_reconciliation['codex_guardian_rollouts']} "
        f"sessions={source_reconciliation['codex_guardian_session_ids']}"
    )
    print(f"stage1_start_gate_passed: {summary['stage1_start_gate_passed']}")


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    default_output = (pathlib.Path.home() / ".review-intelligence").resolve()
    requested_output = args.output_dir.expanduser().resolve()
    if args.dry_run and requested_output == default_output:
        parser.error("--dry-run requires an explicit non-default --output-dir")
    salt = load_or_create_salt(args.output_dir)
    result = collect_review_traces(
        home=args.home.expanduser(),
        since_days=args.since_days,
        now=dt.datetime.now(dt.timezone.utc),
        salt=salt,
    )
    persist_collection(result, args.output_dir)
    _print_summary(result.summary, args.output_dir.expanduser().resolve())
    if result.summary["privacy_violations"]:
        print(json.dumps(result.summary["privacy_violations"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
