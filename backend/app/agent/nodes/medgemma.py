# import json
import json
import logging

# from app.agent.llm_client import call_medgemma
from app.agent.llm_client import call_medgemma
# from app.agent.state import AgentState
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def _extract_chunk_text(chunk: object) -> str:
    # OpenAI-compatible chunk shape.
    choices = getattr(chunk, "choices", None)
    if isinstance(choices, list) and choices:
        first = choices[0]
        delta = getattr(first, "delta", None)
        delta_text = getattr(delta, "content", None)
        if isinstance(delta_text, str) and delta_text:
            return delta_text

        message = getattr(first, "message", None)
        message_text = getattr(message, "content", None)
        if isinstance(message_text, str) and message_text:
            return message_text

    # Legacy/custom stream shape from external gateways.
    if isinstance(chunk, dict):
        if chunk.get("type") == "token":
            token = chunk.get("text", "")
            return token if isinstance(token, str) else ""
        for key in ("text", "content", "response_text", "answer", "message"):
            value = chunk.get(key)
            if isinstance(value, str) and value.strip():
                return value

    # Pydantic/dataclass style objects from some SDKs.
    for attr in ("text", "content", "response_text"):
        value = getattr(chunk, attr, None)
        if isinstance(value, str) and value.strip():
            return value

    model_dump = getattr(chunk, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
            if isinstance(dumped, dict):
                return _extract_chunk_text(dumped)
        except Exception:  # noqa: BLE001
            return ""

    return ""


async def medgemma_node(state: AgentState) -> dict:
    system_prompt = state["system_prompt"]
    if not system_prompt:
        return {"escalation_flag": True, "escalation_reason": "system_prompt_missing"}

    history_summary = state.get("history_summary", "").strip()
    if history_summary:
        system_prompt = f"{system_prompt}\n\nOlder conversation summary:\n{history_summary}"

    messages = list(state["messages"])
    if state.get("tool_results"):
        tool_text = "\n".join(f"[{name} result]\n{value}" for name, value in state["tool_results"].items())
        system_prompt = f"{system_prompt}\n\nTool data:\n{tool_text}"

    full = ""
    try:
        stream = await call_medgemma(system_prompt, messages)
        async for chunk in stream:
            full += _extract_chunk_text(chunk)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MedGemma call failed, returning fallback message: %r", exc)
        return {
            "draft_response": "I am having trouble reaching the clinical model right now. Please try again in a few seconds.",
            "raw_citations": [],
        }

    raw = (full or "").strip()
    if not raw:
        logger.warning("MedGemma returned an empty output stream.")
        return {
            "draft_response": "I am having trouble generating a response right now. Please try again in a few seconds.",
            "raw_citations": [],
        }

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # External MedGemma gateways may return plain text instead of strict JSON.
        return {"draft_response": raw, "raw_citations": []}

    if isinstance(parsed, str):
        text = parsed.strip()
        return {"draft_response": text or raw, "raw_citations": []}

    if not isinstance(parsed, dict):
        return {"draft_response": raw, "raw_citations": []}

    if parsed.get("escalation_flag", False):
        return {
            "escalation_flag": True,
            "escalation_reason": "llm_self_escalation",
            "stop_severity": "HIGH",
        }

    response_text = parsed.get("response_text")
    if not isinstance(response_text, str) or not response_text.strip():
        for key in ("answer", "text", "message"):
            candidate = parsed.get(key)
            if isinstance(candidate, str) and candidate.strip():
                response_text = candidate
                break
    if not isinstance(response_text, str) or not response_text.strip():
        response_text = raw

    citations = parsed.get("citations", [])
    if not isinstance(citations, list):
        citations = []

    return {
        "draft_response": response_text.strip(),
        "raw_citations": citations,
    }
