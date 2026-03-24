from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.responses import RedirectResponse

from .cache import WorkflowCache
from .config import get_settings
from .epic import (
    build_authorize_url,
    exchange_code_for_token,
    fetch_epic_patient_data,
    random_string,
    sha256_base64url,
)
from .models import (
    NormalizeRequest,
    SafetyCheckRequest,
    WorkflowIngestRequest,
    WorkflowUnlockRequest,
)
from .oauth_state import OAuthStateStore
from .safety import run_preflight_safety_check
from .workflow import WorkflowService, run_workflow_pipeline


settings = get_settings()
oauth_state_store = OAuthStateStore(ttl_sec=settings.oauth_state_ttl_sec)
workflow_cache = WorkflowCache(settings=settings)
workflow_service = WorkflowService(settings=settings, cache=workflow_cache)

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


@app.get("/auth/epic/start")
async def auth_epic_start(format: str = Query(default="redirect")) -> Any:
    if not settings.epic_client_id:
        raise HTTPException(status_code=500, detail="EPIC_CLIENT_ID is not configured.")

    state = random_string(32)
    code_verifier = random_string(64)
    code_challenge = sha256_base64url(code_verifier)
    oauth_state_store.put(state=state, code_verifier=code_verifier)
    authorize_url = build_authorize_url(settings=settings, state=state, code_challenge=code_challenge)

    if format == "json":
        return {"authorize_url": authorize_url, "state": state}
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

    code_verifier = oauth_state_store.pop_valid(state)
    if not code_verifier:
        raise HTTPException(status_code=400, detail="State is invalid or expired.")

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
        workflow_snapshot = await run_workflow_pipeline(
            service=workflow_service,
            source_type="fhir",
            source_id="epic-smart",
            patient_id=session_payload["patientId"],
            raw_payload=session_payload["raw"],
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
