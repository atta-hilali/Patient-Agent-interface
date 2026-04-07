# import json
import json
import logging
# from base64 import b64encode
from base64 import b64encode

# from fastapi import APIRouter, Cookie, HTTPException, Request, UploadFile
from fastapi import APIRouter, Cookie, HTTPException, Request, UploadFile
# from fastapi.responses import StreamingResponse
from fastapi.responses import StreamingResponse

# from app.agent.pipeline import run_agent_turn
from app.agent.pipeline import run_agent_turn
# from app.agent_io import PatientInput
from app.agent_io import PatientInput
# from app.config import get_settings
from app.config import get_settings
# from app.cache import get_session_cache
from app.cache import get_session_cache
# from app.models import AuthToken
from app.models import AuthToken


# router = APIRouter()
router = APIRouter()
logger = logging.getLogger(__name__)


# async def _build_patient_input(request: Request, cookie_session_id: str | None) -> PatientInput:
async def _build_patient_input(request: Request, cookie_session_id: str | None) -> PatientInput:
    # content_type = request.headers.get("content-type", "").lower()
    content_type = request.headers.get("content-type", "").lower()
    # if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        # form = await request.form()
        form = await request.form()
        # upload = form.get("image")
        upload = form.get("image")
        # image_b64 = str(form.get("image_b64") or "") or None
        image_b64 = str(form.get("image_b64") or "") or None
        # if isinstance(upload, UploadFile):
        if isinstance(upload, UploadFile):
            # image_bytes = await upload.read()
            image_bytes = await upload.read()
            # image_b64 = b64encode(image_bytes).decode("ascii") if image_bytes else None
            image_b64 = b64encode(image_bytes).decode("ascii") if image_bytes else None
        # payload = PatientInput(
        payload = PatientInput(
            # session_id=str(form.get("session_id") or cookie_session_id or ""),
            session_id=str(form.get("session_id") or cookie_session_id or ""),
            # message=str(form.get("message") or ""),
            message=str(form.get("message") or ""),
            # image_b64=image_b64,
            image_b64=image_b64,
            # modality=str(form.get("modality") or ("image" if image_b64 else "text")),
            modality=str(form.get("modality") or ("image" if image_b64 else "text")),
        # )
        )
        # return payload
        return payload

    # data = await request.json()
    data = await request.json()
    # payload = PatientInput.model_validate(data)
    payload = PatientInput.model_validate(data)
    # if not payload.modality:
    if not payload.modality:
        # payload.modality = "image" if payload.image_b64 else "text"
        payload.modality = "image" if payload.image_b64 else "text"
    # if not payload.session_id and cookie_session_id:
    if not payload.session_id and cookie_session_id:
        # payload.session_id = cookie_session_id
        payload.session_id = cookie_session_id
    # return payload
    return payload


# @router.post("/agent/chat")
@router.post("/agent/chat")
# async def agent_chat(request: Request, session_id: str = Cookie(default=None)):
async def agent_chat(request: Request, session_id: str = Cookie(default=None)):
    # payload = await _build_patient_input(request, session_id)
    payload = await _build_patient_input(request, session_id)
    # # Support the unified payload shape from the frontend while still allowing the
    # Support the unified payload shape from the frontend while still allowing the
    # # authenticated session cookie to remain the primary source of truth.
    # authenticated session cookie to remain the primary source of truth.
    # resolved_session_id = payload.session_id or session_id
    resolved_session_id = payload.session_id or session_id
    # if not resolved_session_id:
    if not resolved_session_id:
        # raise HTTPException(status_code=401, detail="Not authenticated")
        raise HTTPException(status_code=401, detail="Not authenticated")

    # settings = get_settings()
    settings = get_settings()
    # cache = get_session_cache()
    cache = get_session_cache()
    # raw_token = await cache.get_token(resolved_session_id)
    raw_token = await cache.get_token(resolved_session_id)
    # if not raw_token:
    if not raw_token:
        # raise HTTPException(status_code=401, detail="Session expired - please log in again")
        raise HTTPException(status_code=401, detail="Session expired - please log in again")

    # token = AuthToken.model_validate(raw_token)
    token = AuthToken.model_validate(raw_token)
    # # Downstream pipeline code expects the resolved session id to already be on the
    # Downstream pipeline code expects the resolved session id to already be on the
    # # request body, regardless of whether the frontend sent it explicitly or via cookie.
    # request body, regardless of whether the frontend sent it explicitly or via cookie.
    # payload.session_id = resolved_session_id
    payload.session_id = resolved_session_id

    # async def sse_stream():
    async def sse_stream():
        try:
            # async for event in run_agent_turn(payload, token):
            async for event in run_agent_turn(payload, token):
                # data = event if isinstance(event, dict) else event.model_dump()
                data = event if isinstance(event, dict) else event.model_dump()
                # yield f"data: {json.dumps(data)}\n\n"
                yield f"data: {json.dumps(data)}\n\n"
        except HTTPException as exc:
            logger.warning("Agent stream HTTPException: %s", exc.detail)
            error_event = {"type": "error", "text": exc.detail or str(exc), "turn_complete": True}
            yield f"data: {json.dumps(error_event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent stream failed unexpectedly.")
            error_event = {"type": "error", "text": f"Agent failed: {exc}", "turn_complete": True}
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            # yield "data: [DONE]\n\n"
            yield "data: [DONE]\n\n"

    # return StreamingResponse(
    return StreamingResponse(
        # sse_stream(),
        sse_stream(),
        # media_type="text/event-stream",
        media_type="text/event-stream",
        # headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    # )
    )
