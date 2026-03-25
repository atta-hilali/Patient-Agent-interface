from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.responses import RedirectResponse

from .cache import WorkflowCache
from .config import get_settings
from .connectors import ConnectorStore, ConnectorConfig, get_connector_store, verify_internal_key
from .epic import (
    build_authorize_url,
    exchange_code_for_token,
    fetch_epic_patient_data,
    random_string,
    sha256_base64url,
)
from .session_cache import SessionCache
from .models import (
    NormalizeRequest,
    SafetyCheckRequest,
    WorkflowIngestRequest,
    WorkflowUnlockRequest,
    AuthToken,
    ContextSummary,
)
from .oauth_state import OAuthStateStore
from .safety import run_preflight_safety_check
from .workflow import WorkflowService, run_workflow_pipeline


settings = get_settings()
oauth_state_store = OAuthStateStore(
    ttl_sec=settings.oauth_state_ttl_sec,
    redis_url=settings.redis_url,
    signing_key=settings.state_signing_key,
)
workflow_cache = WorkflowCache(settings=settings)
workflow_service = WorkflowService(settings=settings, cache=workflow_cache)
session_cache = SessionCache(settings=settings)
connector_store = ConnectorStore(settings=settings)
connector_store.start_background_refresh()

app = FastAPI(title=settings.app_name)

allow_origins = settings.allowed_origins if settings.allowed_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": settings.app_name, "env": settings.env}


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "ok": True,
        "service": settings.app_name,
        "message": "Backend is running. Use /docs, /health, /auth/epic/start, /workflow/ingest.",
    }


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/workflow/sources")
async def workflow_sources() -> dict[str, Any]:
    return {"supportedSourceTypes": workflow_service.adapter_registry.supported_source_types()}


@app.get("/internal/connectors/{clinic_id}")
async def get_connector(clinic_id: str, _key: None = Depends(verify_internal_key)) -> ConnectorConfig:
    return await connector_store.get(clinic_id)


@app.get("/auth/epic/start")
async def auth_epic_start(
    clinic_id: str = Query(default="demo-clinic"),
    format: str = Query(default="redirect"),
) -> Any:
    if not settings.epic_client_id:
        raise HTTPException(status_code=500, detail="EPIC_CLIENT_ID is not configured.")
    try:
        connector = await connector_store.get(clinic_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if connector.adapter_type != "fhir_r4":
        raise HTTPException(status_code=400, detail="Epic SMART flow is only valid for fhir_r4 adapters.")

    state = random_string(32)
    code_verifier = random_string(64)
    code_challenge = sha256_base64url(code_verifier)
    state_token = await oauth_state_store.issue_state(
        state=state,
        code_verifier=code_verifier,
        clinic_id=connector.clinic_id,
    )
    authorize_url = build_authorize_url(settings=settings, state=state_token, code_challenge=code_challenge)

    if format == "json":
        return {"authorize_url": authorize_url, "state": state_token, "clinic_id": connector.clinic_id}
    return RedirectResponse(url=authorize_url, status_code=302)


@app.get("/auth/epic/callback")
async def auth_epic_callback(
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
) -> dict[str, Any]:
    if error:
        raise HTTPException(status_code=400, detail=f"Epic returned error={error} {error_description}".strip())
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state.")

    entry = await oauth_state_store.pop_valid(state)
    if not entry:
        raise HTTPException(status_code=400, detail="State is invalid or expired.")
    code_verifier = entry.code_verifier

    try:
        token_response = await exchange_code_for_token(
            settings=settings,
            code=code,
            code_verifier=code_verifier,
        )
        session_payload = await fetch_epic_patient_data(
            settings=settings,
            token_response=token_response,
        )
        # Persist AuthToken for this session
        expires_in = token_response.get("expires_in") or 1800
        expires_at_dt = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        expires_at = expires_at_dt.isoformat()
        session_id = random_string(32)
        auth_token = AuthToken(
            access_token=token_response.get("access_token", ""),
            refresh_token=token_response.get("refresh_token"),
            patient_id=session_payload["patientId"],
            expiry=expires_at,
            scope_list=(token_response.get("scope", "") or "").split(),
            adapter_type="fhir_r4",
        )
        await session_cache.set_token(session_id, auth_token.model_dump(mode="json"))

        workflow_snapshot = await run_workflow_pipeline(
            service=workflow_service,
            source_type="fhir_r4",
            source_id=entry.clinic_id or "epic-smart",
            patient_id=session_payload["patientId"],
            raw_payload=session_payload["raw"],
            session_id=session_id,
            session_cache=session_cache,
        )
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        raise HTTPException(status_code=502, detail=f"Epic HTTP error: {detail}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Epic callback processing failed: {exc}") from exc

    return {
        "session": session_payload,
        "workflow": workflow_snapshot,
        "chatUnlock": workflow_snapshot.get("chatUnlock", False),
        "sessionId": session_id,
    }


async def _ingest_request(request: WorkflowIngestRequest) -> dict[str, Any]:
    try:
        return await run_workflow_pipeline(
            service=workflow_service,
            source_type=request.sourceType,
            source_id=request.sourceId,
            patient_id=request.patientId,
            raw_payload=request.rawPayload,
            consent_accepted=request.consentAccepted,
            session_cache=session_cache,
            session_id=request.sessionId or None,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/workflow/normalize")
async def workflow_normalize(request: NormalizeRequest) -> dict[str, Any]:
    return await _ingest_request(request)


@app.post("/workflow/ingest")
async def workflow_ingest(request: WorkflowIngestRequest) -> dict[str, Any]:
    return await _ingest_request(request)


@app.post("/chat/preflight")
async def chat_preflight(request: SafetyCheckRequest) -> dict[str, Any]:
    result = run_preflight_safety_check(
        request.text,
        pain_threshold=settings.preflight_pain_threshold,
    )
    return result.model_dump(mode="json")


@app.post("/workflow/unlock-check")
async def workflow_unlock_check(request: WorkflowUnlockRequest) -> dict[str, Any]:
    result = await workflow_service.check_unlock(
        source_id=request.sourceId,
        patient_id=request.patientId,
        consent_accepted=request.consentAccepted,
    )
    return result.model_dump(mode="json")


def _safe_name(full: str) -> str:
    parts = (full or "").split()
    if not parts:
        return "Unknown"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def _format_next_appt(appointments: list[dict[str, Any]]) -> str | None:
    for appt in appointments:
        start = appt.get("start") or appt.get("description")
        if start:
            return str(start)
    return None


@app.get("/session/{session_id}/context-summary")
async def session_context_summary(
    session_id: str,
    patient_id: str = Query(..., description="Patient identifier for this session"),
) -> dict[str, Any]:
    ctx = await session_cache.get_context(session_id, patient_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="No cached PatientContext for this session.")
    token = await session_cache.get_token(session_id)

    demographics = ctx.get("demographics") or {}
    summary = ContextSummary(
        patient_name=_safe_name(demographics.get("fullName", "")),
        medication_count=len(ctx.get("medications", [])),
        condition_count=len(ctx.get("conditions", [])),
        allergy_count=len(ctx.get("allergies", [])),
        has_alert=len(ctx.get("allergyConflicts", [])) > 0,
        alert_message="Allergy conflict detected" if len(ctx.get("allergyConflicts", [])) > 0 else None,
        next_appointment=_format_next_appt(ctx.get("appointments", [])),
        session_expires_at=(token.get("expiry") if isinstance(token, dict) else None),
        data_source=ctx.get("sourceType"),
    )
    return summary.model_dump(mode="json")
