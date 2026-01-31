"""Simple JSON token store for local development."""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


def read_tokens(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_tokens(path: Path, tokens: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(tokens, handle, indent=2, sort_keys=True)
    tmp.replace(path)

    # Best-effort file permission hardening
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def read_token_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
    except Exception:
        return []
    return []


def write_token_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, sort_keys=True)
    tmp.replace(path)

    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def upsert_token_record(path: Path, record: dict[str, Any], key: str = "user_id") -> None:
    records = read_token_records(path)
    record = {**record, "updated_at": datetime.now(timezone.utc).isoformat()}

    if key in record:
        updated = False
        for idx, existing in enumerate(records):
            if existing.get(key) == record[key]:
                records[idx] = {**existing, **record}
                updated = True
                break
        if not updated:
            records.append(record)
    else:
        records.append(record)

    write_token_records(path, records)


def read_active_user(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
        return value or None
    except Exception:
        return None


def write_active_user(path: Path, user_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(user_id.strip(), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
