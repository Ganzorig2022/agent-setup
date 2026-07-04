#!/usr/bin/env python3
"""Zero-token pipe smoke tests for Claude Code hooks.

The tests run each hook as a subprocess, feed canned JSON on stdin, and assert
the hook's exit code plus stdout/stderr shape. Cases that need files use a
fresh temporary HOME and temporary paths only.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOKS = ROOT / "claude" / "hooks"
FIXTURES = pathlib.Path(__file__).resolve().parent / "hook-smoke-fixtures"
TIMEOUT_SECONDS = 8


class SmokeFailure(Exception):
    pass


def fail(message):
    raise SmokeFailure(message)


def read_fixture(name, replacements):
    path = FIXTURES / name
    raw = path.read_text()
    for key, value in replacements.items():
        raw = raw.replace(key, value)
    try:
        json.loads(raw)
    except Exception as exc:
        fail("fixture is not valid JSON after substitution: %s" % exc)
    return raw


def parse_json(text):
    try:
        return json.loads(text)
    except Exception as exc:
        fail("stdout is not valid JSON: %s; stdout=%r" % (exc, text[:200]))


def parse_json_lines(text):
    lines = [line for line in text.splitlines() if line.strip()]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception as exc:
            fail("stdout line is not valid JSON: %s; line=%r" % (exc, line[:200]))
    return out


def expect_rc(res, code):
    if res.returncode != code:
        fail("expected rc=%s, got rc=%s stdout=%r stderr=%r" % (
            code, res.returncode, res.stdout[:200], res.stderr[:200]))


def expect_silent(res, code=0):
    expect_rc(res, code)
    if res.stdout != "" or res.stderr != "":
        fail("expected no output, got stdout=%r stderr=%r" % (
            res.stdout[:200], res.stderr[:200]))


def ensure(condition, message):
    if not condition:
        fail(message)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def setup_noop(ctx):
    return None


def setup_format_temp_file(ctx):
    project = ctx["tmp"] / "project"
    src = project / "src" / "app.js"
    write_text(project / "package.json", "{}\n")
    write_text(src, "const value = 1\n")
    ctx["env"]["CLAUDE_FILE_PATH"] = str(src)
    ctx["replacements"]["__TEMP_FILE__"] = str(src)
    ctx["scratch"]["format_file"] = src


def setup_plan_file(ctx):
    plans = ctx["home"] / ".claude" / "plans"
    old_plan = plans / "old.md"
    new_plan = plans / "approved.md"
    write_text(old_plan, "# Old plan\n")
    write_text(new_plan, "# Approved plan\n")
    now = time.time()
    os.utime(old_plan, (now - 20, now - 20))
    os.utime(new_plan, (now, now))


def setup_one_edit_transcript(ctx):
    transcript = ctx["tmp"] / "transcripts" / "one-edit.jsonl"
    write_text(
        transcript,
        '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit"}]}}\n',
    )
    ctx["replacements"]["__TEMP_TRANSCRIPT__"] = str(transcript)


def setup_two_edit_transcript(ctx):
    transcript = ctx["tmp"] / "transcripts" / "two-edits.jsonl"
    write_text(
        transcript,
        "\n".join([
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit"}]}}',
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Write"}]}}',
            "",
        ]),
    )
    ctx["replacements"]["__TEMP_TRANSCRIPT__"] = str(transcript)


def setup_missing_agent_transcript(ctx):
    ctx["replacements"]["__TEMP_AGENT_TRANSCRIPT__"] = str(
        ctx["tmp"] / "missing" / "agent-smoke.jsonl")


def setup_agent_transcript(ctx):
    transcript = ctx["tmp"] / "subagents" / "agent-smoke.jsonl"
    write_text(
        transcript,
        "\n".join([
            '{"timestamp":"2026-07-04T00:00:00Z","type":"user","message":{"content":"review"}}',
            '{"timestamp":"2026-07-04T00:00:05Z","type":"assistant","message":{"model":"claude-sonnet-4-5-20251001","usage":{"output_tokens":1234,"cache_creation_input_tokens":5,"cache_read_input_tokens":6},"content":[{"type":"tool_use","name":"Read","id":"toolu_1"}]}}',
            "",
        ]),
    )
    write_text(transcript.parent / "agent-smoke.meta.json",
               '{"description":"Review invoices"}\n')
    (ctx["home"] / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    ctx["replacements"]["__TEMP_AGENT_TRANSCRIPT__"] = str(transcript)


def expect_blocked_rm(res, ctx):
    expect_rc(res, 2)
    ensure(res.stdout == "", "expected empty stdout")
    ensure("recursive force delete" in res.stderr, "missing block message")


def expect_plan_no_file(res, ctx):
    expect_rc(res, 0)
    ensure(res.stderr == "", "expected empty stderr")
    data = parse_json(res.stdout)
    out = data.get("hookSpecificOutput", {})
    ensure(out.get("hookEventName") == "PostToolUse", "wrong hook event")
    ctx_text = out.get("additionalContext", "")
    ensure("A plan was just approved" in ctx_text, "missing context text")
    ensure("Approved plan file:" not in ctx_text, "unexpected plan file")


def expect_plan_with_file(res, ctx):
    expect_rc(res, 0)
    ensure(res.stderr == "", "expected empty stderr")
    data = parse_json(res.stdout)
    ctx_text = data.get("hookSpecificOutput", {}).get("additionalContext", "")
    ensure("Approved plan file:" in ctx_text, "missing approved plan pointer")
    ensure(".claude/plans/approved.md" in ctx_text, "wrong approved plan")


def expect_retro_nudge(res, ctx):
    expect_rc(res, 0)
    ensure(res.stderr == "", "expected empty stderr")
    data = parse_json(res.stdout)
    ensure(data.get("suppressOutput") is True, "suppressOutput must be true")
    ensure("systemMessage" in data, "missing systemMessage")
    marker = ctx["home"] / ".claude" / ".cache" / "retro-nudge" / "smoke-two-edits"
    ensure(marker.exists(), "expected temp marker to be written")


def expect_update_memory(res, ctx):
    expect_rc(res, 1)
    ensure(res.stderr == "", "expected empty stderr")
    ensure(res.stdout.startswith("Session ending ("), "missing stop prompt")
    expected = str(ctx["home"] / ".claude" / "agent-memory" / "STATE.md")
    ensure(expected in res.stdout, "prompt used wrong STATE.md path")


def expect_statusline(res, ctx):
    expect_rc(res, 0)
    ensure(res.stderr == "", "expected empty stderr")
    rows = parse_json_lines(res.stdout)
    ensure(len(rows) == 1, "expected one JSON line")
    ensure(rows[0].get("id") == "task-1", "wrong task id")
    ensure(rows[0].get("content") == "Review billing flow (1.5k tok)",
           "wrong statusline content: %r" % rows[0].get("content"))


def expect_usage_missing(res, ctx):
    expect_silent(res, 0)


def expect_usage_summary(res, ctx):
    expect_rc(res, 0)
    ensure(res.stderr == "", "expected empty stderr")
    data = parse_json(res.stdout)
    msg = data.get("systemMessage", "")
    for piece in (
        "code-reviewer: Review invoices",
        "sonnet-4-5",
        "out 1.2k",
        "cache r/w 6/5",
        "1 tools",
        "0m05s",
    ):
        ensure(piece in msg, "missing %r in systemMessage %r" % (piece, msg))
    log_file = ctx["home"] / ".claude" / "hooks" / "subagent-usage.log"
    ensure(log_file.exists(), "expected temp usage log")


CASES = [
    {
        "hook": "block-dangerous.sh",
        "case": "safe-command",
        "fixture": "block-dangerous-safe.json",
        "expect": lambda res, ctx: expect_silent(res, 0),
    },
    {
        "hook": "block-dangerous.sh",
        "case": "rm-rf-blocked",
        "fixture": "block-dangerous-rm-rf.json",
        "expect": expect_blocked_rm,
    },
    {
        "hook": "format-file.sh",
        "case": "missing-file-env",
        "fixture": "format-file-edit.json",
        "expect": lambda res, ctx: expect_silent(res, 0),
    },
    {
        "hook": "format-file.sh",
        "case": "temp-js-no-config",
        "fixture": "format-file-edit.json",
        "setup": setup_format_temp_file,
        "expect": lambda res, ctx: expect_silent(res, 0),
    },
    {
        "hook": "plan-handoff.sh",
        "case": "no-plan-file",
        "fixture": "plan-handoff-exit-plan.json",
        "expect": expect_plan_no_file,
    },
    {
        "hook": "plan-handoff.sh",
        "case": "latest-plan-file",
        "fixture": "plan-handoff-exit-plan.json",
        "setup": setup_plan_file,
        "expect": expect_plan_with_file,
    },
    {
        "hook": "retro-nudge.sh",
        "case": "stop-active-silent",
        "fixture": "retro-nudge-active.json",
        "expect": lambda res, ctx: expect_silent(res, 0),
    },
    {
        "hook": "retro-nudge.sh",
        "case": "one-edit-silent",
        "fixture": "retro-nudge-one-edit.json",
        "setup": setup_one_edit_transcript,
        "expect": lambda res, ctx: expect_silent(res, 0),
    },
    {
        "hook": "retro-nudge.sh",
        "case": "two-edits-nudge",
        "fixture": "retro-nudge-two-edits.json",
        "setup": setup_two_edit_transcript,
        "expect": expect_retro_nudge,
    },
    {
        "hook": "update-memory.sh",
        "case": "stop-prompt",
        "fixture": "update-memory-stop.json",
        "expect": expect_update_memory,
    },
    {
        "hook": "subagent-statusline.py",
        "case": "tasks-array-token-count",
        "fixture": "subagent-statusline-tasks.json",
        "expect": expect_statusline,
    },
    {
        "hook": "subagent-usage.py",
        "case": "missing-transcript-silent",
        "fixture": "subagent-usage-missing.json",
        "setup": setup_missing_agent_transcript,
        "expect": expect_usage_missing,
    },
    {
        "hook": "subagent-usage.py",
        "case": "transcript-summary",
        "fixture": "subagent-usage-transcript.json",
        "setup": setup_agent_transcript,
        "expect": expect_usage_summary,
    },
]


def run_case(case):
    hook_name = case["hook"]
    label = "%s:%s" % (hook_name, case["case"])
    hook_path = HOOKS / hook_name
    if not hook_path.exists():
        return "FAIL %s - missing hook %s" % (label, hook_path)

    with tempfile.TemporaryDirectory(prefix="hook-smoke-") as tmp_raw:
        tmp = pathlib.Path(tmp_raw)
        home = tmp / "home"
        home.mkdir()
        env = os.environ.copy()
        env["HOME"] = str(home)
        env.pop("CLAUDE_FILE_PATH", None)
        ctx = {
            "tmp": tmp,
            "home": home,
            "env": env,
            "replacements": {
                "__TEMP_FILE__": str(tmp / "missing-file.js"),
                "__TEMP_TRANSCRIPT__": str(tmp / "missing-transcript.jsonl"),
                "__TEMP_AGENT_TRANSCRIPT__": str(
                    tmp / "missing" / "agent-smoke.jsonl"),
            },
            "scratch": {},
        }
        setup = case.get("setup", setup_noop)
        try:
            setup(ctx)
            stdin_text = read_fixture(case["fixture"], ctx["replacements"])
            res = subprocess.run(
                [str(hook_path)],
                input=stdin_text,
                capture_output=True,
                text=True,
                env=ctx["env"],
                timeout=TIMEOUT_SECONDS,
            )
            case["expect"](res, ctx)
        except subprocess.TimeoutExpired:
            return "FAIL %s - timed out after %ss" % (label, TIMEOUT_SECONDS)
        except SmokeFailure as exc:
            return "FAIL %s - %s" % (label, exc)
        except Exception as exc:
            return "FAIL %s - unexpected error: %s" % (label, exc)
    return "PASS %s" % label


def main():
    lines = [run_case(case) for case in CASES]
    for line in lines:
        print(line)
    return 1 if any(line.startswith("FAIL ") for line in lines) else 0


if __name__ == "__main__":
    sys.exit(main())
