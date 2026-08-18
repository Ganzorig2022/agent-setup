#!/usr/bin/env python3
"""Safely merge portable Claude and Codex preferences into live config files."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import tempfile
import tomllib
from typing import Any


CLAUDE_PORTABLE_KEYS = (
    "env",
    "permissions",
    "hooks",
    "statusLine",
    "subagentStatusLine",
    "enabledPlugins",
    "extraKnownMarketplaces",
    "effortLevel",
    "tui",
    "autoMemoryEnabled",
    "theme",
    "editorMode",
    "autoCompactEnabled",
    "autoUpdaterChannel",
)
CLAUDE_FORBIDDEN_GLOBAL_KEYS = ("autoMode",)
CLAUDE_MERGED_MAP_KEYS = ("env", "enabledPlugins", "extraKnownMarketplaces")
CLAUDE_LOCAL_WINS_MAP_KEYS = ("enabledPlugins", "extraKnownMarketplaces")
CODEX_PORTABLE_KEYS: dict[str | None, tuple[str, ...]] = {
    None: (
        "model",
        "model_reasoning_effort",
        "plan_mode_reasoning_effort",
        "web_search",
        "personality",
        "approvals_reviewer",
        "service_tier",
        "suppress_unstable_features_warning",
    ),
    "agents": ("max_threads", "max_depth", "job_max_runtime_seconds"),
    "features": (
        "collaboration_modes",
        "prevent_idle_sleep",
        "goals",
        "terminal_resize_reflow",
        "js_repl",
    ),
    "notice": ("fast_default_opt_out",),
    "tui": ("status_line", "status_line_use_colors", "pet"),
}
SECTION_RE = re.compile(r"^\s*(?:\[\[([^\]]+)]]|\[([^\]]+)])\s*(?:#.*)?$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write validated changes")
    mode.add_argument("--dry-run", action="store_true", help="report changes only (default)")
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument("--home", type=pathlib.Path, default=pathlib.Path.home())
    return parser.parse_args()


def read_json(path: pathlib.Path, *, required: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if required:
            raise ValueError(f"required JSON template is missing: {path}")
        return {}
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def ordered_union(portable: list[Any], local: list[Any]) -> list[Any]:
    merged = list(portable)
    for item in local:
        if item not in merged:
            merged.append(item)
    return merged


def merge_permissions(portable: Any, local: Any) -> dict[str, Any]:
    if not isinstance(portable, dict):
        raise ValueError("portable Claude permissions must be an object")
    local_map = local if isinstance(local, dict) else {}
    merged = dict(local_map)
    for key, value in portable.items():
        if key in {"allow", "deny"}:
            portable_rules = value if isinstance(value, list) else []
            local_rules = local_map.get(key, [])
            if not isinstance(local_rules, list):
                local_rules = []
            merged[key] = ordered_union(portable_rules, local_rules)
        else:
            merged[key] = value
    return merged


def merge_hooks(portable: Any, local: Any) -> dict[str, Any]:
    if not isinstance(portable, dict):
        raise ValueError("portable Claude hooks must be an object")
    local_map = local if isinstance(local, dict) else {}
    merged = dict(local_map)
    for event, portable_hooks in portable.items():
        local_hooks = local_map.get(event, [])
        if isinstance(portable_hooks, list) and isinstance(local_hooks, list):
            merged[event] = ordered_union(portable_hooks, local_hooks)
        else:
            merged[event] = portable_hooks
    return merged


def merge_claude(template_path: pathlib.Path, live_path: pathlib.Path) -> tuple[str, list[str]]:
    template = read_json(template_path, required=True)
    live = read_json(live_path)
    changed: list[str] = []
    for key in CLAUDE_PORTABLE_KEYS:
        if key not in template:
            continue
        portable_value = template[key]
        if key == "permissions":
            merged_value = merge_permissions(portable_value, live.get(key))
        elif key == "hooks":
            merged_value = merge_hooks(portable_value, live.get(key))
        elif key in CLAUDE_MERGED_MAP_KEYS:
            local_value = live.get(key)
            local_map = local_value if isinstance(local_value, dict) else {}
            if not isinstance(portable_value, dict):
                raise ValueError(f"portable Claude {key} must be an object")
            merged_value = (
                {**portable_value, **local_map}
                if key in CLAUDE_LOCAL_WINS_MAP_KEYS
                else {**local_map, **portable_value}
            )
        else:
            merged_value = portable_value
        if live.get(key) != merged_value:
            live[key] = merged_value
            changed.append(key)
    for key in CLAUDE_FORBIDDEN_GLOBAL_KEYS:
        if key in live:
            del live[key]
            changed.append(f"remove:{key}")
    return json.dumps(live, indent=2, ensure_ascii=False) + "\n", changed


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported portable TOML value: {type(value).__name__}")


def toml_multiline_string_mask(lines: list[str]) -> list[bool]:
    """Mark lines that begin inside a TOML multiline basic or literal string."""
    state: str | None = None
    mask: list[bool] = []
    for line in lines:
        mask.append(state is not None)
        index = 0
        while index < len(line):
            if state is not None:
                closing = line.find(state, index)
                if closing < 0:
                    break
                if state == '"""':
                    backslashes = 0
                    position = closing - 1
                    while position >= 0 and line[position] == "\\":
                        backslashes += 1
                        position -= 1
                    if backslashes % 2:
                        index = closing + 1
                        continue
                state = None
                index = closing + 3
                continue

            if line[index] == "#":
                break
            if line.startswith('"""', index) or line.startswith("'''", index):
                state = line[index : index + 3]
                index += 3
                continue
            if line[index] in {'"', "'"}:
                quote = line[index]
                index += 1
                while index < len(line):
                    if quote == '"' and line[index] == "\\":
                        index += 2
                        continue
                    if line[index] == quote:
                        index += 1
                        break
                    index += 1
                continue
            index += 1
    return mask


def section_bounds(lines: list[str], section: str | None) -> tuple[int, int] | None:
    multiline_mask = toml_multiline_string_mask(lines)
    headers = [
        (index, match.group(1) or match.group(2))
        for index, line in enumerate(lines)
        if not multiline_mask[index] and (match := SECTION_RE.match(line))
    ]
    if section is None:
        return 0, headers[0][0] if headers else len(lines)
    for position, (start, name) in enumerate(headers):
        if name == section:
            end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
            return start + 1, end
    return None


def set_toml_key(lines: list[str], section: str | None, key: str, value: Any) -> None:
    bounds = section_bounds(lines, section)
    rendered = f"{key} = {toml_value(value)}\n"
    if bounds is None:
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.extend([f"[{section}]\n", rendered])
        return

    start, end = bounds
    assignment = re.compile(rf"^\s*{re.escape(key)}\s*=")
    multiline_mask = toml_multiline_string_mask(lines)
    for index in range(start, end):
        if not multiline_mask[index] and assignment.match(lines[index]):
            value_text = lines[index].split("=", 1)[1]
            value_end = index + 1
            while value_end <= end:
                try:
                    tomllib.loads(f"value = {value_text}")
                except tomllib.TOMLDecodeError:
                    if value_end == end:
                        raise ValueError(f"could not parse existing TOML value for {key}")
                    value_text += lines[value_end]
                    value_end += 1
                    continue
                break
            lines[index:value_end] = [rendered]
            return
    lines.insert(end, rendered)


def get_table(config: dict[str, Any], section: str | None) -> dict[str, Any]:
    if section is None:
        return config
    value = config.get(section, {})
    if not isinstance(value, dict):
        raise ValueError(f"expected [{section}] to be a TOML table")
    return value


def portable_codex_values(config: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for section, keys in CODEX_PORTABLE_KEYS.items():
        table = get_table(config, section)
        for key in keys:
            if key in table:
                label = key if section is None else f"{section}.{key}"
                values[label] = table[key]
    return values


def merge_codex(template_path: pathlib.Path, live_path: pathlib.Path) -> tuple[str, list[str]]:
    template_text = template_path.read_text(encoding="utf-8")
    template = tomllib.loads(template_text)
    if live_path.exists():
        live_text = live_path.read_text(encoding="utf-8")
        try:
            before = tomllib.loads(live_text)
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"invalid TOML in {live_path}: {error}") from error
    else:
        live_text = template_text
        before = {}

    lines = live_text.splitlines(keepends=True)
    for section, keys in CODEX_PORTABLE_KEYS.items():
        source = get_table(template, section)
        for key in keys:
            if key in source:
                set_toml_key(lines, section, key, source[key])

    merged = "".join(lines)
    try:
        after = tomllib.loads(merged)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"portable merge produced invalid TOML: {error}") from error
    before_values = portable_codex_values(before)
    after_values = portable_codex_values(after)
    changed = sorted(key for key, value in after_values.items() if before_values.get(key) != value)
    return merged, changed


def ensure_private_directory(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def backup_live(path: pathlib.Path, home: pathlib.Path, backup_root: pathlib.Path) -> None:
    if path.is_symlink() or not path.exists():
        return
    try:
        relative = path.relative_to(home)
    except ValueError:
        relative = pathlib.Path(path.name)
    destination = backup_root / relative
    ensure_private_directory(destination.parent)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as source:
        destination.write_bytes(source.read())
    os.chmod(destination, 0o600)


def atomic_write(path: pathlib.Path, content: str) -> None:
    ensure_private_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    repo = args.repo.expanduser().resolve()
    home = args.home.expanduser().resolve()
    targets = (
        (
            "Claude",
            repo / "claude/settings.template.json",
            home / ".claude/settings.json",
            merge_claude,
        ),
        (
            "Codex",
            repo / "codex/config.template.toml",
            home / ".codex/config.toml",
            merge_codex,
        ),
    )

    pending: list[tuple[str, pathlib.Path, str, list[str]]] = []
    for name, template, live, merger in targets:
        content, changed = merger(template, live)
        insecure_mode = live.exists() and bool(live.stat().st_mode & 0o077)
        if changed or not live.exists() or live.is_symlink() or insecure_mode:
            pending.append((name, live, content, changed))
        detail = ", ".join(changed) if changed else "no portable key drift"
        link_note = "; detach mutable symlink" if live.is_symlink() else ""
        mode_note = "; harden permissions" if insecure_mode else ""
        print(f"{name}: {detail}{link_note}{mode_note}")

    if not args.apply:
        print("dry-run: no files written")
        return 0
    if not pending:
        print("apply: already current")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = home / ".agent-setup-backup/config" / stamp
    for _, live, _, _ in pending:
        backup_live(live, home, backup_root)
    for _, live, content, _ in pending:
        atomic_write(live, content)
    print(f"apply: updated {len(pending)} file(s); private backups: {backup_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
