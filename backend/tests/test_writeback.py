from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import HTTPException

from app.adapters import AdapterResolution, SourceAdapter
from app.connectors import ConnectorConfig
from app.writeback import WriteBackService


class _FakeAdapter(SourceAdapter):
    source_type = "fhir_r4"
    adapter_name = "fake-adapter"

    async def write_session_summary(self, **kwargs):  # type: ignore[override]
        return {"ok": True, "resource_type": "Communication", "echo": kwargs}

    async def write_observation(self, **kwargs):  # type: ignore[override]
        return {"ok": True, "resource_type": "Observation", "echo": kwargs}

    async def write_flag(self, **kwargs):  # type: ignore[override]
        return {"ok": True, "resource_type": "Flag", "echo": kwargs}


@dataclass
class _FakeRegistry:
    adapter: SourceAdapter

    def resolve(self, source_type: str) -> AdapterResolution:
        return AdapterResolution(
            source_type=source_type,
            adapter_name=self.adapter.adapter_name,
            adapter=self.adapter,
        )


class _FakeConnectorStore:
    async def get(self, clinic_id: str) -> ConnectorConfig:
        if clinic_id not in {"demo-clinic", "known-clinic"}:
            raise HTTPException(status_code=404, detail="Clinic not found")
        return ConnectorConfig(
            clinic_id=clinic_id,
            adapter_type="fhir_r4",
            base_url="https://example.org/fhir",
            auth_method="smart_pkce",
            topic_yaml="general_medicine",
            write_back="fhir",
            specialty="internal_medicine",
        )


class _FakeSettings:
    pass


def test_writeback_routes_flag_and_uses_connector_fallback(monkeypatch):
    class _Audit:
        def append(self, **kwargs):
            return kwargs

    monkeypatch.setattr("app.writeback.get_audit_logger", lambda: _Audit())
    service = WriteBackService(
        settings=_FakeSettings(),
        adapter_registry=_FakeRegistry(_FakeAdapter()),
        connector_store=_FakeConnectorStore(),
    )

    # Unknown clinic should fall back to demo-clinic.
    result = asyncio.run(
        service.write_flag(
            session_id="s-1",
            patient_id="p-1",
            reason="crisis_keyword",
            severity="HIGH",
            clinic_id="missing-clinic",
        )
    )

    assert result.ok is True
    assert result.operation == "flag"
    assert result.clinic_id == "demo-clinic"
    assert result.adapter == "fake-adapter"
    assert result.resource_type == "Flag"


def test_writeback_routes_session_summary(monkeypatch):
    class _Audit:
        def append(self, **kwargs):
            return kwargs

    monkeypatch.setattr("app.writeback.get_audit_logger", lambda: _Audit())
    service = WriteBackService(
        settings=_FakeSettings(),
        adapter_registry=_FakeRegistry(_FakeAdapter()),
        connector_store=_FakeConnectorStore(),
    )

    result = asyncio.run(
        service.write_session_summary(
            session_id="s-2",
            patient_id="p-2",
            summary="Patient reported mild pain and improved today.",
            clinic_id="known-clinic",
        )
    )

    assert result.ok is True
    assert result.operation == "session_summary"
    assert result.clinic_id == "known-clinic"
    assert result.resource_type == "Communication"
