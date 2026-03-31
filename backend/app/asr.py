from __future__ import annotations

import base64
from typing import Any

import httpx

from .config import Settings


def decode_base64_audio(value: str) -> bytes:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("audioBase64 is empty.")

    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]

    normalized = raw.replace("\n", "").replace(" ", "")
    padding = "=" * (-len(normalized) % 4)
    normalized = f"{normalized}{padding}"

    try:
        data = base64.b64decode(normalized, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("audioBase64 is not valid base64.") from exc

    if not data:
        raise ValueError("Decoded audio payload is empty.")
    return data


def _build_headers(settings: Settings) -> dict[str, str]:
    if not settings.asr_auth_token:
        return {}

    header_name = settings.asr_auth_header or "Authorization"
    token = settings.asr_auth_token
    if header_name.lower() == "authorization" and not token.lower().startswith("bearer "):
        token = f"Bearer {token}"
    return {header_name: token}


TEXT_KEYS = {
    "text",
    "transcript",
    "utterance",
    "prediction",
    "pred_text",
    "normalized_text",
    "display_text",
    "result",
}


def _key_looks_like_text(key: str) -> bool:
    lowered = (key or "").strip().lower()
    if lowered in TEXT_KEYS:
        return True
    if "transcript" in lowered:
        return True
    if lowered.endswith("text"):
        return True
    return False


def _collect_text_fragments(payload: Any) -> list[str]:
    fragments: list[str] = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, str) and value.strip() and _key_looks_like_text(key):
                fragments.append(value.strip())
                continue

            if isinstance(value, (list, dict)):
                fragments.extend(_collect_text_fragments(value))

    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, (list, dict)):
                fragments.extend(_collect_text_fragments(item))
            elif isinstance(item, str) and item.strip():
                fragments.append(item.strip())

    return fragments


def _extract_text(payload: Any) -> str:
    pieces = _collect_text_fragments(payload)
    if not pieces:
        return ""
    seen: set[str] = set()
    deduped: list[str] = []
    for piece in pieces:
        if piece in seen:
            continue
        seen.add(piece)
        deduped.append(piece)
    return " ".join(deduped).strip()


def _extract_language(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        for key in ("language", "language_code"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def _extract_model(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("model", "model_name"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
    return ""


async def transcribe_audio(
    *,
    settings: Settings,
    audio_bytes: bytes,
    mime_type: str,
    file_name: str,
    language: str = "",
) -> dict[str, str]:
    if not settings.asr_base_url:
        raise RuntimeError("ASR_BASE_URL is not configured.")

    path = settings.asr_transcribe_path or "/v1/audio/transcriptions"
    if not path.startswith("/"):
        path = f"/{path}"
    endpoint = f"{settings.asr_base_url.rstrip('/')}{path}"

    request_language = (language or settings.asr_default_language or "en-US").strip()

    files = {
        "file": (
            file_name or "voice.wav",
            audio_bytes,
            mime_type or "audio/wav",
        )
    }
    data = {"language": request_language}
    headers = _build_headers(settings)
    timeout = httpx.Timeout(float(max(settings.asr_timeout_sec, 1)))

    async with httpx.AsyncClient(timeout=timeout, verify=settings.asr_verify_tls) as client:
        response = await client.post(endpoint, data=data, files=files, headers=headers)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        payload: Any = response.json()
        transcript = _extract_text(payload)
        if not transcript:
            if isinstance(payload, dict):
                keys = ", ".join(sorted(str(key) for key in payload.keys()))
                raise RuntimeError(f"ASR response did not contain transcript text. Top-level keys: {keys}")
            raise RuntimeError("ASR response did not contain transcript text.")
        return {
            "text": transcript,
            "language": _extract_language(payload, request_language),
            "model": _extract_model(payload),
        }

    transcript = (response.text or "").strip()
    if not transcript:
        raise RuntimeError("ASR response was empty.")
    return {
        "text": transcript,
        "language": request_language,
        "model": "",
    }
