from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

import httpx

from app.writeback import get_writeback_service

logger = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("ESCALATION_WEBHOOK_URL", "")
SMS_URL = os.getenv("SMS_ALERT_URL", "")
WEBHOOK_SECRET = os.getenv("ESCALATION_WEBHOOK_SECRET", os.getenv("WEBHOOK_SECRET", ""))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def write_fhir_flag(patient_id: str, trigger: str, severity: str, session_id: str) -> bool:
    """
    Backward-compatible wrapper used by the existing pipeline.
    The actual transport is now routed through the connector adapter abstraction.
    """
    result = await get_writeback_service().write_flag(
        session_id=session_id,
        patient_id=patient_id,
        reason=trigger,
        severity=severity,
    )
    return result.ok


async def write_fhir_observation(patient_id: str, trigger: str, session_id: str) -> bool:
    score = ""
    for part in (trigger or "").split(":"):
        token = part.strip()
        if token.isdigit():
            score = token
            break

    result = await get_writeback_service().write_observation(
        session_id=session_id,
        patient_id=patient_id,
        loinc_code="72514-3",
        value=score or trigger or "1",
        unit="score",
    )
    return result.ok


async def write_session_summary(patient_id: str, summary: str, session_id: str) -> bool:
    result = await get_writeback_service().write_session_summary(
        session_id=session_id,
        patient_id=patient_id,
        summary=summary,
    )
    return result.ok


async def fire_webhook(session_id: str, patient_id: str, trigger: str) -> bool:
    if not WEBHOOK_URL:
        return False

    payload = json.dumps(
        {
            "session_id": session_id,
            "patient_id": patient_id,
            "trigger": trigger,
            "timestamp": _now_iso(),
        },
        separators=(",", ":"),
        ensure_ascii=True,
    )
    signature = hmac.new(WEBHOOK_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Veldooc-Signature": signature}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(WEBHOOK_URL, content=payload, headers=headers)
            response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Escalation webhook failed: %r", exc)
        return False


async def send_sms_alert(session_id: str, trigger: str) -> bool:
    if not SMS_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                SMS_URL,
                json={
                    "session_id": session_id,
                    "trigger": trigger,
                    "timestamp": _now_iso(),
                },
            )
            response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Escalation SMS failed: %r", exc)
        return False

