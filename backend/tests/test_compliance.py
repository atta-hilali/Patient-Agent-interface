from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from app.compliance.audit import ImmutableAuditLogger
from app.compliance.checklist import HipaaChecklistService
from app.compliance.secrets import SecretResolver


@dataclass
class _AuditSettings:
    immutable_audit_enabled: bool = True
    immutable_audit_file: str = ""


@dataclass
class _SecretSettings:
    vault_enabled: bool = False
    vault_addr: str = ""
    vault_token: str = ""
    vault_mount: str = "secret/data"
    vault_kv_version: int = 2


def test_immutable_audit_chain_detects_tampering(tmp_path: Path):
    audit_path = tmp_path / "audit_chain.jsonl"
    logger = ImmutableAuditLogger(_AuditSettings(immutable_audit_file=str(audit_path)))

    logger.append(event_type="startup", payload={"service": "test"})
    logger.append(event_type="auth", payload={"patient_id": "p-1"})
    ok_report = logger.verify_chain()
    assert ok_report["ok"] is True
    assert ok_report["records"] == 2

    # Tamper second line payload and keep old hash -> chain must fail.
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    second["payload"]["patient_id"] = "p-tampered"
    lines[1] = json.dumps(second, separators=(",", ":"))
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    fail_report = logger.verify_chain()
    assert fail_report["ok"] is False
    assert fail_report["error"] in {"hash_mismatch", "prev_hash_mismatch"}


def test_secret_resolver_env_first(monkeypatch):
    monkeypatch.setenv("STATE_SIGNING_KEY", "env-secret")
    resolver = SecretResolver(_SecretSettings())
    value = asyncio.run(resolver.resolve("STATE_SIGNING_KEY"))
    assert value == "env-secret"


def test_hipaa_checklist_evaluates_required_items(monkeypatch, tmp_path: Path):
    service = HipaaChecklistService()
    checklist_path = tmp_path / "hipaa_launch_checklist.json"
    checklist_path.write_text(
        json.dumps(
            [
                {"id": "safety_gate_enforced", "source": "automatic", "required": True, "description": "auto"},
                {"id": "clinical_signoff", "source": "manual", "required": True, "description": "manual"},
            ]
        ),
        encoding="utf-8",
    )
    service.path = checklist_path

    async def _fake_auto():
        return {"safety_gate_enforced": True}

    monkeypatch.setattr(service, "_automatic_status", _fake_auto)
    monkeypatch.setenv("HIPAA_CLINICAL_SIGNOFF_APPROVED", "true")

    report = asyncio.run(service.evaluate())
    assert report["ok"] is True
    assert report["required_total"] == 2
    assert report["required_passed"] == 2
