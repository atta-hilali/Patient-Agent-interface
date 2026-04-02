<<<<<<< HEAD
# from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone
# from typing import Any
=======
import asyncio
import socket
>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f
from typing import Any
from urllib.parse import urlparse

# import httpx
import httpx
# from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi import Depends, FastAPI, HTTPException, Query
# from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import RedirectResponse, Response
from fastapi.responses import RedirectResponse, Response
# from pydantic import BaseModel, Field
from pydantic import BaseModel, Field

<<<<<<< HEAD
# from .agent.llm_client import get_llm_health, get_vllm_deployment_command
from .agent.llm_client import get_llm_health, get_vllm_deployment_command
# from .cache import WorkflowCache
=======
from .asr import decode_base64_audio, transcribe_audio
>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f
from .cache import WorkflowCache
# from .config import get_settings
from .config import get_settings
# from .connectors import ConnectorConfig, ConnectorStore, verify_internal_key
from .connectors import ConnectorConfig, ConnectorStore, verify_internal_key
# from .epic import (
from .epic import (
    # build_authorize_url,
    build_authorize_url,
    # exchange_code_for_token,
    exchange_code_for_token,
    # fetch_epic_patient_data,
    fetch_epic_patient_data,
    # random_string,
    random_string,
    # sha256_base64url,
    sha256_base64url,
# )
)
# from .models import (
from .models import (
<<<<<<< HEAD
    # AuthToken,
    AuthToken,
    # ContextSummary,
    ContextSummary,
    # NormalizeRequest,
=======
    AsrTranscribeRequest,
    AsrTranscribeResponse,
    CdaIngestRequest,
    CsvIngestRequest,
    Hl7IngestRequest,
>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f
    NormalizeRequest,
    # SafetyCheckRequest,
    SafetyCheckRequest,
    # WorkflowIngestRequest,
    WorkflowIngestRequest,
    # WorkflowUnlockRequest,
    WorkflowUnlockRequest,
# )
)
<<<<<<< HEAD
# from .oauth_state import OAuthStateStore
=======
from .hl7_mllp import Hl7MllpListener
>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f
from .oauth_state import OAuthStateStore
# from .routers import agent as agent_router
from .routers import agent as agent_router
# from .routers import audio as audio_router
from .routers import audio as audio_router
# from .routers import tts as tts_router
from .routers import tts as tts_router
# from .safety.checker import get_safety_checker
from .safety.checker import get_safety_checker
# from .safety import run_preflight_safety_check
from .safety import run_preflight_safety_check
# from .safety.preflight import get_preflight_checker
from .safety.preflight import get_preflight_checker
# from .session_cache import SessionCache
from .session_cache import SessionCache
# from .workflow import WorkflowService, run_workflow_pipeline
from .workflow import WorkflowService, run_workflow_pipeline


# settings = get_settings()
settings = get_settings()
# oauth_state_store = OAuthStateStore(
oauth_state_store = OAuthStateStore(
    # ttl_sec=settings.oauth_state_ttl_sec,
    ttl_sec=settings.oauth_state_ttl_sec,
    # redis_url=settings.redis_url,
    redis_url=settings.redis_url,
    # signing_key=settings.state_signing_key,
    signing_key=settings.state_signing_key,
# )
)
# workflow_cache = WorkflowCache(settings=settings)
workflow_cache = WorkflowCache(settings=settings)
# workflow_service = WorkflowService(settings=settings, cache=workflow_cache)
workflow_service = WorkflowService(settings=settings, cache=workflow_cache)
<<<<<<< HEAD
# session_cache = SessionCache(settings=settings)
session_cache = SessionCache(settings=settings)
# connector_store = ConnectorStore(settings=settings)
connector_store = ConnectorStore(settings=settings)
=======
hl7_listener: Hl7MllpListener | None = None
hl7_recent_messages: list[dict[str, Any]] = []
>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f

# app = FastAPI(title=settings.app_name)
app = FastAPI(title=settings.app_name)

# allow_origins = settings.allowed_origins if settings.allowed_origins else ["*"]
allow_origins = settings.allowed_origins if settings.allowed_origins else ["*"]
# app.add_middleware(
app.add_middleware(
    # CORSMiddleware,
    CORSMiddleware,
    # allow_origins=allow_origins,
    allow_origins=allow_origins,
    # allow_methods=["*"],
    allow_methods=["*"],
    # allow_headers=["*"],
    allow_headers=["*"],
# )
)

# app.include_router(agent_router.router)
app.include_router(agent_router.router)
# app.include_router(audio_router.router)
app.include_router(audio_router.router)
# app.include_router(tts_router.router)
app.include_router(tts_router.router)

<<<<<<< HEAD

# class SafetyProfileUpdateRequest(BaseModel):
class SafetyProfileUpdateRequest(BaseModel):
    # specialty: str | None = None
    specialty: str | None = None
    # topic_yaml: str = Field(min_length=1)
    topic_yaml: str = Field(min_length=1)


# class CustomSafetyProfileRequest(BaseModel):
class CustomSafetyProfileRequest(BaseModel):
    # specialty: str | None = None
    specialty: str | None = None
    # yaml_content: str = Field(min_length=1)
    yaml_content: str = Field(min_length=1)


# @app.on_event("startup")
@app.on_event("startup")
# async def startup_events() -> None:
async def startup_events() -> None:
    # get_preflight_checker()
    get_preflight_checker()
    # connector_store.start_background_refresh()
    connector_store.start_background_refresh()


# @app.get("/health")
=======
async def _handle_mllp_message(message: str, peer: str) -> dict[str, Any]:
    snapshot = await run_workflow_pipeline(
        service=workflow_service,
        source_type="hl7",
        source_id=settings.hl7_mllp_source_id,
        patient_id="hl7-patient",
        raw_payload={"hl7Message": message},
    )
    record = {
        "receivedAt": snapshot.get("updatedAt"),
        "peer": peer,
        "sourceId": settings.hl7_mllp_source_id,
        "patientId": snapshot.get("patientId"),
        "cacheKey": snapshot.get("cacheKey"),
    }
    hl7_recent_messages.append(record)
    if len(hl7_recent_messages) > 100:
        del hl7_recent_messages[0 : len(hl7_recent_messages) - 100]
    return record


@app.on_event("startup")
async def startup_event() -> None:
    await workflow_cache.ping()

    global hl7_listener
    if settings.hl7_mllp_enabled:
        hl7_listener = Hl7MllpListener(
            host=settings.hl7_mllp_host,
            port=settings.hl7_mllp_port,
            on_message=_handle_mllp_message,
        )
        await hl7_listener.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global hl7_listener
    if hl7_listener:
        await hl7_listener.stop()
        hl7_listener = None


>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f
@app.get("/health")
# async def health() -> dict[str, Any]:
async def health() -> dict[str, Any]:
    # llm_health = get_llm_health()
    llm_health = get_llm_health()
    # return {
    return {
        # "ok": True,
        "ok": True,
        # "service": settings.app_name,
        "service": settings.app_name,
<<<<<<< HEAD
        # "env": settings.env,
        "env": settings.env,
        # "llm": llm_health,
        "llm": llm_health,
        # "alert": llm_health["alert"],
        "alert": llm_health["alert"],
        # "deployment_command": get_vllm_deployment_command(),
        "deployment_command": get_vllm_deployment_command(),
    # }
=======
        "message": "Backend is running. Use /docs, /health, /auth/epic/start, /workflow/ingest, /workflow/ingest/csv, /voice/asr/probe, /voice/transcribe.",
>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f
    }


# @app.get("/")
@app.get("/")
# async def root() -> dict[str, Any]:
async def root() -> dict[str, Any]:
    # return {
    return {
        # "ok": True,
        "ok": True,
        # "service": settings.app_name,
        "service": settings.app_name,
        # "message": "Backend is running. Use /docs, /health, /auth/epic/start, /workflow/ingest.",
        "message": "Backend is running. Use /docs, /health, /auth/epic/start, /workflow/ingest.",
    # }
    }


# @app.get("/favicon.ico")
@app.get("/favicon.ico")
# async def favicon() -> Response:
async def favicon() -> Response:
    # return Response(status_code=204)
    return Response(status_code=204)


# @app.get("/workflow/sources")
@app.get("/workflow/sources")
# async def workflow_sources() -> dict[str, Any]:
async def workflow_sources() -> dict[str, Any]:
    # return {"supportedSourceTypes": workflow_service.adapter_registry.supported_source_types()}
    return {"supportedSourceTypes": workflow_service.adapter_registry.supported_source_types()}


<<<<<<< HEAD
# @app.get("/internal/connectors/{clinic_id}")
@app.get("/internal/connectors/{clinic_id}")
# async def get_connector(clinic_id: str, _key: None = Depends(verify_internal_key)) -> ConnectorConfig:
async def get_connector(clinic_id: str, _key: None = Depends(verify_internal_key)) -> ConnectorConfig:
    # return await connector_store.get(clinic_id)
    return await connector_store.get(clinic_id)


# @app.get("/internal/safety/topic-profiles")
@app.get("/internal/safety/topic-profiles")
# async def list_safety_topic_profiles(_key: None = Depends(verify_internal_key)) -> dict[str, Any]:
async def list_safety_topic_profiles(_key: None = Depends(verify_internal_key)) -> dict[str, Any]:
    # return {"profiles": get_safety_checker().available_topic_profiles()}
    return {"profiles": get_safety_checker().available_topic_profiles()}


# @app.post("/internal/connectors/{clinic_id}/safety-profile")
@app.post("/internal/connectors/{clinic_id}/safety-profile")
# async def set_clinic_safety_profile(
async def set_clinic_safety_profile(
    # clinic_id: str,
    clinic_id: str,
    # request: SafetyProfileUpdateRequest,
    request: SafetyProfileUpdateRequest,
    # _key: None = Depends(verify_internal_key),
    _key: None = Depends(verify_internal_key),
# ) -> ConnectorConfig:
) -> ConnectorConfig:
    # return await connector_store.update_topic_yaml(
    return await connector_store.update_topic_yaml(
        # clinic_id,
        clinic_id,
        # topic_yaml=request.topic_yaml,
        topic_yaml=request.topic_yaml,
        # specialty=request.specialty,
        specialty=request.specialty,
    # )
    )


# @app.post("/internal/connectors/{clinic_id}/safety-profile/custom")
@app.post("/internal/connectors/{clinic_id}/safety-profile/custom")
# async def upload_custom_safety_profile(
async def upload_custom_safety_profile(
    # clinic_id: str,
    clinic_id: str,
    # request: CustomSafetyProfileRequest,
    request: CustomSafetyProfileRequest,
    # _key: None = Depends(verify_internal_key),
    _key: None = Depends(verify_internal_key),
# ) -> ConnectorConfig:
) -> ConnectorConfig:
    # checker = get_safety_checker()
    checker = get_safety_checker()
    # file_name = checker.save_custom_topic_yaml(clinic_id=clinic_id, yaml_content=request.yaml_content)
    file_name = checker.save_custom_topic_yaml(clinic_id=clinic_id, yaml_content=request.yaml_content)
    # return await connector_store.update_topic_yaml(
    return await connector_store.update_topic_yaml(
        # clinic_id,
        clinic_id,
        # topic_yaml=file_name,
        topic_yaml=file_name,
        # specialty=request.specialty,
        specialty=request.specialty,
    # )
    )


# @app.get("/auth/epic/start")
=======
@app.get("/cache/status")
async def cache_status() -> dict[str, Any]:
    redis_reachable = False
    redis_error = ""
    try:
        redis_reachable = await workflow_cache.ping()
    except Exception as exc:  # noqa: BLE001
        redis_error = str(exc)

    return {
        "redisRequired": settings.redis_required,
        "redisConfigured": bool(settings.redis_url),
        "redisReachable": redis_reachable,
        "redisError": redis_error,
        "cacheKeyPrefix": settings.workflow_cache_key_prefix,
        "ttlSeconds": settings.workflow_cache_ttl_sec,
    }


@app.get("/hl7/mllp/status")
async def hl7_mllp_status() -> dict[str, Any]:
    return {
        "enabled": settings.hl7_mllp_enabled,
        "running": bool(hl7_listener and hl7_listener.is_running),
        "host": settings.hl7_mllp_host,
        "port": settings.hl7_mllp_port,
        "sourceId": settings.hl7_mllp_source_id,
        "recentMessages": len(hl7_recent_messages),
    }


@app.get("/hl7/mllp/messages")
async def hl7_mllp_messages() -> dict[str, Any]:
    return {"messages": hl7_recent_messages[-50:]}


>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f
@app.get("/auth/epic/start")
# async def auth_epic_start(
async def auth_epic_start(
    # clinic_id: str = Query(default="demo-clinic"),
    clinic_id: str = Query(default="demo-clinic"),
    # format: str = Query(default="redirect"),
    format: str = Query(default="redirect"),
# ) -> Any:
) -> Any:
    # if not settings.epic_client_id:
    if not settings.epic_client_id:
        # raise HTTPException(status_code=500, detail="EPIC_CLIENT_ID is not configured.")
        raise HTTPException(status_code=500, detail="EPIC_CLIENT_ID is not configured.")
    # try:
    try:
        # connector = await connector_store.get(clinic_id)
        connector = await connector_store.get(clinic_id)
    # except HTTPException:
    except HTTPException:
        # raise
        raise
    # except Exception as exc:  # noqa: BLE001
    except Exception as exc:  # noqa: BLE001
        # raise HTTPException(status_code=500, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    # if connector.adapter_type != "fhir_r4":
    if connector.adapter_type != "fhir_r4":
        # raise HTTPException(status_code=400, detail="Epic SMART flow is only valid for fhir_r4 adapters.")
        raise HTTPException(status_code=400, detail="Epic SMART flow is only valid for fhir_r4 adapters.")

    # state = random_string(32)
    state = random_string(32)
    # code_verifier = random_string(64)
    code_verifier = random_string(64)
    # code_challenge = sha256_base64url(code_verifier)
    code_challenge = sha256_base64url(code_verifier)
    # state_token = await oauth_state_store.issue_state(
    state_token = await oauth_state_store.issue_state(
        # state=state,
        state=state,
        # code_verifier=code_verifier,
        code_verifier=code_verifier,
        # clinic_id=connector.clinic_id,
        clinic_id=connector.clinic_id,
    # )
    )
    # authorize_url = build_authorize_url(settings=settings, state=state_token, code_challenge=code_challenge)
    authorize_url = build_authorize_url(settings=settings, state=state_token, code_challenge=code_challenge)

    # if format == "json":
    if format == "json":
        # return {"authorize_url": authorize_url, "state": state_token, "clinic_id": connector.clinic_id}
        return {"authorize_url": authorize_url, "state": state_token, "clinic_id": connector.clinic_id}
    # return RedirectResponse(url=authorize_url, status_code=302)
    return RedirectResponse(url=authorize_url, status_code=302)


# @app.get("/auth/epic/callback")
@app.get("/auth/epic/callback")
# async def auth_epic_callback(
async def auth_epic_callback(
    # code: str = Query(default=""),
    code: str = Query(default=""),
    # state: str = Query(default=""),
    state: str = Query(default=""),
    # error: str = Query(default=""),
    error: str = Query(default=""),
    # error_description: str = Query(default=""),
    error_description: str = Query(default=""),
# ) -> dict[str, Any]:
) -> dict[str, Any]:
    # if error:
    if error:
        # raise HTTPException(status_code=400, detail=f"Epic returned error={error} {error_description}".strip())
        raise HTTPException(status_code=400, detail=f"Epic returned error={error} {error_description}".strip())
    # if not code or not state:
    if not code or not state:
        # raise HTTPException(status_code=400, detail="Missing code or state.")
        raise HTTPException(status_code=400, detail="Missing code or state.")

    # entry = await oauth_state_store.pop_valid(state)
    entry = await oauth_state_store.pop_valid(state)
    # if not entry:
    if not entry:
        # raise HTTPException(status_code=400, detail="State is invalid or expired.")
        raise HTTPException(status_code=400, detail="State is invalid or expired.")
    # code_verifier = entry.code_verifier
    code_verifier = entry.code_verifier

    # try:
    try:
        # token_response = await exchange_code_for_token(
        token_response = await exchange_code_for_token(
            # settings=settings,
            settings=settings,
            # code=code,
            code=code,
            # code_verifier=code_verifier,
            code_verifier=code_verifier,
        # )
        )
        # session_payload = await fetch_epic_patient_data(
        session_payload = await fetch_epic_patient_data(
            # settings=settings,
            settings=settings,
            # token_response=token_response,
            token_response=token_response,
        # )
        )
        # # Persist AuthToken for this session
        # Persist AuthToken for this session
        # expires_in = token_response.get("expires_in") or 1800
        expires_in = token_response.get("expires_in") or 1800
        # expires_at_dt = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        expires_at_dt = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        # expires_at = expires_at_dt.isoformat()
        expires_at = expires_at_dt.isoformat()
        # session_id = random_string(32)
        session_id = random_string(32)
        # auth_token = AuthToken(
        auth_token = AuthToken(
            # access_token=token_response.get("access_token", ""),
            access_token=token_response.get("access_token", ""),
            # refresh_token=token_response.get("refresh_token"),
            refresh_token=token_response.get("refresh_token"),
            # patient_id=session_payload["patientId"],
            patient_id=session_payload["patientId"],
            # clinic_id=entry.clinic_id or "demo-clinic",
            clinic_id=entry.clinic_id or "demo-clinic",
            # expiry=expires_at,
            expiry=expires_at,
            # scope_list=(token_response.get("scope", "") or "").split(),
            scope_list=(token_response.get("scope", "") or "").split(),
            # adapter_type="fhir_r4",
            adapter_type="fhir_r4",
        # )
        )
        # await session_cache.set_token(session_id, auth_token.model_dump(mode="json"))
        await session_cache.set_token(session_id, auth_token.model_dump(mode="json"))

        # workflow_snapshot = await run_workflow_pipeline(
        workflow_snapshot = await run_workflow_pipeline(
            # service=workflow_service,
            service=workflow_service,
            # source_type="fhir_r4",
            source_type="fhir_r4",
            # source_id=entry.clinic_id or "epic-smart",
            source_id=entry.clinic_id or "epic-smart",
            # patient_id=session_payload["patientId"],
            patient_id=session_payload["patientId"],
            # raw_payload=session_payload["raw"],
            raw_payload=session_payload["raw"],
            # session_id=session_id,
            session_id=session_id,
            # session_cache=session_cache,
            session_cache=session_cache,
        # )
        )
    # except httpx.HTTPStatusError as exc:
    except httpx.HTTPStatusError as exc:
        # detail = exc.response.text if exc.response is not None else str(exc)
        detail = exc.response.text if exc.response is not None else str(exc)
        # raise HTTPException(status_code=502, detail=f"Epic HTTP error: {detail}") from exc
        raise HTTPException(status_code=502, detail=f"Epic HTTP error: {detail}") from exc
    # except Exception as exc:  # noqa: BLE001
    except Exception as exc:  # noqa: BLE001
        # raise HTTPException(status_code=500, detail=f"Epic callback processing failed: {exc}") from exc
        raise HTTPException(status_code=500, detail=f"Epic callback processing failed: {exc}") from exc

    # return {
    return {
        # "session": session_payload,
        "session": session_payload,
        # "workflow": workflow_snapshot,
        "workflow": workflow_snapshot,
        # "chatUnlock": workflow_snapshot.get("chatUnlock", False),
        "chatUnlock": workflow_snapshot.get("chatUnlock", False),
        # "sessionId": session_id,
        "sessionId": session_id,
    # }
    }


# async def _ingest_request(request: WorkflowIngestRequest) -> dict[str, Any]:
async def _ingest_request(request: WorkflowIngestRequest) -> dict[str, Any]:
    # try:
    try:
        # return await run_workflow_pipeline(
        return await run_workflow_pipeline(
            # service=workflow_service,
            service=workflow_service,
            # source_type=request.sourceType,
            source_type=request.sourceType,
            # source_id=request.sourceId,
            source_id=request.sourceId,
            # patient_id=request.patientId,
            patient_id=request.patientId,
            # raw_payload=request.rawPayload,
            raw_payload=request.rawPayload,
            # consent_accepted=request.consentAccepted,
            consent_accepted=request.consentAccepted,
            # session_cache=session_cache,
            session_cache=session_cache,
            # session_id=request.sessionId or None,
            session_id=request.sessionId or None,
        # )
        )
    # except Exception as exc:  # noqa: BLE001
    except Exception as exc:  # noqa: BLE001
        # raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# @app.post("/workflow/normalize")
@app.post("/workflow/normalize")
# async def workflow_normalize(request: NormalizeRequest) -> dict[str, Any]:
async def workflow_normalize(request: NormalizeRequest) -> dict[str, Any]:
    # return await _ingest_request(request)
    return await _ingest_request(request)


# @app.post("/workflow/ingest")
@app.post("/workflow/ingest")
# async def workflow_ingest(request: WorkflowIngestRequest) -> dict[str, Any]:
async def workflow_ingest(request: WorkflowIngestRequest) -> dict[str, Any]:
    # return await _ingest_request(request)
    return await _ingest_request(request)


<<<<<<< HEAD
# @app.post("/chat/preflight")
=======
@app.post("/workflow/ingest/hl7")
async def workflow_ingest_hl7(request: Hl7IngestRequest) -> dict[str, Any]:
    try:
        snapshot = await run_workflow_pipeline(
            service=workflow_service,
            source_type="hl7",
            source_id=request.sourceId,
            patient_id=request.patientId or "hl7-patient",
            raw_payload={"hl7Message": request.hl7Message},
            consent_accepted=request.consentAccepted,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return snapshot


@app.post("/workflow/ingest/cda")
async def workflow_ingest_cda(request: CdaIngestRequest) -> dict[str, Any]:
    try:
        snapshot = await run_workflow_pipeline(
            service=workflow_service,
            source_type="cda",
            source_id=request.sourceId,
            patient_id=request.patientId or "cda-patient",
            raw_payload={
                "cdaXml": request.cdaXml,
                "xpathMap": request.xpathMap,
            },
            consent_accepted=request.consentAccepted,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return snapshot


@app.post("/workflow/ingest/csv")
async def workflow_ingest_csv(request: CsvIngestRequest) -> dict[str, Any]:
    try:
        snapshot = await run_workflow_pipeline(
            service=workflow_service,
            source_type="csv",
            source_id=request.sourceId,
            patient_id=request.patientId or "csv-patient",
            raw_payload={
                "csvText": request.csvText,
                "mapping": request.mapping,
            },
            consent_accepted=request.consentAccepted,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return snapshot


>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f
@app.post("/chat/preflight")
# async def chat_preflight(request: SafetyCheckRequest) -> dict[str, Any]:
async def chat_preflight(request: SafetyCheckRequest) -> dict[str, Any]:
    # result = run_preflight_safety_check(
    result = run_preflight_safety_check(
        # request.text,
        request.text,
        # pain_threshold=settings.preflight_pain_threshold,
        pain_threshold=settings.preflight_pain_threshold,
    # )
    )
    # return result.model_dump(mode="json")
    return result.model_dump(mode="json")


<<<<<<< HEAD
# @app.post("/workflow/unlock-check")
=======
@app.get("/voice/asr/probe")
async def voice_asr_probe() -> dict[str, Any]:
    if not settings.asr_base_url:
        raise HTTPException(status_code=500, detail="ASR_BASE_URL is not configured.")

    parsed = urlparse(settings.asr_base_url)
    host = parsed.hostname or ""
    scheme = parsed.scheme or "http"
    port = parsed.port or (443 if scheme == "https" else 80)

    dns_resolved = False
    tcp_reachable = False
    http_reachable = False
    http_status = 0
    errors: list[str] = []

    try:
        loop = asyncio.get_running_loop()
        await loop.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        dns_resolved = True
    except Exception as exc:  # noqa: BLE001
        errors.append(f"dns:{exc}")

    if dns_resolved:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5.0)
            writer.close()
            await writer.wait_closed()
            tcp_reachable = True
        except Exception as exc:  # noqa: BLE001
            errors.append(f"tcp:{exc}")

    headers: dict[str, str] = {}
    if settings.asr_auth_token:
        token = settings.asr_auth_token
        if settings.asr_auth_header.lower() == "authorization" and not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
        headers[settings.asr_auth_header] = token

    health_path = settings.asr_health_path or "/v1/health/ready"
    if not health_path.startswith("/"):
        health_path = f"/{health_path}"
    health_url = f"{settings.asr_base_url.rstrip('/')}{health_path}"

    try:
        timeout = httpx.Timeout(float(max(settings.asr_timeout_sec, 1)))
        async with httpx.AsyncClient(timeout=timeout, verify=settings.asr_verify_tls) as client:
            response = await client.get(health_url, headers=headers)
        http_status = response.status_code
        http_reachable = True
    except Exception as exc:  # noqa: BLE001
        errors.append(f"http:{exc}")

    return {
        "configured": True,
        "baseUrl": settings.asr_base_url,
        "healthUrl": health_url,
        "verifyTls": settings.asr_verify_tls,
        "host": host,
        "port": port,
        "dnsResolved": dns_resolved,
        "tcpReachable": tcp_reachable,
        "httpReachable": http_reachable,
        "httpStatus": http_status,
        "errors": errors,
    }


@app.post("/voice/transcribe")
async def voice_transcribe(request: AsrTranscribeRequest) -> dict[str, Any]:
    try:
        audio_bytes = decode_base64_audio(request.audioBase64)
        asr_result = await transcribe_audio(
            settings=settings,
            audio_bytes=audio_bytes,
            mime_type=request.mimeType,
            file_name=request.fileName,
            language=request.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        raise HTTPException(status_code=502, detail=f"ASR upstream error: {detail}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"ASR transcription failed: {exc}") from exc

    response = AsrTranscribeResponse(
        text=asr_result["text"],
        language=asr_result["language"],
        model=asr_result["model"],
    )
    return response.model_dump(mode="json")


>>>>>>> 8cef2868d3614e914651eb0379e3ae5755bfab2f
@app.post("/workflow/unlock-check")
# async def workflow_unlock_check(request: WorkflowUnlockRequest) -> dict[str, Any]:
async def workflow_unlock_check(request: WorkflowUnlockRequest) -> dict[str, Any]:
    # result = await workflow_service.check_unlock(
    result = await workflow_service.check_unlock(
        # source_id=request.sourceId,
        source_id=request.sourceId,
        # patient_id=request.patientId,
        patient_id=request.patientId,
        # consent_accepted=request.consentAccepted,
        consent_accepted=request.consentAccepted,
    # )
    )
    # return result.model_dump(mode="json")
    return result.model_dump(mode="json")


# def _safe_name(full: str) -> str:
def _safe_name(full: str) -> str:
    # parts = (full or "").split()
    parts = (full or "").split()
    # if not parts:
    if not parts:
        # return "Unknown"
        return "Unknown"
    # if len(parts) == 1:
    if len(parts) == 1:
        # return parts[0]
        return parts[0]
    # return f"{parts[0]} {parts[-1][0]}."
    return f"{parts[0]} {parts[-1][0]}."


# def _format_next_appt(appointments: list[dict[str, Any]]) -> str | None:
def _format_next_appt(appointments: list[dict[str, Any]]) -> str | None:
    # for appt in appointments:
    for appt in appointments:
        # start = appt.get("start") or appt.get("description")
        start = appt.get("start") or appt.get("description")
        # if start:
        if start:
            # return str(start)
            return str(start)
    # return None
    return None


# @app.get("/session/{session_id}/context-summary")
@app.get("/session/{session_id}/context-summary")
# async def session_context_summary(
async def session_context_summary(
    # session_id: str,
    session_id: str,
    # patient_id: str = Query(..., description="Patient identifier for this session"),
    patient_id: str = Query(..., description="Patient identifier for this session"),
# ) -> dict[str, Any]:
) -> dict[str, Any]:
    # ctx = await session_cache.get_context(session_id, patient_id)
    ctx = await session_cache.get_context(session_id, patient_id)
    # if not ctx:
    if not ctx:
        # raise HTTPException(status_code=404, detail="No cached PatientContext for this session.")
        raise HTTPException(status_code=404, detail="No cached PatientContext for this session.")
    # token = await session_cache.get_token(session_id)
    token = await session_cache.get_token(session_id)

    # demographics = ctx.get("demographics") or {}
    demographics = ctx.get("demographics") or {}
    # summary = ContextSummary(
    summary = ContextSummary(
        # patient_name=_safe_name(demographics.get("fullName", "")),
        patient_name=_safe_name(demographics.get("fullName", "")),
        # medication_count=len(ctx.get("medications", [])),
        medication_count=len(ctx.get("medications", [])),
        # condition_count=len(ctx.get("conditions", [])),
        condition_count=len(ctx.get("conditions", [])),
        # allergy_count=len(ctx.get("allergies", [])),
        allergy_count=len(ctx.get("allergies", [])),
        # has_alert=len(ctx.get("allergyConflicts", [])) > 0,
        has_alert=len(ctx.get("allergyConflicts", [])) > 0,
        # alert_message="Allergy conflict detected" if len(ctx.get("allergyConflicts", [])) > 0 else None,
        alert_message="Allergy conflict detected" if len(ctx.get("allergyConflicts", [])) > 0 else None,
        # next_appointment=_format_next_appt(ctx.get("appointments", [])),
        next_appointment=_format_next_appt(ctx.get("appointments", [])),
        # session_expires_at=(token.get("expiry") if isinstance(token, dict) else None),
        session_expires_at=(token.get("expiry") if isinstance(token, dict) else None),
        # data_source=ctx.get("sourceType"),
        data_source=ctx.get("sourceType"),
    # )
    )
    # return summary.model_dump(mode="json")
    return summary.model_dump(mode="json")
