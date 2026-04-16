from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from .adapters import AdapterRegistry, build_default_registry
from .cache import get_session_cache
from .compliance.audit import get_audit_logger
from .config import Settings, get_settings
from .connectors import ConnectorConfig, ConnectorStore
from .models import AuthToken

logger = logging.getLogger(__name__)


@dataclass
class WriteBackResult:
    ok: bool
    operation: str
    clinic_id: str
    source_type: str
    adapter: str
    resource_type: str
    detail: dict[str, Any]


class WriteBackService:
    """
    Uniform write-back router that dispatches writes through the same adapter
    family used for reads. This keeps Phase 3 behavior consistent across all
    connector types (fhir, hl7, rest/webhook, csv/manual no-op).
    """

    def __init__(
        self,
        *,
        settings: Settings,
        adapter_registry: AdapterRegistry | None = None,
        connector_store: ConnectorStore | None = None,
    ) -> None:
        self.settings = settings
        self.adapter_registry = adapter_registry or build_default_registry()
        self.connector_store = connector_store or ConnectorStore(settings)

    async def _resolve_connector(self, clinic_id: str | None) -> ConnectorConfig:
        requested = (clinic_id or "").strip() or "demo-clinic"
        try:
            return await self.connector_store.get(requested)
        except HTTPException as exc:
            if exc.status_code == 404 and requested != "demo-clinic":
                return await self.connector_store.get("demo-clinic")
            raise

    async def _resolve_auth_token(self, session_id: str) -> AuthToken | None:
        if not session_id:
            return None
        raw = await get_session_cache().get_token(session_id)
        if not isinstance(raw, dict):
            return None
        try:
            return AuthToken.model_validate(raw)
        except Exception:  # noqa: BLE001
            return None

    async def _route(
        self,
        *,
        operation: str,
        session_id: str,
        patient_id: str,
        clinic_id: str | None,
        payload: dict[str, Any],
    ) -> WriteBackResult:
        token = await self._resolve_auth_token(session_id)
        connector = await self._resolve_connector(clinic_id or (token.clinic_id if token else ""))
        resolution = self.adapter_registry.resolve(connector.adapter_type)
        adapter = resolution.adapter
        bearer = token.access_token if token else None

        if operation == "session_summary":
            raw_result = await adapter.write_session_summary(
                connector=connector,
                patient_id=patient_id,
                summary=str(payload.get("summary") or ""),
                session_id=session_id,
                auth_token=bearer,
            )
            resource_type = "session_summary"
        elif operation == "observation":
            raw_result = await adapter.write_observation(
                connector=connector,
                patient_id=patient_id,
                loinc_code=str(payload.get("loinc_code") or ""),
                value=str(payload.get("value") or ""),
                unit=str(payload.get("unit") or ""),
                session_id=session_id,
                auth_token=bearer,
            )
            resource_type = "observation"
        elif operation == "flag":
            raw_result = await adapter.write_flag(
                connector=connector,
                patient_id=patient_id,
                reason=str(payload.get("reason") or ""),
                severity=str(payload.get("severity") or "HIGH"),
                session_id=session_id,
                auth_token=bearer,
            )
            resource_type = "flag"
        else:
            raise ValueError(f"Unsupported write-back operation '{operation}'.")

        detail = raw_result if isinstance(raw_result, dict) else {"result": raw_result}
        ok = bool(detail.get("ok", False))
        if not ok:
            logger.warning(
                "Write-back failed operation=%s clinic=%s adapter=%s detail=%s",
                operation,
                connector.clinic_id,
                resolution.adapter_name,
                detail,
            )
        get_audit_logger().append(
            event_type="writeback",
            payload={
                "operation": operation,
                "ok": ok,
                "clinic_id": connector.clinic_id,
                "adapter": resolution.adapter_name,
                "source_type": resolution.source_type,
                "resource_type": detail.get("resource_type", resource_type),
            },
        )

        return WriteBackResult(
            ok=ok,
            operation=operation,
            clinic_id=connector.clinic_id,
            source_type=resolution.source_type,
            adapter=resolution.adapter_name,
            resource_type=str(detail.get("resource_type") or resource_type),
            detail=detail,
        )

    async def write_session_summary(
        self,
        *,
        session_id: str,
        patient_id: str,
        summary: str,
        clinic_id: str | None = None,
    ) -> WriteBackResult:
        return await self._route(
            operation="session_summary",
            session_id=session_id,
            patient_id=patient_id,
            clinic_id=clinic_id,
            payload={"summary": summary},
        )

    async def write_observation(
        self,
        *,
        session_id: str,
        patient_id: str,
        loinc_code: str,
        value: str,
        unit: str = "",
        clinic_id: str | None = None,
    ) -> WriteBackResult:
        return await self._route(
            operation="observation",
            session_id=session_id,
            patient_id=patient_id,
            clinic_id=clinic_id,
            payload={"loinc_code": loinc_code, "value": value, "unit": unit},
        )

    async def write_flag(
        self,
        *,
        session_id: str,
        patient_id: str,
        reason: str,
        severity: str = "HIGH",
        clinic_id: str | None = None,
    ) -> WriteBackResult:
        return await self._route(
            operation="flag",
            session_id=session_id,
            patient_id=patient_id,
            clinic_id=clinic_id,
            payload={"reason": reason, "severity": severity},
        )


_writeback_service: WriteBackService | None = None


def get_writeback_service() -> WriteBackService:
    global _writeback_service
    if _writeback_service is None:
        _writeback_service = WriteBackService(settings=get_settings())
    return _writeback_service
