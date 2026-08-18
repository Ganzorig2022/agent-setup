#!/usr/bin/env python3
"""Deterministically audit portable and live Claude/Codex configuration hygiene."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import stat
import subprocess
import tomllib
from dataclasses import dataclass, field
from typing import Iterable


SECRET_PATTERNS = {
    "JWT": re.compile(rb"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "Anthropic token": re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "OpenAI-style token": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(rb"\bgh[oprsu]_[A-Za-z0-9]{20,}\b"),
    "GitLab token": re.compile(rb"\b(?:glpat|gldt|glrt|gloas|glptt|glagent|glimt|glsoat|glcbt|glft|glffct)-[A-Za-z0-9_-]{16,}\b"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "Slack token": re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Telegram bot token": re.compile(rb"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "model token": re.compile(rb"\bomlx-[A-Za-z0-9_-]{16,}\b"),
}
FORBIDDEN_TRACKED_NAMES = {
    "auth.json",
    "settings.local.json",
    "default.rules",
    "history.jsonl",
    "session_index.jsonl",
    "traces.jsonl",
}
FORBIDDEN_CODEX_TEMPLATE_KEYS = {"notify", "profile"}
FORBIDDEN_CODEX_TEMPLATE_TABLES = {
    "projects",
    "marketplaces",
    "mcp_servers",
    "plugins",
    "desktop",
    "skills",
}
RISKY_RULE_PATTERNS = {
    "credential-bearing command": re.compile(rb"(?:Bearer\s+eyJ|Authorization:)"),
    "destructive removal": re.compile(
        rb"\brm\b(?=[^\n]{0,120}(?:-[A-Za-z]*[rR]|--recursive))"
        rb"(?=[^\n]{0,120}(?:-[A-Za-z]*[fF]|--force))[^\n]{0,120}"
    ),
    "destructive Git operation": re.compile(
        rb"\bgit\b[^\n]{0,100}\b(?:reset\b[^\n]{0,30}--hard|checkout\b[^\n]{0,30}--|clean\b[^\n]{0,30}-[a-z]*f)"
    ),
    "mutating HTTP request": re.compile(
        rb"\bcurl\b[^\n]{0,200}(?:-X|--request)[^\n]{0,20}(?:POST|PUT|PATCH|DELETE)"
    ),
    "environment sourcing": re.compile(
        rb"(?:^|[;\s\",])(?:source|\.)\b[^\n]{0,100}(?:\.env|credentials|secret)"
    ),
}


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def ok(self, message: str) -> None:
        self.checks.append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home())
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    return parser.parse_args()


def repository_files(repo: pathlib.Path) -> Iterable[pathlib.Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("git ls-files failed while enumerating the portable repository")
    for raw in result.stdout.split(b"\0"):
        if raw:
            yield repo / os.fsdecode(raw)


def scan_file_for_secrets(path: pathlib.Path) -> list[str]:
    try:
        if path.is_symlink():
            content = os.fsencode(os.readlink(path))
            return secret_types(content)
        if path.stat().st_size > 10 * 1024 * 1024:
            return []
        content = path.read_bytes()
    except OSError:
        return []
    return secret_types(content)


def secret_types(content: bytes) -> list[str]:
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(content)]


def audit_repository(repo: pathlib.Path, report: Report) -> None:
    files = list(repository_files(repo))
    for path in files:
        relative = path.relative_to(repo)
        if path.name in FORBIDDEN_TRACKED_NAMES or path.suffix in {".sqlite", ".db"}:
            report.fail(f"portable repo contains forbidden local state: {relative}")
        for secret_type in scan_file_for_secrets(path):
            report.fail(f"possible {secret_type} in portable repo: {relative}")
    report.ok(f"scanned {len(files)} portable repository files")


def load_json_object(path: pathlib.Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("root value is not an object")
    return value


def audit_templates(repo: pathlib.Path, report: Report) -> None:
    claude_path = repo / "claude/settings.template.json"
    codex_path = repo / "codex/config.template.toml"
    try:
        claude = load_json_object(claude_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        report.fail(f"invalid Claude portable template: {error}")
    else:
        if "autoMode" in claude:
            report.fail("Claude portable template contains machine/project-specific autoMode context")
        if "/Users/" in claude_path.read_text(encoding="utf-8"):
            report.fail("Claude portable template contains an absolute user path")
        report.ok("Claude portable template is parseable and sanitized")

    try:
        codex = tomllib.loads(codex_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        report.fail(f"invalid Codex portable template: {error}")
    else:
        for key in sorted(FORBIDDEN_CODEX_TEMPLATE_KEYS & codex.keys()):
            report.fail(f"Codex portable template contains local-only key: {key}")
        for table in sorted(FORBIDDEN_CODEX_TEMPLATE_TABLES & codex.keys()):
            report.fail(f"Codex portable template contains local-only table: [{table}]")
        if "/Users/" in codex_path.read_text(encoding="utf-8"):
            report.fail("Codex portable template contains an absolute user path")
        report.ok("Codex portable template is parseable and sanitized")


def check_private_mode(path: pathlib.Path, report: Report) -> None:
    if not path.exists():
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        report.fail(f"sensitive local file is not private: {path} mode={mode:04o}")


def audit_live(home: pathlib.Path, report: Report) -> None:
    claude_settings = home / ".claude/settings.json"
    claude_local = home / ".claude/settings.local.json"
    codex_config = home / ".codex/config.toml"
    codex_rules = home / ".codex/rules/default.rules"

    for path in (claude_local, codex_config, codex_rules):
        check_private_mode(path, report)
    if claude_settings.is_symlink():
        report.fail("mutable Claude settings.json is still a symlink")
    elif claude_settings.exists():
        check_private_mode(claude_settings, report)
        report.ok("live Claude settings are a private regular file")
    if codex_config.is_symlink():
        report.fail("mutable Codex config.toml must not be a symlink")

    if codex_rules.is_symlink():
        report.fail("local Codex approval rules must not be a symlink")
    if codex_rules.exists():
        content = codex_rules.read_bytes()
        for secret_type in secret_types(content):
            report.fail(f"possible {secret_type} in local Codex approval rules")
        for risk, pattern in RISKY_RULE_PATTERNS.items():
            if pattern.search(content):
                report.fail(f"risky local Codex approval rule: {risk}")
        report.ok("local Codex approval rules contain no recognized secret or high-risk pattern")

    if codex_config.exists():
        try:
            config = tomllib.loads(codex_config.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            report.fail(f"invalid live Codex config: {error}")
        else:
            projects = config.get("projects", {})
            home_trust = projects.get(str(home), {}) if isinstance(projects, dict) else {}
            if isinstance(home_trust, dict) and home_trust.get("trust_level") == "trusted":
                report.fail(f"Codex grants broad trusted-project scope to the home directory: {home}")
            report.ok("live Codex config has no broad home-directory trust")

    runtime_roots = (
        home / ".codex/history.jsonl",
        home / ".codex/archived_sessions",
        home / ".codex/sessions",
        home / ".codex/backups",
    )
    residual_files = 0
    marker = re.compile(rb"merchant-sandbox\.qpay\.mn/v2/invoice[^\n]{0,4000}\beyJ[A-Za-z0-9_-]{10,}\.")
    candidates: list[pathlib.Path] = []
    for root in runtime_roots:
        if root.is_file():
            candidates.append(root)
        elif root.is_dir():
            candidates.extend(path for path in root.rglob("*") if path.is_file())
    for path in candidates:
        try:
            if path.stat().st_size <= 100 * 1024 * 1024 and marker.search(path.read_bytes()):
                residual_files += 1
        except OSError:
            continue
    if residual_files:
        report.warn(
            f"known sandbox endpoint and JWT-like text remain in {residual_files} open/runtime file(s); "
            "rotate the credential and sanitize those files after Codex closes them"
        )
    else:
        report.ok("no known sandbox JWT pattern found in scanned plaintext Codex runtime files")


def render_text(report: Report) -> str:
    status = "PASS" if not report.failures else "FAIL"
    lines = [f"config-hygiene: {status}"]
    lines.extend(f"OK: {message}" for message in report.checks)
    lines.extend(f"WARN: {message}" for message in report.warnings)
    lines.extend(f"FAIL: {message}" for message in report.failures)
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    repo = args.repo.expanduser().resolve()
    home = args.home.expanduser().resolve()
    report = Report()
    try:
        audit_repository(repo, report)
        audit_templates(repo, report)
        audit_live(home, report)
    except (OSError, RuntimeError) as error:
        report.fail(str(error))

    if args.json:
        print(json.dumps({"failures": report.failures, "warnings": report.warnings, "checks": report.checks}, indent=2))
    else:
        print(render_text(report))
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
