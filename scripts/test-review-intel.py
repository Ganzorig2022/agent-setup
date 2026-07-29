#!/usr/bin/env python3
"""Behavior tests for the review-intelligence Stage 0A harvester."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
from copy import deepcopy

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from review_intel.harvest import collect_review_traces
from review_intel.parsers import extract_findings, parse_codex_candidates
from review_intel.redact import privacy_violations, redact_text
from review_intel.store import load_or_create_salt, persist_collection
from review_intel.taxonomy import categorize_finding, finding_usability
from review_intel.usage import reconcile_usage_logs


NOW = dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.timezone.utc)
SALT = b"test-salt"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures/review-intel"


def _write_claude_review(
    home: pathlib.Path,
    *,
    index: int,
    output: str,
) -> None:
    subagents = home / ".claude/projects/project/session/subagents"
    subagents.mkdir(parents=True, exist_ok=True)
    agent_id = f"gate-claude-{index}"
    (subagents / f"agent-{agent_id}.meta.json").write_text(
        json.dumps({"agentType": "code-reviewer", "description": "Review"})
    )
    (subagents / f"agent-{agent_id}.jsonl").write_text(
        json.dumps(
            {
                "type": "assistant",
                "uuid": f"gate-message-{index}",
                "sessionId": "gate-claude-session",
                "agentId": agent_id,
                "timestamp": "2026-07-29T11:00:00Z",
                "message": {"content": [{"type": "text", "text": output}]},
            }
        )
        + "\n"
    )


def _write_codex_review(
    home: pathlib.Path,
    *,
    index: int,
    output: str,
) -> None:
    sessions = home / ".codex/sessions/2026/07/29"
    sessions.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "timestamp": "2026-07-29T10:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": f"gate-codex-session-{index}",
                "session_id": f"gate-codex-session-{index}",
                "parent_thread_id": "gate-codex-parent",
                "cwd": "/Users/dev/QPay/web",
                "source": {
                    "subagent": {
                        "thread_spawn": {
                            "agent_role": "code-reviewer",
                            "parent_thread_id": "gate-codex-parent",
                        }
                    }
                },
                "thread_source": "subagent",
            },
        },
        {
            "timestamp": "2026-07-29T10:01:00Z",
            "type": "event_msg",
            "payload": {
                "type": "task_complete",
                "turn_id": f"gate-turn-{index}",
                "last_agent_message": output,
            },
        },
    ]
    (sessions / f"rollout-gate-{index}.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n"
    )


class ReviewIntelTests(unittest.TestCase):
    def test_extracts_structured_qri_v1_findings(self) -> None:
        output = """Human-readable review.

```qri-v1
[{"severity":"HIGH","category":"race-idempotency","abstract":"Retry can create a duplicate settlement row","file":"settlement.js"}]
```
"""

        status, findings = extract_findings(output)

        self.assertEqual(status, "parsed_findings")
        self.assertEqual(
            findings,
            [
                {
                    "severity": "high",
                    "abstract": "Retry can create a duplicate settlement row",
                    "reported_category": "race-idempotency",
                    "source_format": "qri-v1",
                }
            ],
        )

    def test_qri_v1_rejects_a_finding_without_file(self) -> None:
        output = """```qri-v1
[{"severity":"HIGH","category":"race-idempotency","abstract":"Retry can create a duplicate settlement row"}]
```"""

        self.assertEqual(extract_findings(output), ("unparsed", []))

    def test_qri_v1_rejects_extra_finding_fields(self) -> None:
        output = """```qri-v1
[{"severity":"LOW","category":"test-eval","abstract":"Trailer includes a field outside the contract","file":"review.py","line":42}]
```"""

        self.assertEqual(extract_findings(output), ("unparsed", []))

    def test_qri_v1_rejects_categories_outside_the_contract(self) -> None:
        output = """```qri-v1
[{"severity":"MEDIUM","category":"made-up-category","abstract":"Finding uses an unsupported category value","file":"review.py"}]
```"""

        self.assertEqual(extract_findings(output), ("unparsed", []))

    def test_qri_v1_rejects_an_empty_file_value(self) -> None:
        output = """```qri-v1
[{"severity":"LOW","category":"test-eval","abstract":"Finding has no usable file location","file":""}]
```"""

        self.assertEqual(extract_findings(output), ("unparsed", []))

    def test_qri_v1_rejects_non_canonical_severity_aliases(self) -> None:
        output = """```qri-v1
[{"severity":"MAJOR","category":"test-eval","abstract":"Finding uses an unsupported severity alias","file":"review.py"}]
```"""

        self.assertEqual(extract_findings(output), ("unparsed", []))

    def test_qri_v1_rejects_unsafe_file_values(self) -> None:
        for file_value in (
            "/Users/dev/project/review.py",
            "../review.py",
            "src/../review.py",
            "https://example.invalid/review.py",
            "~/review.py",
        ):
            output = (
                "```qri-v1\n"
                '[{"severity":"LOW","category":"test-eval",'
                '"abstract":"Finding has an unsafe file location",'
                f'"file":"{file_value}"}}]\n```'
            )

            self.assertEqual(extract_findings(output), ("unparsed", []))

    def test_qri_v1_rejects_short_abstracts(self) -> None:
        output = """```qri-v1
[{"severity":"LOW","category":"test-eval","abstract":"Too short","file":"review.py"}]
```"""

        self.assertEqual(extract_findings(output), ("unparsed", []))

    def test_fixture_corpus_covers_guardian_unparsed_and_redaction(self) -> None:
        guardian, reason = parse_codex_candidates(
            FIXTURES / "codex/guardian-union.jsonl"
        )
        self.assertEqual(reason, "included")
        self.assertEqual(len(guardian), 1)
        unparsed = (FIXTURES / "unparsed-format.txt").read_text()
        self.assertEqual(extract_findings(unparsed), ("unparsed", []))
        adversarial = (FIXTURES / "adversarial-redaction.txt").read_text()
        self.assertEqual(
            privacy_violations(
                {"goal_abstract": redact_text(adversarial, limit=500)}
            ),
            [],
        )
        candidates, reason = parse_codex_candidates(
            FIXTURES / "codex/string-union.jsonl"
        )
        self.assertEqual(candidates, [])
        self.assertEqual(reason, "unknown_subagent_union")

    def test_collects_claude_reviewer_as_versioned_private_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            subagents = (
                home
                / ".claude/projects/-Users-dev-QPay/sample-session/subagents"
            )
            subagents.mkdir(parents=True)
            meta = subagents / "agent-a1.meta.json"
            meta.write_text(
                json.dumps(
                    {
                        "agentType": "code-reviewer",
                        "description": "Review payment_settlements in /Users/dev/QPay/api",
                    }
                )
            )
            transcript = subagents / "agent-a1.jsonl"
            transcript.write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "message-1",
                        "sessionId": "session-1",
                        "agentId": "a1",
                        "cwd": "/Users/dev/QPay/api",
                        "gitBranch": "feature/internal-ticket",
                        "timestamp": "2026-07-29T11:00:00Z",
                        "message": {
                            "model": "claude-sonnet",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "[HIGH] src/payments.js:42 accepts payment_settlements "
                                        "without validation."
                                    ),
                                }
                            ],
                        },
                    }
                )
                + "\n"
            )

            result = collect_review_traces(
                home=home,
                since_days=30,
                now=NOW,
                salt=SALT,
            )

            self.assertEqual(len(result.traces), 1)
            trace = result.traces[0]
            self.assertEqual(trace["schema_version"], "qri-trace-v2")
            self.assertTrue(trace["parser_version"])
            self.assertEqual(trace["provider"], "claude")
            self.assertEqual(trace["source_class"], "claude_editable")
            self.assertEqual(trace["reviewer_role"], "code-reviewer")
            self.assertEqual(trace["parse_status"], "parsed_findings")
            self.assertEqual(trace["finding_count"], 1)
            self.assertEqual(trace["goal_abstract"], "")
            serialized = json.dumps(trace)
            self.assertNotIn("QPay", serialized)
            self.assertNotIn("payment_settlements", serialized)
            self.assertNotIn("/Users/", serialized)
            self.assertNotIn("feature/internal-ticket", serialized)

    def test_stage1_gate_ignores_pre_trailer_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            subagents = home / ".claude/projects/project/session/subagents"
            subagents.mkdir(parents=True)
            for index in range(20):
                agent_id = f"legacy-{index}"
                (subagents / f"agent-{agent_id}.meta.json").write_text(
                    json.dumps(
                        {
                            "agentType": "code-reviewer",
                            "description": "Review",
                        }
                    )
                )
                (subagents / f"agent-{agent_id}.jsonl").write_text(
                    json.dumps(
                        {
                            "type": "assistant",
                            "uuid": f"message-{index}",
                            "sessionId": "legacy-session",
                            "agentId": agent_id,
                            "timestamp": "2026-07-29T11:00:00Z",
                            "message": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": (
                                            "[HIGH] Missing route validation "
                                            "allows unsafe request input."
                                        ),
                                    }
                                ]
                            },
                        }
                    )
                    + "\n"
                )

            result = collect_review_traces(
                home=home, since_days=30, now=NOW, salt=SALT
            )

            self.assertEqual(
                result.summary["post_trailer_editable_runs"],
                0,
            )
            self.assertEqual(
                result.summary["post_trailer_runs_by_class"],
                {"claude_editable": 0, "codex_editable": 0},
            )
            self.assertEqual(
                result.summary["post_trailer_parse_gate_states"],
                {
                    "claude_editable": "insufficient_evidence",
                    "codex_editable": "insufficient_evidence",
                },
            )
            self.assertEqual(
                result.summary["post_trailer_usable_gate_states"],
                {
                    "claude_editable": "insufficient_evidence",
                    "codex_editable": "insufficient_evidence",
                },
            )
            self.assertEqual(
                result.summary["post_trailer_gate_minimum_evidence_runs"],
                5,
            )
            self.assertNotIn(
                "post_trailer_parse_gate_passed",
                result.summary,
            )
            self.assertNotIn(
                "post_trailer_usable_gate_passed",
                result.summary,
            )
            self.assertFalse(result.summary["stage1_start_gate_passed"])

    def test_clean_codex_runs_are_parse_evidence_but_not_usable_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            sessions = home / ".codex/sessions/2026/07/29"
            sessions.mkdir(parents=True)
            for index in range(5):
                records = [
                    {
                        "timestamp": "2026-07-29T10:00:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": f"codex-session-clean-{index}",
                            "session_id": f"codex-session-clean-{index}",
                            "parent_thread_id": "parent-clean",
                            "cwd": "/Users/dev/QPay/web",
                            "source": {
                                "subagent": {
                                    "thread_spawn": {
                                        "agent_role": "code-reviewer",
                                        "parent_thread_id": "parent-clean",
                                    }
                                }
                            },
                            "thread_source": "subagent",
                        },
                    },
                    {
                        "timestamp": "2026-07-29T10:01:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "task_complete",
                            "turn_id": f"turn-clean-{index}",
                            "last_agent_message": (
                                "No findings.\n\n```qri-v1\n[]\n```"
                            ),
                        },
                    },
                ]
                (sessions / f"rollout-clean-{index}.jsonl").write_text(
                    "\n".join(json.dumps(record) for record in records) + "\n"
                )

            result = collect_review_traces(
                home=home,
                since_days=30,
                now=NOW,
                salt=SALT,
            )

            self.assertEqual(
                result.summary["post_trailer_runs_by_class"],
                {"claude_editable": 0, "codex_editable": 5},
            )
            self.assertEqual(
                result.summary[
                    "post_trailer_finding_bearing_runs_by_class"
                ],
                {"claude_editable": 0, "codex_editable": 0},
            )
            self.assertEqual(
                result.summary["post_trailer_parse_gate_states"],
                {
                    "claude_editable": "insufficient_evidence",
                    "codex_editable": "passed",
                },
            )
            self.assertEqual(
                result.summary["post_trailer_usable_gate_states"],
                {
                    "claude_editable": "insufficient_evidence",
                    "codex_editable": "insufficient_evidence",
                },
            )
            self.assertEqual(
                result.summary["stage1_start_gate_blockers"],
                [
                    {
                        "gate": "post_trailer_editable_runs",
                        "state": "insufficient_evidence",
                        "qualifying_runs": 5,
                        "minimum_qualifying_runs": 20,
                    },
                    {
                        "gate": "parse",
                        "source_class": "claude_editable",
                        "state": "insufficient_evidence",
                        "qualifying_runs": 0,
                        "minimum_qualifying_runs": 5,
                        "rate": None,
                    },
                    {
                        "gate": "usable_finding",
                        "source_class": "claude_editable",
                        "state": "insufficient_evidence",
                        "qualifying_runs": 0,
                        "minimum_qualifying_runs": 5,
                        "rate": None,
                    },
                    {
                        "gate": "usable_finding",
                        "source_class": "codex_editable",
                        "state": "insufficient_evidence",
                        "qualifying_runs": 0,
                        "minimum_qualifying_runs": 5,
                        "rate": None,
                    },
                ],
            )
            self.assertFalse(result.summary["stage1_start_gate_passed"])

    def test_stage1_gate_uses_only_post_trailer_quality_rates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            trailer = (
                "Human review.\n\n```qri-v1\n"
                '[{"severity":"HIGH","category":"validation",'
                '"abstract":"Missing route validation allows unsafe request input",'
                '"file":"route.js"}]\n```'
            )
            for index in range(10):
                _write_claude_review(home, index=index, output=trailer)
                _write_codex_review(home, index=index, output=trailer)
            for index in range(5):
                _write_claude_review(
                    home,
                    index=100 + index,
                    output="Unstructured legacy prose.",
                )

            result = collect_review_traces(
                home=home, since_days=30, now=NOW, salt=SALT
            )

            self.assertEqual(
                result.summary["post_trailer_editable_runs"],
                20,
            )
            self.assertEqual(
                result.summary["post_trailer_runs_by_class"],
                {"claude_editable": 10, "codex_editable": 10},
            )
            self.assertEqual(
                result.summary[
                    "post_trailer_finding_bearing_runs_by_class"
                ],
                {"claude_editable": 10, "codex_editable": 10},
            )
            self.assertEqual(
                result.summary["post_trailer_parse_rates"],
                {"claude_editable": 1.0, "codex_editable": 1.0},
            )
            self.assertEqual(
                result.summary["post_trailer_usable_finding_rates"],
                {"claude_editable": 1.0, "codex_editable": 1.0},
            )
            self.assertEqual(
                result.summary["advisory_lifetime_parse_rates"],
                {"claude_editable": 0.667, "codex_editable": 1.0},
            )
            self.assertEqual(
                result.summary["advisory_lifetime_usable_finding_rates"],
                {"claude_editable": 1.0, "codex_editable": 1.0},
            )
            self.assertEqual(
                result.summary["post_trailer_parse_gate_states"],
                {"claude_editable": "passed", "codex_editable": "passed"},
            )
            self.assertEqual(
                result.summary["post_trailer_usable_gate_states"],
                {"claude_editable": "passed", "codex_editable": "passed"},
            )
            self.assertNotIn("parse_rates", result.summary)
            self.assertNotIn("usable_finding_rates", result.summary)
            self.assertNotIn("editable_parse_gate_passed", result.summary)
            self.assertNotIn("editable_usable_gate_passed", result.summary)
            self.assertNotIn(
                "post_trailer_parse_gate_passed",
                result.summary,
            )
            self.assertNotIn(
                "post_trailer_usable_gate_passed",
                result.summary,
            )
            self.assertEqual(
                result.summary["stage1_start_gate_blockers"],
                [],
            )
            self.assertTrue(result.summary["stage1_start_gate_passed"])

    def test_post_trailer_gate_reports_measured_failures_per_class(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            usable = (
                "```qri-v1\n"
                '[{"severity":"HIGH","category":"validation",'
                '"abstract":"Missing route validation allows unsafe request input",'
                '"file":"route.js"}]\n```'
            )
            unusable = (
                "```qri-v1\n"
                '[{"severity":"LOW","category":"test-eval",'
                '"abstract":"This is informational and not a bug",'
                '"file":"review.js"}]\n```'
            )
            malformed = "```qri-v1\nnot-json\n```"
            outputs = [usable, usable, usable, usable, unusable, malformed]
            for index, output in enumerate(outputs):
                _write_claude_review(home, index=index, output=output)
                _write_codex_review(home, index=index, output=output)

            result = collect_review_traces(
                home=home,
                since_days=30,
                now=NOW,
                salt=SALT,
            )

            self.assertEqual(
                result.summary["post_trailer_runs_by_class"],
                {"claude_editable": 6, "codex_editable": 6},
            )
            self.assertEqual(
                result.summary[
                    "post_trailer_finding_bearing_runs_by_class"
                ],
                {"claude_editable": 5, "codex_editable": 5},
            )
            self.assertEqual(
                result.summary["post_trailer_parse_gate_states"],
                {"claude_editable": "failed", "codex_editable": "failed"},
            )
            self.assertEqual(
                result.summary["post_trailer_usable_gate_states"],
                {"claude_editable": "failed", "codex_editable": "failed"},
            )
            self.assertFalse(result.summary["stage1_start_gate_passed"])

    def test_under_minimum_evidence_never_reports_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            unusable = (
                "```qri-v1\n"
                '[{"severity":"LOW","category":"test-eval",'
                '"abstract":"This is informational and not a bug",'
                '"file":"review.js"}]\n```'
            )
            for index in range(4):
                _write_claude_review(home, index=index, output=unusable)

            result = collect_review_traces(
                home=home,
                since_days=30,
                now=NOW,
                salt=SALT,
            )

            self.assertEqual(
                result.summary["post_trailer_usable_finding_rates"],
                {"claude_editable": 0.0},
            )
            self.assertEqual(
                result.summary["post_trailer_parse_gate_states"][
                    "claude_editable"
                ],
                "insufficient_evidence",
            )
            self.assertEqual(
                result.summary["post_trailer_usable_gate_states"][
                    "claude_editable"
                ],
                "insufficient_evidence",
            )

    def test_usable_finding_rate_requires_category_and_substantive_abstract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            subagents = home / ".claude/projects/project/session/subagents"
            subagents.mkdir(parents=True)
            (subagents / "agent-a1.meta.json").write_text(
                json.dumps(
                    {"agentType": "code-reviewer", "description": "Review"}
                )
            )
            (subagents / "agent-a1.jsonl").write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "message-1",
                        "sessionId": "session-1",
                        "agentId": "a1",
                        "timestamp": "2026-07-29T11:00:00Z",
                        "message": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "[HIGH] Missing route validation allows "
                                        "unsafe request input.\n"
                                        "[LOW] Crash"
                                    ),
                                }
                            ]
                        },
                    }
                )
                + "\n"
            )

            result = collect_review_traces(
                home=home, since_days=30, now=NOW, salt=SALT
            )

            findings = result.traces[0]["findings"]
            self.assertEqual(findings[0]["reported_category"], "validation")
            self.assertTrue(findings[0]["usable"])
            self.assertFalse(findings[1]["usable"])
            self.assertEqual(
                result.summary[
                    "advisory_lifetime_usable_finding_rates"
                ]["claude_editable"],
                0.5,
            )
            self.assertFalse(result.traces[0]["theme_eligible"])
            self.assertEqual(
                result.traces[0]["theme_exclusion_reason"],
                "claude_editable_usable_finding_rate_below_0.90",
            )

    def test_taxonomy_covers_observed_reviewer_defect_language(self) -> None:
        examples = {
            "Off-screen logo likely never loads": "ui-correctness",
            "No database audit trail for rejected payments": "data-integrity",
            "Silent escalation write failure": "error-handling",
            "Substring matching creates false escalations": "matching-correctness",
            "All-or-nothing embedding failure in seeder": "data-integrity",
            "Weekly generation is lost during offline runs": "delivery-reliability",
            "Scanning only applies when explicitly enabled": "feature-gating",
            "Inconsistent escalation recording across channels": "data-integrity",
            "Same typo in the regex letter class": "matching-correctness",
            "New shape is narrower and may reject legacy data": "compatibility",
            "Guardian dedupe uses child identity instead of parent identity": (
                "race-idempotency"
            ),
            "Bytecode embeds local absolute source paths": "secret-exposure",
        }

        self.assertEqual(
            {text: categorize_finding(text) for text in examples},
            examples,
        )

    def test_informational_or_dismissed_mentions_are_not_usable_findings(self) -> None:
        for abstract in (
            "Representation change is informational, not a bug",
            "Convention is pre-existing and not introduced by this diff",
        ):
            usable, reason = finding_usability(
                abstract=abstract,
                category="type-safety",
                source_format="severity_line",
            )
            self.assertFalse(usable)
            self.assertEqual(reason, "dismissed-or-informational")

    def test_filename_redaction_does_not_leave_extension_suffixes(self) -> None:
        redacted = redact_text(
            "Using --save-baseline silently corrupts baseline.json on disk"
        )
        self.assertEqual(
            redacted,
            "Using --[identifier] silently corrupts [file] on disk",
        )

    def test_collects_codex_thread_spawn_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            sessions = home / ".codex/sessions/2026/07/29"
            sessions.mkdir(parents=True)
            rollout = sessions / "rollout-review.jsonl"
            records = [
                {
                    "timestamp": "2026-07-29T10:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "codex-session-1",
                        "session_id": "codex-session-1",
                        "parent_thread_id": "parent-1",
                        "cwd": "/Users/dev/QPay/web",
                        "source": {
                            "subagent": {
                                "thread_spawn": {
                                    "agent_role": "typescript-reviewer",
                                    "parent_thread_id": "parent-1",
                                }
                            }
                        },
                        "thread_source": "subagent",
                    },
                },
                {
                    "timestamp": "2026-07-29T10:01:00Z",
                    "type": "turn_context",
                    "payload": {"model": "gpt-test"},
                },
                {
                    "timestamp": "2026-07-29T10:02:00Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "turn_id": "turn-1",
                        "last_agent_message": (
                            "### MEDIUM — src/orders.ts:8 mutates order_items directly."
                        ),
                    },
                },
            ]
            rollout.write_text("\n".join(json.dumps(record) for record in records) + "\n")

            result = collect_review_traces(
                home=home,
                since_days=30,
                now=NOW,
                salt=SALT,
            )

            self.assertEqual(len(result.traces), 1)
            trace = result.traces[0]
            self.assertEqual(trace["provider"], "codex")
            self.assertEqual(trace["source_class"], "codex_editable")
            self.assertEqual(trace["reviewer_role"], "typescript-reviewer")
            self.assertEqual(trace["parse_status"], "parsed_findings")
            self.assertNotIn("order_items", json.dumps(trace))

    def test_collapses_codex_guardian_union_to_session_level(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            sessions = home / ".codex/sessions/2026/07/29"
            sessions.mkdir(parents=True)
            rollout = sessions / "rollout-guardian.jsonl"
            records = [
                {
                    "timestamp": "2026-07-29T09:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "guardian-session",
                        "session_id": "guardian-session",
                        "parent_thread_id": "guardian-parent",
                        "cwd": "/Users/dev/QPay/service",
                        "source": {"subagent": {"other": "guardian"}},
                        "thread_source": "subagent",
                    },
                },
                {
                    "timestamp": "2026-07-29T09:01:00Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "turn_id": "guardian-turn-1",
                        "last_agent_message": "PASS — no verified findings.",
                    },
                },
                {
                    "timestamp": "2026-07-29T09:02:00Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "turn_id": "guardian-turn-2",
                        "last_agent_message": (
                            "[BLOCKER] src/auth.js:10 exposes customer_secrets."
                        ),
                    },
                },
            ]
            rollout.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            duplicate_rollout = sessions / "rollout-guardian-duplicate.jsonl"
            duplicate_records = [
                {
                    "timestamp": "2026-07-29T08:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "guardian-rollout-2",
                        "session_id": "different-child-session",
                        "parent_thread_id": "guardian-parent",
                        "cwd": "/Users/dev/QPay/service",
                        "source": {"subagent": {"other": "guardian"}},
                        "thread_source": "subagent",
                    },
                },
                {
                    "timestamp": "2026-07-29T08:01:00Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "turn_id": "guardian-duplicate-turn",
                        "last_agent_message": "No verified findings.",
                    },
                },
            ]
            duplicate_rollout.write_text(
                "\n".join(json.dumps(record) for record in duplicate_records)
                + "\n"
            )

            result = collect_review_traces(
                home=home,
                since_days=30,
                now=NOW,
                salt=SALT,
            )

            self.assertEqual(len(result.traces), 1)
            self.assertEqual(
                {trace["source_class"] for trace in result.traces},
                {"codex_guardian"},
            )
            self.assertEqual(
                result.traces[0]["session_hash"],
                result.traces[0]["parent_session_hash"],
            )
            self.assertEqual(
                {trace["reviewer_role"] for trace in result.traces},
                {"codex-auto-review"},
            )
            self.assertEqual(
                {trace["parse_status"] for trace in result.traces},
                {"parsed_findings"},
            )
            self.assertEqual(result.summary["guardian_mode"], "run_only")
            self.assertFalse(result.traces[0]["theme_eligible"])
            self.assertEqual(
                result.traces[0]["theme_exclusion_reason"],
                "guardian_session_counts_only",
            )
            self.assertNotIn("customer_secrets", json.dumps(result.traces))
            self.assertEqual(
                sum(
                    entry["reason"] == "duplicate_guardian_session"
                    for entry in result.ledger
                ),
                1,
            )
            self.assertEqual(
                result.summary["source_reconciliation"],
                {
                    "status": "exact_source_identity_match",
                    "claude_editable_source_ids": 0,
                    "codex_editable_source_ids": 0,
                    "codex_guardian_rollouts": 2,
                    "codex_guardian_session_ids": 1,
                    "normalized_trace_counts": {
                        "claude_editable": 0,
                        "codex_editable": 0,
                        "codex_guardian": 1,
                    },
                },
            )

    def test_guardian_below_parse_threshold_is_run_level_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            sessions = home / ".codex/sessions/2026/07/29"
            sessions.mkdir(parents=True)
            rollout = sessions / "rollout-guardian.jsonl"
            records = [
                {
                    "timestamp": "2026-07-29T09:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "guardian-session",
                        "session_id": "guardian-session",
                        "cwd": "/Users/dev/QPay/service",
                        "source": {"subagent": {"other": "guardian"}},
                        "thread_source": "subagent",
                    },
                },
                {
                    "timestamp": "2026-07-29T09:01:00Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "turn_id": "turn-clean",
                        "last_agent_message": "No verified findings.",
                    },
                },
                {
                    "timestamp": "2026-07-29T09:02:00Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "turn_id": "turn-unparsed",
                        "last_agent_message": "Looks reasonable to me.",
                    },
                },
            ]
            rollout.write_text("\n".join(json.dumps(record) for record in records) + "\n")

            result = collect_review_traces(
                home=home,
                since_days=30,
                now=NOW,
                salt=SALT,
            )

            self.assertEqual(
                result.summary["advisory_lifetime_parse_rates"][
                    "codex_guardian"
                ],
                0.0,
            )
            self.assertEqual(result.summary["guardian_mode"], "run_only")
            self.assertTrue(
                all(not trace["theme_eligible"] for trace in result.traces)
            )
            self.assertTrue(
                all(
                    trace["theme_exclusion_reason"]
                    == "guardian_parse_rate_below_0.90"
                    for trace in result.traces
                )
            )
            guardian_ledger = [
                entry for entry in result.ledger if entry.get("run_id")
            ]
            self.assertTrue(
                all(
                    entry["theme_status"] == "excluded"
                    and entry["theme_exclusion_reason"]
                    == "guardian_parse_rate_below_0.90"
                    for entry in guardian_ledger
                )
            )

    def test_persistence_is_idempotent_and_keeps_parser_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            home = root / "home"
            output = root / "private-output"
            subagents = home / ".claude/projects/project/session/subagents"
            subagents.mkdir(parents=True)
            (subagents / "agent-a1.meta.json").write_text(
                json.dumps(
                    {
                        "agentType": "security-reviewer",
                        "description": "Review authentication changes",
                    }
                )
            )
            (subagents / "agent-a1.jsonl").write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "message-1",
                        "sessionId": "session-1",
                        "agentId": "a1",
                        "cwd": "/private/project",
                        "timestamp": "2026-07-29T11:00:00Z",
                        "message": {
                            "model": "test",
                            "content": [
                                {"type": "text", "text": "No verified findings."}
                            ],
                        },
                    }
                )
                + "\n"
            )
            first = collect_review_traces(
                home=home, since_days=30, now=NOW, salt=SALT
            )

            persist_collection(first, output)
            persist_collection(first, output)
            lines = (output / "traces.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)

            revised = deepcopy(first)
            revised.traces[0]["parser_version"] = "future-parser"
            revised.traces[0]["record_id"] = "future-record-id"
            persist_collection(revised, output)
            lines = (output / "traces.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 2)

            (subagents / "agent-a1.meta.json").unlink()
            (subagents / "agent-a1.jsonl").unlink()
            empty = collect_review_traces(
                home=home, since_days=30, now=NOW, salt=SALT
            )
            persist_collection(empty, output)
            self.assertEqual(
                len((output / "traces.jsonl").read_text().splitlines()),
                2,
            )
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertEqual(
                (output / "traces.jsonl").stat().st_mode & 0o777,
                0o600,
            )

    def test_persistence_fails_closed_on_corrupt_existing_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "private-output"
            output.mkdir()
            (output / "traces.jsonl").write_text("{not-json}\n")
            (output / "traces.jsonl").chmod(0o600)
            result = collect_review_traces(
                home=pathlib.Path(tmp),
                since_days=30,
                now=NOW,
                salt=SALT,
            )

            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                persist_collection(result, output)

    def test_persistence_rejects_store_file_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            output = root / "private-output"
            output.mkdir(mode=0o700)
            redirected = root / "redirected.jsonl"
            redirected.write_text("")
            (output / "traces.jsonl").symlink_to(redirected)
            result = collect_review_traces(
                home=root,
                since_days=30,
                now=NOW,
                salt=SALT,
            )

            with self.assertRaisesRegex(ValueError, "symlink"):
                persist_collection(result, output)

    def test_output_fails_closed_in_git_or_cloud_paths_and_salt_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo"
            (repo / ".git").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "git worktree"):
                persist_collection(
                    collect_review_traces(
                        home=root,
                        since_days=30,
                        now=NOW,
                        salt=SALT,
                    ),
                    repo / "review-intelligence",
                )

            cloud = root / "Library/Mobile Documents/review-intelligence"
            with self.assertRaisesRegex(ValueError, "cloud-synced"):
                load_or_create_salt(cloud)

            output = root / "safe-output"
            first = load_or_create_salt(output)
            second = load_or_create_salt(output)
            self.assertEqual(first, second)
            self.assertEqual((output / "salt").stat().st_mode & 0o777, 0o600)

    def test_redaction_removes_adversarial_proprietary_material(self) -> None:
        raw = """
        ```ts
        const bearer = "secret-value";
        ```
        QPay SettlementEngine reads ticket_assignees from
        /Users/dev/QPay/internal/src/settlementEngine.ts:42.
        Contact owner@example.com or https://internal.example/path from 10.0.0.8.
        token=super-secret-value hash abcdef0123456789abcdef0123456789
        `CustomerLedger` and "merchant_private_rule" are affected.
        """
        redacted = redact_text(raw, limit=500)
        for forbidden in (
            "QPay",
            "SettlementEngine",
            "ticket_assignees",
            "/Users/",
            "owner@example.com",
            "internal.example",
            "10.0.0.8",
            "super-secret-value",
            "abcdef0123456789abcdef0123456789",
            "CustomerLedger",
            "merchant_private_rule",
            "MIN_ACTIONABLE_CHARS",
            "console.log",
        ):
            self.assertNotIn(forbidden, redacted)
        self.assertEqual(privacy_violations({"goal_abstract": redacted}), [])

    def test_privacy_scan_rejects_sensitive_trace_values(self) -> None:
        trace = {
            "goal_abstract": "Inspect /Users/dev/QPay/private_api",
            "findings": [{"abstract": "Leaks private_schema_name"}],
        }

        violations = privacy_violations(trace)

        self.assertEqual(
            {violation["field"] for violation in violations},
            {"goal_abstract", "findings.0.abstract"},
        )

    def test_redaction_removes_bearer_and_high_entropy_credentials(self) -> None:
        raw = (
            "Leaks Bearer mnbvcxzlkjhgfdsapoiuytrewq0987654321 and "
            "API key abcdEFGHijklMNOP1234567890qrstuv."
        )
        redacted = redact_text(raw, limit=500)
        self.assertNotIn("mnbvcxz", redacted)
        self.assertNotIn("abcdEFGH", redacted)
        self.assertEqual(
            privacy_violations({"findings": [{"abstract": redacted}]}),
            [],
        )

    def test_redaction_truncates_only_at_token_boundaries(self) -> None:
        redacted = redact_text(
            "alpha beta gamma delta epsilon",
            limit=18,
        )

        self.assertEqual(redacted, "alpha beta gamma…")

    def test_structured_qri_trailer_is_preferred_over_prose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            subagents = home / ".claude/projects/project/session/subagents"
            subagents.mkdir(parents=True)
            (subagents / "agent-a1.meta.json").write_text(
                json.dumps(
                    {
                        "agentType": "code-reviewer",
                        "description": "Review changes",
                    }
                )
            )
            trailer = [
                {
                    "severity": "HIGH",
                    "category": "race-idempotency",
                    "abstract": "CustomerLedger reads invoice_rows before commit",
                    "file": "internal.ts",
                }
            ]
            text = (
                "Free prose without a standard severity heading.\n\n"
                "```qri-v1\n"
                + json.dumps(trailer)
                + "\n```"
            )
            (subagents / "agent-a1.jsonl").write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "message-1",
                        "sessionId": "session-1",
                        "agentId": "a1",
                        "cwd": "/private/repo",
                        "timestamp": "2026-07-29T11:00:00Z",
                        "message": {
                            "model": "test",
                            "content": [{"type": "text", "text": text}],
                        },
                    }
                )
                + "\n"
            )

            result = collect_review_traces(
                home=home, since_days=30, now=NOW, salt=SALT
            )

            finding = result.traces[0]["findings"][0]
            self.assertEqual(finding["severity"], "high")
            self.assertEqual(
                finding["reported_category"],
                "race-idempotency",
            )
            self.assertNotIn("CustomerLedger", json.dumps(finding))

    def test_clean_parser_does_not_treat_incidental_pass_as_clean(self) -> None:
        self.assertEqual(
            extract_findings("The validation does not pass in production."),
            ("unparsed", []),
        )

    def test_clean_parser_recognizes_real_reviewer_approval_variants(self) -> None:
        approvals = (
            "### ✅ APPROVED — No CRITICAL or HIGH issues",
            "## Verdict: Approve — no CRITICAL or HIGH issues",
            "### ✅ PASS — Core Bug Fix is Correct",
            "**PASS** — The diff correctly fixes the reported bug.",
            "**Verdict: APPROVE** — No issues found.",
        )

        self.assertEqual(
            [extract_findings(output)[0] for output in approvals],
            ["parsed_clean"] * len(approvals),
        )

    def test_clean_parser_recognizes_codex_reassessment_variants(self) -> None:
        approvals = (
            "No verified actionable findings in the scoped changes.",
            "No actionable React issues remain in the latest diff.",
            "Findings: none in the scoped TypeScript changes.",
            "Approve for the responsive table change.",
            "Approval: scoped diff approved.",
            "Reassessment: both prior findings are retracted.",
            "Revised verdict: **no code blocker found for this build**.",
        )

        self.assertEqual(
            [extract_findings(output)[0] for output in approvals],
            ["parsed_clean"] * len(approvals),
        )

    def test_markdown_severity_table_preserves_nonzero_finding_counts(self) -> None:
        output = """
        | Severity | Count | Status |
        |----------|-------|--------|
        | CRITICAL | 1     | fail   |
        | MEDIUM   | 1     | warn   |
        | LOW      | 1     | note   |
        """

        status, findings = extract_findings(output)

        self.assertEqual(status, "parsed_findings")
        self.assertEqual(
            [finding["severity"] for finding in findings],
            ["critical", "medium", "low"],
        )
        self.assertTrue(
            all(finding["source_format"] == "severity_table_summary" for finding in findings)
        )

    def test_severity_section_headings_are_not_findings(self) -> None:
        output = """
        ### CRITICAL Issues

        **[CRITICAL] Drill mode can overwrite the committed evaluation baseline**
        **[LOW] / notes (ship-blocking: no)**
        """

        status, findings = extract_findings(output)

        self.assertEqual(status, "parsed_findings")
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0]["abstract"],
            "Drill mode can overwrite the committed evaluation baseline",
        )

    def test_zero_table_rows_and_none_markers_are_not_findings(self) -> None:
        output = """
        | Severity | Count | Status |
        |----------|-------|--------|
        | CRITICAL | 0     | pass   |
        | HIGH     | 0     | pass   |

        ### HIGH
        **None.**

        **CRITICAL:** 0
        **HIGH:** 0

        **Verdict: APPROVE** — No issues found.
        """

        self.assertEqual(extract_findings(output), ("parsed_clean", []))

    def test_section_and_numbered_severity_formats_extract_real_findings(self) -> None:
        output = """
        ## HIGH
        **Incorrect key prop can leak component state**

        ### MEDIUM
        #### 1. Transaction spans external service call
        - **Evidence:** connection remains open

        **2. LOW — Nominal test command is not wired to the new suite**
        """

        status, findings = extract_findings(output)

        self.assertEqual(status, "parsed_findings")
        self.assertEqual(
            [(finding["severity"], finding["abstract"]) for finding in findings],
            [
                ("high", "Incorrect key prop can leak component state"),
                ("medium", "Transaction spans external service call"),
                ("low", "Nominal test command is not wired to the new suite"),
            ],
        )

    def test_outside_window_reviewers_are_explicitly_ledgered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            claude = home / ".claude/projects/project/session/subagents"
            claude.mkdir(parents=True)
            (claude / "agent-old.meta.json").write_text(
                json.dumps(
                    {"agentType": "code-reviewer", "description": "Review"}
                )
            )
            (claude / "agent-old.jsonl").write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "uuid": "old-message",
                        "sessionId": "old-session",
                        "agentId": "old-agent",
                        "timestamp": "2026-06-01T00:00:00Z",
                        "message": {
                            "content": [
                                {"type": "text", "text": "No verified findings."}
                            ]
                        },
                    }
                )
                + "\n"
            )
            codex = home / ".codex/sessions/2026/06/01"
            codex.mkdir(parents=True)
            (codex / "rollout-old.jsonl").write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {
                                    "id": "old-codex",
                                    "session_id": "old-codex",
                                    "thread_source": "subagent",
                                    "source": {
                                        "subagent": {
                                            "thread_spawn": {
                                                "agent_role": "code-reviewer"
                                            }
                                        }
                                    },
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-06-01T00:00:00Z",
                                "type": "event_msg",
                                "payload": {
                                    "type": "task_complete",
                                    "turn_id": "old-turn",
                                    "last_agent_message": "No verified findings.",
                                },
                            }
                        ),
                    )
                )
                + "\n"
            )

            result = collect_review_traces(
                home=home, since_days=30, now=NOW, salt=SALT
            )

            self.assertEqual(result.traces, [])
            outside = [
                entry
                for entry in result.ledger
                if entry["reason"] == "outside_window"
            ]
            self.assertEqual({entry["provider"] for entry in outside}, {"claude", "codex"})

    def test_usage_logs_reconcile_by_provider_source_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            claude_log = home / ".claude/hooks/subagent-usage.log"
            codex_log = home / ".codex/log/subagent-usage.log"
            claude_log.parent.mkdir(parents=True)
            codex_log.parent.mkdir(parents=True)
            claude_log.write_text(
                "2026-07-29 10:00:00 ◇ code-reviewer: Review change — sonnet\n"
            )
            codex_log.write_text(
                "2026-07-29 10:01:00 ◇ typescript reviewer "
                "(typescript-reviewer) — gpt\n"
                "2026-07-29 10:02:00 ◇ subagent — codex-auto-review\n"
            )
            traces = [
                {"source_class": "claude_editable"},
                {"source_class": "codex_editable"},
                {"source_class": "codex_guardian"},
            ]

            result = reconcile_usage_logs(
                home=home,
                traces=traces,
                cutoff_date=dt.date(2026, 6, 29),
            )

            self.assertEqual(
                result["usage_log_counts"],
                {
                    "claude_editable": 1,
                    "codex_editable": 1,
                    "codex_guardian": 1,
                },
            )
            self.assertEqual(result["status"], "exact_count_match")

    def test_codex_usage_surplus_is_labeled_cumulative_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            codex_log = home / ".codex/log/subagent-usage.log"
            codex_log.parent.mkdir(parents=True)
            codex_log.write_text(
                "2026-07-29 10:01:00 ◇ code reviewer "
                "(code-reviewer) — gpt · out 1k\n"
                "2026-07-29 10:02:00 ◇ code reviewer "
                "(code-reviewer) — gpt · out 2k\n"
            )

            result = reconcile_usage_logs(
                home=home,
                traces=[{"source_class": "codex_editable"}],
                cutoff_date=dt.date(2026, 6, 29),
            )

            self.assertEqual(
                result["usage_event_surplus_vs_traces"]["codex_editable"],
                1,
            )
            self.assertIn("cumulative", result["interpretation"])


if __name__ == "__main__":
    unittest.main()
