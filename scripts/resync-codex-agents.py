#!/usr/bin/env python3
"""Regenerate Codex agent .toml ports from Claude .md sources.

Convention (per bug-hunter.toml, ported 2026-07-02):
  - description copied verbatim from Claude frontmatter
  - model = gpt-5.5; reasoning effort / sandbox / nicknames preserved from existing toml
  - developer_instructions = prompt-defense baseline + Claude body + Codex Compatibility footer
"""
import re, sys, tomllib
from pathlib import Path

HOME = Path.home()
CLAUDE_AGENTS = HOME / ".claude/agents"
CODEX_AGENTS = HOME / ".codex/agents"
DEFENSE = (HOME / ".claude/prompt-defense.md").read_text().strip()

AGENTS = [
    "architect", "bug-hunter", "build-error-resolver", "code-reviewer",
    "database-reviewer",
    "doc-updater", "e2e-runner", "flutter-reviewer", "goal-verifier",
    "payments-reviewer",
    "performance-optimizer", "planner", "react-reviewer", "refactor-cleaner",
    "security-reviewer", "silent-failure-hunter", "tdd-guide",
    "typescript-reviewer",
]

NEW_AGENT_DEFAULTS = {
    "goal-verifier": {
        "model_reasoning_effort": "high",
        "sandbox_mode": "read-only",
        "nickname_candidates": '["goal verifier", "goal_verifier", "verifier"]',
    },
    "database-reviewer": {
        "model_reasoning_effort": "high",
        "sandbox_mode": "read-only",
        "nickname_candidates": '["database reviewer", "database_reviewer", "db reviewer"]',
    },
    "payments-reviewer": {
        "model_reasoning_effort": "high",
        "sandbox_mode": "read-only",
        "nickname_candidates": '["payments reviewer", "payments_reviewer", "money reviewer"]',
    },
    "performance-optimizer": {
        "model_reasoning_effort": "high",
        "sandbox_mode": "read-only",
        "nickname_candidates": '["performance optimizer", "performance_optimizer", "perf"]',
    },
    "silent-failure-hunter": {
        "model_reasoning_effort": "high",
        "sandbox_mode": "read-only",
        "nickname_candidates": '["silent failure hunter", "silent_failure_hunter", "silent failures"]',
    },
    "flutter-reviewer": {
        "model_reasoning_effort": "high",
        "sandbox_mode": "read-only",
        "nickname_candidates": '["flutter reviewer", "flutter_reviewer", "dart reviewer"]',
    },
}

FOOTER_RO = (
    "## Codex Compatibility\n\n"
    "This file was converted from a Claude-style agent prompt into a Codex custom agent. "
    "Treat any Claude-specific tool names (Read, Grep, Glob, Bash, Write, Edit) and agent names "
    "mentioned above as role intent: use the equivalent Codex tools available in the active session, "
    "and stay strictly read-only. Follow Codex system, developer, repository, and user instructions first."
)
FOOTER_RW = (
    "## Codex Compatibility\n\n"
    "This file was converted from a Claude-style agent prompt into a Codex custom agent. "
    "Treat any Claude-specific tool names (Read, Grep, Glob, Bash, Write, Edit) and agent names "
    "mentioned above as role intent: use the equivalent Codex tools available in the active session. "
    "Follow Codex system, developer, repository, and user instructions first."
)


def parse_md(path):
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        sys.exit(f"no frontmatter in {path}")
    fm_raw, body = m.groups()
    fm = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, body.strip()


def existing_header(name):
    p = CODEX_AGENTS / f"{name}.toml"
    if not p.exists():
        return dict(NEW_AGENT_DEFAULTS.get(name, {}))
    t = p.read_text()
    out = {}
    for key in ("model_reasoning_effort", "sandbox_mode"):
        m = re.search(rf'^{key} = "([^"]+)"', t, re.M)
        out[key] = m.group(1) if m else "high"
    m = re.search(r"^nickname_candidates = (\[.*?\])", t, re.M)
    out["nickname_candidates"] = m.group(1) if m else f'["{name.replace("-", " ")}", "{name.replace("-", "_")}"]'
    return out


def toml_escape_basic(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def toml_escape_multiline(s):
    s = s.replace("\\", "\\\\")
    s = s.replace('"""', '""\\"')
    return s


for name in AGENTS:
    md = CLAUDE_AGENTS / f"{name}.md"
    fm, body = parse_md(md)
    hdr = existing_header(name)
    footer = FOOTER_RO if hdr["sandbox_mode"] == "read-only" else FOOTER_RW
    instructions = f"{DEFENSE}\n\n{body}\n\n{footer}\n"
    toml_text = (
        f'name = "{toml_escape_basic(fm["name"])}"\n'
        f'description = "{toml_escape_basic(fm["description"])}"\n'
        f'model = "gpt-5.5"\n'
        f'model_reasoning_effort = "{hdr["model_reasoning_effort"]}"\n'
        f'sandbox_mode = "{hdr["sandbox_mode"]}"\n'
        f'nickname_candidates = {hdr["nickname_candidates"]}\n'
        f'developer_instructions = """\n{toml_escape_multiline(instructions)}"""\n'
    )
    parsed = tomllib.loads(toml_text)  # validate
    assert parsed["name"] == fm["name"]
    assert parsed["developer_instructions"].strip().endswith("instructions first.")
    assert body.split("\n")[0].strip()[:40] in parsed["developer_instructions"]
    out = CODEX_AGENTS / f"{name}.toml"
    is_new = not out.exists()
    out.write_text(toml_text)
    print(f"{'NEW ' if is_new else 'sync'}  {name}.toml  ({len(toml_text)} bytes, effort={hdr['model_reasoning_effort']}, sandbox={hdr['sandbox_mode']})")

print("all files validated with tomllib")
