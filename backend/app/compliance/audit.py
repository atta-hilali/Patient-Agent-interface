from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ImmutableAuditLogger:
    """
    Append-only hash-chained audit logger.

    Each line stores:
      - event metadata and payload
      - prev_hash from previous record
      - hash of current record
    """

    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.immutable_audit_enabled
        self.path = Path(settings.immutable_audit_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read_last_hash(self) -> str:
        if not self.path.exists():
            return "GENESIS"
        last_hash = "GENESIS"
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except Exception:  # noqa: BLE001
                    continue
                last_hash = str(payload.get("hash") or last_hash)
        return last_hash

    def append(self, *, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}

        with self._lock:
            prev_hash = self._read_last_hash()
            record = {
                "ts": _now_iso(),
                "event_type": event_type,
                "payload": payload,
                "prev_hash": prev_hash,
            }
            digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            record["hash"] = digest
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n")
            return record

    def verify_chain(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "ok": True, "records": 0}
        if not self.path.exists():
            return {"enabled": True, "ok": True, "records": 0}

        prev_hash = "GENESIS"
        records = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except Exception as exc:  # noqa: BLE001
                    return {"enabled": True, "ok": False, "line": line_no, "error": f"invalid_json:{exc}"}

                expected_prev = str(record.get("prev_hash") or "")
                if expected_prev != prev_hash:
                    return {
                        "enabled": True,
                        "ok": False,
                        "line": line_no,
                        "error": "prev_hash_mismatch",
                        "expected_prev": prev_hash,
                        "actual_prev": expected_prev,
                    }

                expected_hash = str(record.get("hash") or "")
                canonical = dict(record)
                canonical.pop("hash", None)
                computed_hash = hashlib.sha256(
                    json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                if expected_hash != computed_hash:
                    return {
                        "enabled": True,
                        "ok": False,
                        "line": line_no,
                        "error": "hash_mismatch",
                    }

                prev_hash = expected_hash
                records += 1

        return {"enabled": True, "ok": True, "records": records, "last_hash": prev_hash}


_audit_logger: ImmutableAuditLogger | None = None


def get_audit_logger() -> ImmutableAuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = ImmutableAuditLogger(get_settings())
    return _audit_logger

