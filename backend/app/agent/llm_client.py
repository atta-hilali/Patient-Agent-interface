from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import deque
from typing import AsyncIterator, Iterable

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


async def call_medgemma(
    system_prompt: str,
    messages: list,
    tools: list | None = None,
) -> AsyncIterator:
    return await _with_retry(
        lambda: VLLM.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[{"role": "system", "content": system_prompt}] + _serialize_messages(messages),
            tools=tools,
            temperature=0.1,
            max_tokens=MAX_TOKENS,
            stream=True,
            response_format={"type": "json_object"},
        )
    )


async def call_medgemma_intent(prompt: str, question: str) -> str:
    response = await _with_retry(
        lambda: VLLM.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": question}],
            temperature=0.0,
            max_tokens=3,
        )
    )
    return response.choices[0].message.content or "tools"


async def call_medgemma_tool_planner(system_prompt: str, messages: list, tool_catalog: list[dict]) -> list[dict]:
    catalog_json = json.dumps(tool_catalog, ensure_ascii=True)
    response = await _with_retry(
        lambda: VLLM.chat.completions.create(
            model=DEFAULT_MODEL,
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
    content = response.choices[0].message.content or '{"tool_calls":[]}'
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return []
    tool_calls = parsed.get("tool_calls", [])
    return tool_calls if isinstance(tool_calls, list) else []


async def call_medgemma_vision(prompt: str, image_b64: str) -> str:
    response = await _with_retry(
        lambda: VLLM.chat.completions.create(
            model=DEFAULT_MODEL,
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
