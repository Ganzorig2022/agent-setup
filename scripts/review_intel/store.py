"""Private append-only persistence for normalized review traces."""

from __future__ import annotations

import json
import os
import pathlib
import secrets
import stat

from .harvest import CollectionResult


_CLOUD_MARKERS = (
    "/library/mobile documents/",
    "/dropbox/",
    "/onedrive/",
    "/google drive/",
    "/icloud drive/",
)


def validate_output_path(output_dir: pathlib.Path) -> pathlib.Path:
    resolved = output_dir.expanduser().resolve()
    lowered = f"{resolved.as_posix().lower()}/"
    if any(marker in lowered for marker in _CLOUD_MARKERS):
        raise ValueError("output directory is inside a recognized cloud-synced path")
    for ancestor in (resolved, *resolved.parents):
        if (ancestor / ".git").exists():
            raise ValueError("output directory is inside a git worktree")
    return resolved


def load_or_create_salt(output_dir: pathlib.Path) -> bytes:
    output_dir = validate_output_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)
    path = output_dir / "salt"
    _reject_unsafe_store_file(path)
    if path.exists():
        value = _read_private_bytes(path)
        if len(value) != 32:
            raise ValueError("existing salt must be exactly 32 bytes")
        return value
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.fchmod(descriptor, 0o600)
    value = secrets.token_bytes(32)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)
    return value


def _existing_ids(path: pathlib.Path, key: str) -> set[str]:
    values: set[str] = set()
    _reject_unsafe_store_file(path)
    if not path.exists():
        return values
    text = _read_private_bytes(path).decode("utf-8")
    for line_number, raw in enumerate(text.splitlines(), start=1):
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"invalid JSON in {path.name} at line {line_number}"
            ) from error
        value = record.get(key) if isinstance(record, dict) else None
        if not value:
            raise ValueError(
                f"missing {key} in {path.name} at line {line_number}"
            )
        values.add(str(value))
    return values


def _append_unique(
    path: pathlib.Path,
    records: list[dict],
    *,
    key: str,
) -> int:
    seen = _existing_ids(path, key)
    pending = []
    for record in records:
        record_id = str(record.get(key) or "")
        if not record_id:
            raise ValueError(f"record missing required {key}")
        if record_id in seen:
            continue
        seen.add(record_id)
        pending.append(record)
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_APPEND
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        for record in pending:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
    return len(pending)


def _write_private_json(path: pathlib.Path, value: dict) -> None:
    _reject_unsafe_store_file(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    _reject_unsafe_store_file(temporary)
    descriptor = os.open(
        temporary,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_TRUNC
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def _reject_unsafe_store_file(path: pathlib.Path) -> None:
    if path.is_symlink():
        raise ValueError(f"store file must not be a symlink: {path.name}")
    if path.exists() and not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"store file must be regular: {path.name}")


def _read_private_bytes(path: pathlib.Path) -> bytes:
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"store file must be regular: {path.name}")
        if metadata.st_mode & 0o077:
            raise ValueError(f"store file must be private (0600): {path.name}")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            return handle.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def persist_collection(result: CollectionResult, output_dir: pathlib.Path) -> dict:
    output_dir = validate_output_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)
    trace_count = _append_unique(
        output_dir / "traces.jsonl",
        result.traces,
        key="record_id",
    )
    ledger_count = _append_unique(
        output_dir / "collection.jsonl",
        result.ledger,
        key="ledger_id",
    )
    _write_private_json(output_dir / "summary.json", result.summary)
    return {
        "traces_appended": trace_count,
        "ledger_appended": ledger_count,
    }
