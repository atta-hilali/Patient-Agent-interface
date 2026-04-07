from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections import deque
from typing import AsyncIterator, Iterable

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from openai import AsyncOpenAI

from app.config import get_settings

_settings = get_settings()
MEDGEMMA_BASE_URL = _settings.medgemma_base_url or "http://localhost:8001/v1"
MEDGEMMA_API_KEY = _settings.medgemma_api_key or "not-used"
MEDGEMMA_MODE = (_settings.medgemma_mode or "mvp").lower()
MVP_MODEL = _settings.medgemma_mvp_model or "google/medgemma-4b-it"
SPRINT3_MODEL = _settings.medgemma_sprint3_model or "google/medgemma-27b-it"
MAX_TOKENS = int(_settings.medgemma_max_tokens or 1024)
DEFAULT_MODEL = SPRINT3_MODEL if MEDGEMMA_MODE in {"27b", "sprint3", "production"} else MVP_MODEL
VLLM = AsyncOpenAI(base_url=MEDGEMMA_BASE_URL, api_key=MEDGEMMA_API_KEY)
_latencies_ms: deque[float] = deque(maxlen=200)
_resolved_model_id: str | None = None
logger = logging.getLogger(__name__)

# LangSmith is intentionally disabled in production because this project handles
# clinical content and may include PHI. In dev/staging it can be enabled for tracing.
if os.getenv("LANGSMITH_API_KEY") and os.getenv("APP_ENV", "dev").lower() != "production":
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


def _record_latency(start: float) -> None:
    _latencies_ms.append((time.perf_counter() - start) * 1000)


def get_llm_health() -> dict:
    ordered = sorted(_latencies_ms)
    p99 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))] if ordered else 0.0
    return {
        "sample_count": len(ordered),
        "p99_ms": round(p99, 2),
        "alert": p99 > 3000,
        "base_url": MEDGEMMA_BASE_URL,
        "model": DEFAULT_MODEL,
        "resolved_model": _resolved_model_id or DEFAULT_MODEL,
        "mode": MEDGEMMA_MODE,
    }


def get_vllm_deployment_command() -> str:
    if DEFAULT_MODEL == SPRINT3_MODEL:
        return (
            "vllm serve google/medgemma-27b-it "
            "--tensor-parallel-size 2 "
            "--max-model-len 8192 "
            "--enable-chunked-prefill "
            "--dtype bfloat16 "
            "--port 8001"
        )
    return (
        "vllm serve google/medgemma-4b-it "
        "--max-model-len 8192 "
        "--enable-chunked-prefill "
        "--dtype bfloat16 "
        "--port 8001"
    )


TOOL_PLANNER_PROMPT = (
    "You are a clinical tool planner.\n"
    "Choose only the tools that are necessary to answer the patient safely.\n"
    "Return JSON with this shape:\n"
    '{"tool_calls":[{"name":"tool_name","args":{"arg":"value"}}]}\n'
    "Rules:\n"
    "- Use only the provided tool names.\n"
    "- Use [] when no tool is needed.\n"
    "- For get_* cached context tools, always include session_id.\n"
    "- For check_drug_interaction, include session_id and any known rxcuis if available.\n"
    "- For search_guidelines, include query.\n"
    "- For analyze_image, include image_b64 and patient_context_summary when an image is present.\n"
    "- For escalate_to_human, include session_id and reason."
)


async def _with_retry(factory, *, attempts: int = 2):
    # The vLLM endpoint is local infrastructure, so a short retry helps smooth over
    # transient startup hiccups without hiding persistent failures.
    for attempt in range(attempts):
        start = time.perf_counter()
        try:
            result = await factory()
            _record_latency(start)
            return result
        except Exception:  # noqa: BLE001
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(0.2 * (attempt + 1))


def _status_code_from_exception(exc: Exception) -> int | None:
    value = getattr(exc, "status_code", None)
    if isinstance(value, int):
        return value
    text = str(exc)
    match = re.search(r"\b(4\d\d|5\d\d)\b", text)
    return int(match.group(1)) if match else None


def _extract_text_fragments(payload: object) -> list[str]:
    fragments: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).strip().lower()
            if isinstance(value, str) and value.strip() and (
                lowered in {"text", "answer", "message", "response", "response_text", "output"}
                or lowered.endswith("text")
            ):
                fragments.append(value.strip())
            elif isinstance(value, (dict, list)):
                fragments.extend(_extract_text_fragments(value))
    elif isinstance(payload, list):
        for item in payload:
            fragments.extend(_extract_text_fragments(item))
    return fragments


class _LegacyDelta:
    def __init__(self, content: str) -> None:
        self.content = content


class _LegacyChoice:
    def __init__(self, content: str) -> None:
        self.delta = _LegacyDelta(content)


class _LegacyChunk:
    def __init__(self, content: str) -> None:
        self.choices = [_LegacyChoice(content)]


async def _single_chunk_stream(text: str) -> AsyncIterator[_LegacyChunk]:
    yield _LegacyChunk(text)


async def _resolve_model_id() -> str:
    global _resolved_model_id
    if _resolved_model_id:
        return _resolved_model_id

    preferred = DEFAULT_MODEL
    try:
        listing = await VLLM.models.list()
        available = [item.id for item in getattr(listing, "data", []) if getattr(item, "id", None)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not list MedGemma models at %s: %r", MEDGEMMA_BASE_URL, exc)
        _resolved_model_id = preferred
        return _resolved_model_id

    if not available:
        _resolved_model_id = preferred
        return _resolved_model_id

    if preferred in available:
        _resolved_model_id = preferred
        return _resolved_model_id

    preferred_l = preferred.lower()
    scale_match = re.search(r"(\d+)\s*b", preferred_l)
    if scale_match:
        scale_token = f"{scale_match.group(1)}b"
        for item in available:
            if scale_token in item.lower():
                _resolved_model_id = item
                logger.warning(
                    "Configured model '%s' not found. Using discovered model '%s'. Available=%s",
                    preferred,
                    item,
                    ",".join(available),
                )
                return _resolved_model_id

    _resolved_model_id = available[0]
    logger.warning(
        "Configured model '%s' not found. Using first discovered model '%s'. Available=%s",
        preferred,
        _resolved_model_id,
        ",".join(available),
    )
    return _resolved_model_id


async def _call_legacy_chat(system_prompt: str, messages: list) -> AsyncIterator[_LegacyChunk]:
    payload = {
        "messages": [{"role": "system", "content": system_prompt}, *_serialize_messages(messages)],
        "max_new_tokens": MAX_TOKENS,
        "temperature": 0.1,
        "top_p": 0.9,
        "top_k": 50,
        "repetition_penalty": 1.1,
        "stream": False,
    }
    endpoint = f"{MEDGEMMA_BASE_URL.rstrip('/')}/chat"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        data = response.json()

    parts = _extract_text_fragments(data)
    text = " ".join(dict.fromkeys(parts)).strip()
    if not text:
        text = json.dumps(data, ensure_ascii=False)
    return _single_chunk_stream(text)


async def call_medgemma(
    system_prompt: str,
    messages: list,
    tools: list | None = None,
) -> AsyncIterator:
    model_id = await _resolve_model_id()
    payload = {
        "model": model_id,
        "messages": [{"role": "system", "content": system_prompt}] + _serialize_messages(messages),
        "tools": tools,
        "temperature": 0.1,
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "response_format": {"type": "json_object"},
    }
    try:
        return await _with_retry(lambda: VLLM.chat.completions.create(**payload))
    except Exception as exc:  # noqa: BLE001
        status = _status_code_from_exception(exc)
        if status in {400, 404, 415, 422}:
            logger.warning(
                "OpenAI chat/completions incompatible for %s (status=%s). Falling back to legacy /chat.",
                MEDGEMMA_BASE_URL,
                status,
            )
            return await _call_legacy_chat(system_prompt, messages)
        raise


async def call_medgemma_intent(prompt: str, question: str) -> str:
    model_id = await _resolve_model_id()
    try:
        response = await _with_retry(
            lambda: VLLM.chat.completions.create(
                model=model_id,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": question}],
                temperature=0.0,
                max_tokens=3,
            )
        )
        return response.choices[0].message.content or "tools"
    except Exception:  # noqa: BLE001
        return "tools"


async def call_medgemma_tool_planner(system_prompt: str, messages: list, tool_catalog: list[dict]) -> list[dict]:
    model_id = await _resolve_model_id()
    catalog_json = json.dumps(tool_catalog, ensure_ascii=True)
    try:
        response = await _with_retry(
            lambda: VLLM.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": TOOL_PLANNER_PROMPT},
                    {"role": "system", "content": f"Clinical context:\n{system_prompt}"},
                    {"role": "system", "content": f"Available tools:\n{catalog_json}"},
                    *_serialize_messages(messages),
                ],
                temperature=0.0,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
        )
    except Exception:  # noqa: BLE001
        return []
    content = response.choices[0].message.content or '{"tool_calls":[]}'
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return []
    tool_calls = parsed.get("tool_calls", [])
    return tool_calls if isinstance(tool_calls, list) else []


async def call_medgemma_vision(prompt: str, image_b64: str) -> str:
    model_id = await _resolve_model_id()
    try:
        response = await _with_retry(
            lambda: VLLM.chat.completions.create(
                model=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=512,
            )
        )
        return response.choices[0].message.content or ""
    except Exception:  # noqa: BLE001
        return ""


def extract_complete_sentences(text: str) -> tuple[list[str], str]:
    matches = list(re.finditer(r"[^.!?]+[.!?]+(?:\s+|$)", text))
    if not matches:
        return [], text
    sentences = [match.group(0).strip() for match in matches]
    remainder = text[matches[-1].end() :]
    return sentences, remainder


def iter_sentence_fragments(text: str) -> Iterable[str]:
    sentences, remainder = extract_complete_sentences(text)
    for sentence in sentences:
        yield sentence
    if remainder.strip():
        yield remainder.strip()


def _serialize_messages(messages: list) -> list[dict]:
    serialized: list[dict] = []
    for message in messages:
        if isinstance(message, dict):
            serialized.append(message)
        elif isinstance(message, HumanMessage):
            serialized.append({"role": "user", "content": message.content})
        elif isinstance(message, AIMessage):
            serialized.append({"role": "assistant", "content": message.content})
        elif isinstance(message, SystemMessage):
            serialized.append({"role": "system", "content": message.content})
        elif isinstance(message, BaseMessage):
            serialized.append({"role": "user", "content": message.content})
        else:
            serialized.append({"role": "user", "content": str(message)})
    return serialized
