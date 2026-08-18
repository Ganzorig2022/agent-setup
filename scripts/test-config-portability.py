#!/usr/bin/env python3
"""Regression tests for portable configuration merge and hygiene checks."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
import tomllib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[1]
APPLY = REPO / "scripts/apply-portable-config.py"
AUDIT = REPO / "scripts/config-hygiene-audit.py"


def run_script(script: pathlib.Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(script), *arguments],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )


class PortableConfigTests(unittest.TestCase):
    def make_home(self, root: pathlib.Path) -> pathlib.Path:
        home = root / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".codex/rules").mkdir(parents=True)
        local_settings = home / ".claude/settings.local.json"
        local_settings.write_text("{}\n", encoding="utf-8")
        rules = home / ".codex/rules/default.rules"
        rules.write_text("", encoding="utf-8")
        os.chmod(local_settings, 0o600)
        os.chmod(rules, 0o600)
        return home

    def test_apply_detaches_symlink_and_preserves_local_codex_sections(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portable-config-") as temporary:
            root = pathlib.Path(temporary)
            home = self.make_home(root)
            old_claude = root / "old-claude.json"
            old_claude.write_text(
                json.dumps(
                    {
                        "env": {"LOCAL_ONLY_ENV": "preserved"},
                        "permissions": {
                            "allow": ["Bash(local-safe *)"],
                            "deny": ["Read(./machine-secret/**)"],
                            "defaultMode": "auto",
                            "localPolicy": "preserved",
                        },
                        "hooks": {"Notification": [{"hooks": [{"type": "command", "command": "local-notify"}]}]},
                        "enabledPlugins": {
                            "local-plugin@example": True,
                            "codex@openai-codex": False,
                        },
                        "autoMode": {"environment": ["project-specific"]},
                        "localExtensionState": {"keep": True},
                    }
                ),
                encoding="utf-8",
            )
            claude_live = home / ".claude/settings.json"
            claude_live.symlink_to(old_claude)

            codex_live = home / ".codex/config.toml"
            codex_live.write_text(
                'notes = """\n'
                'model = "not-a-setting"\n'
                '"""\n'
                'model = "old-model"\n'
                'notify = ["/machine/local/notify"]\n\n'
                '[projects."/machine/local/project"]\n'
                'trust_level = "trusted"\n\n'
                '[tui]\n'
                'status_line = [\n'
                '  "old-model",\n'
                '  "old-context",\n'
                ']\n'
                'model_availability_nux = true\n\n'
                '[[skills.config]]\n'
                'path = "/machine/local/skill"\n'
                'enabled = false\n',
                encoding="utf-8",
            )
            os.chmod(codex_live, 0o600)

            result = run_script(
                APPLY,
                "--apply",
                "--repo",
                str(REPO),
                "--home",
                str(home),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(claude_live.is_symlink())
            self.assertEqual(claude_live.stat().st_mode & 0o777, 0o600)

            claude = json.loads(claude_live.read_text(encoding="utf-8"))
            self.assertEqual(claude["permissions"]["defaultMode"], "plan")
            self.assertIn("Bash(local-safe *)", claude["permissions"]["allow"])
            self.assertIn("Read(./machine-secret/**)", claude["permissions"]["deny"])
            self.assertEqual(claude["permissions"]["localPolicy"], "preserved")
            self.assertEqual(claude["env"]["LOCAL_ONLY_ENV"], "preserved")
            self.assertTrue(claude["enabledPlugins"]["local-plugin@example"])
            self.assertFalse(claude["enabledPlugins"]["codex@openai-codex"])
            self.assertIn("Notification", claude["hooks"])
            self.assertNotIn("autoMode", claude)
            self.assertEqual(claude["localExtensionState"], {"keep": True})

            codex_text = codex_live.read_text(encoding="utf-8")
            codex = tomllib.loads(codex_text)
            self.assertEqual(codex["model"], "gpt-5.6-sol")
            self.assertIn('model = "not-a-setting"', codex["notes"])
            self.assertEqual(codex["model_reasoning_effort"], "medium")
            self.assertEqual(codex["notify"], ["/machine/local/notify"])
            self.assertEqual(codex["projects"]["/machine/local/project"]["trust_level"], "trusted")
            self.assertTrue(codex["tui"]["model_availability_nux"])
            self.assertEqual(codex["skills"]["config"][0]["path"], "/machine/local/skill")
            self.assertNotIn("status_line", codex["skills"]["config"][0])
            self.assertEqual(
                codex["tui"]["status_line"],
                ["model-with-reasoning", "context-remaining", "five-hour-limit", "weekly-limit", "current-dir", "codex-version"],
            )
            self.assertFalse(
                list((home / ".agent-setup-backup").rglob("settings.json")),
                "detaching a symlink must not copy its target into backups",
            )

            before_second_apply = (claude_live.read_bytes(), codex_live.read_bytes())
            second = run_script(
                APPLY,
                "--apply",
                "--repo",
                str(REPO),
                "--home",
                str(home),
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(before_second_apply, (claude_live.read_bytes(), codex_live.read_bytes()))

            audit = run_script(
                AUDIT,
                "--repo",
                str(REPO),
                "--home",
                str(home),
            )
            self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
            self.assertIn("config-hygiene: PASS", audit.stdout)

    def test_dry_run_does_not_change_live_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portable-config-") as temporary:
            home = self.make_home(pathlib.Path(temporary))
            claude_live = home / ".claude/settings.json"
            codex_live = home / ".codex/config.toml"
            claude_live.write_text('{"custom": true}\n', encoding="utf-8")
            codex_live.write_text('model = "unchanged"\n', encoding="utf-8")
            before = (claude_live.read_bytes(), codex_live.read_bytes())

            result = run_script(
                APPLY,
                "--dry-run",
                "--repo",
                str(REPO),
                "--home",
                str(home),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, (claude_live.read_bytes(), codex_live.read_bytes()))
            self.assertIn("dry-run: no files written", result.stdout)

    def test_invalid_live_toml_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portable-config-") as temporary:
            home = self.make_home(pathlib.Path(temporary))
            (home / ".claude/settings.json").write_text("{}\n", encoding="utf-8")
            codex_live = home / ".codex/config.toml"
            original = b"[broken\n"
            codex_live.write_bytes(original)

            result = run_script(
                APPLY,
                "--apply",
                "--repo",
                str(REPO),
                "--home",
                str(home),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(codex_live.read_bytes(), original)

    def test_missing_claude_template_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portable-config-") as temporary:
            root = pathlib.Path(temporary)
            home = self.make_home(root)
            repo = root / "repo"
            (repo / "claude").mkdir(parents=True)
            (repo / "codex").mkdir(parents=True)
            (repo / "codex/config.template.toml").write_text('model = "safe"\n', encoding="utf-8")

            result = run_script(
                APPLY,
                "--apply",
                "--repo",
                str(repo),
                "--home",
                str(home),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((home / ".claude/settings.json").exists())

    def test_hygiene_flags_reordered_recursive_force_removal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portable-config-") as temporary:
            home = self.make_home(pathlib.Path(temporary))
            claude = home / ".claude/settings.json"
            codex = home / ".codex/config.toml"
            rules = home / ".codex/rules/default.rules"
            claude.write_text("{}\n", encoding="utf-8")
            codex.write_text('model = "local"\n', encoding="utf-8")
            rules.write_text(
                'prefix_rule(pattern=["rm", "-fr", "/important"], decision="allow")\n',
                encoding="utf-8",
            )
            for path in (claude, codex, rules):
                os.chmod(path, 0o600)

            audit = run_script(AUDIT, "--repo", str(REPO), "--home", str(home))
            self.assertNotEqual(audit.returncode, 0)
            self.assertIn("risky local Codex approval rule: destructive removal", audit.stdout)

    def test_hygiene_rejects_symlinked_rules_and_scans_target_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portable-config-") as temporary:
            root = pathlib.Path(temporary)
            home = self.make_home(root)
            claude = home / ".claude/settings.json"
            codex = home / ".codex/config.toml"
            rules = home / ".codex/rules/default.rules"
            target = root / "external.rules"
            claude.write_text("{}\n", encoding="utf-8")
            codex.write_text('model = "local"\n', encoding="utf-8")
            rules.unlink()
            target.write_text("sk-" + "ant-" + ("A" * 32) + "\n", encoding="utf-8")
            rules.symlink_to(target)
            for path in (claude, codex, target):
                os.chmod(path, 0o600)

            audit = run_script(AUDIT, "--repo", str(REPO), "--home", str(home))
            self.assertNotEqual(audit.returncode, 0)
            self.assertIn("local Codex approval rules must not be a symlink", audit.stdout)
            self.assertIn("possible Anthropic token in local Codex approval rules", audit.stdout)


if __name__ == "__main__":
    unittest.main()
