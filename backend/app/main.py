import asyncio
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.responses import RedirectResponse

from .asr import decode_base64_audio, transcribe_audio
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
    AsrTranscribeRequest,
    AsrTranscribeResponse,
    CdaIngestRequest,
    CsvIngestRequest,
    Hl7IngestRequest,
    NormalizeRequest,
    SafetyCheckRequest,
    WorkflowIngestRequest,
    WorkflowUnlockRequest,
)
from .hl7_mllp import Hl7MllpListener
from .oauth_state import OAuthStateStore
from .safety import run_preflight_safety_check
from .workflow import WorkflowService, run_workflow_pipeline


settings = get_settings()
oauth_state_store = OAuthStateStore(ttl_sec=settings.oauth_state_ttl_sec)
workflow_cache = WorkflowCache(settings=settings)
workflow_service = WorkflowService(settings=settings, cache=workflow_cache)
hl7_listener: Hl7MllpListener | None = None
hl7_recent_messages: list[dict[str, Any]] = []

app = FastAPI(title=settings.app_name)

allow_origins = settings.allowed_origins if settings.allowed_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": settings.app_name, "env": settings.env}


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "ok": True,
        "service": settings.app_name,
        "message": "Backend is running. Use /docs, /health, /auth/epic/start, /workflow/ingest, /workflow/ingest/csv, /voice/asr/probe, /voice/transcribe.",
    }


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/workflow/sources")
async def workflow_sources() -> dict[str, Any]:
    return {"supportedSourceTypes": workflow_service.adapter_registry.supported_source_types()}


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


@app.post("/chat/preflight")
async def chat_preflight(request: SafetyCheckRequest) -> dict[str, Any]:
    result = run_preflight_safety_check(
        request.text,
        pain_threshold=settings.preflight_pain_threshold,
    )
    return result.model_dump(mode="json")


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


@app.post("/workflow/unlock-check")
async def workflow_unlock_check(request: WorkflowUnlockRequest) -> dict[str, Any]:
    result = await workflow_service.check_unlock(
        source_id=request.sourceId,
        patient_id=request.patientId,
        consent_accepted=request.consentAccepted,
    )
    return result.model_dump(mode="json")
