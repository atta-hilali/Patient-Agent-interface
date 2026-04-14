from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import agent_graph
from app.agent.llm_client import extract_complete_sentences
from app.agent.state import AgentState
from app.agent_io import PatientInput
from app.cache import read_context, read_prompt
from app.config import get_settings
from app.connectors import ConnectorStore
from app.models import AuthToken
from app.safety.escalation import fire_webhook, send_sms_alert, write_fhir_flag, write_fhir_observation
from app.safety.nemoguard_input import check_input_safety
from app.safety.preflight import AllergyIndex, get_preflight_checker


# Fixed escalation copy is loaded once and reused across preflight, input safety,
# and output safety paths so these responses never depend on an LLM.
_BASE_DIR = Path(__file__).resolve().parents[2]
_ESCALATION_PATH = _BASE_DIR / "config" / "escalation_messages.json"
if _ESCALATION_PATH.exists():
    ESCALATION_MSGS = json.loads(_ESCALATION_PATH.read_text(encoding="utf-8"))
else:
    ESCALATION_MSGS = {
        "general_escalation": {
            "text": "I am escalating this to your care team now for a safer follow-up.",
        },
        "topic_control_general": {
            "text": "For this question, please contact your clinician directly.",
        },
    }
MAX_TURNS = 10
_history: dict[str, list] = {}
_history_summaries: dict[str, str] = {}
_connector_store: ConnectorStore | None = None
logger = logging.getLogger(__name__)

# Input safety should only hard-stop on clearly critical categories.
# Less-critical moderation categories can continue and will still be checked
# again on model output by the mandatory output safety node.
CRITICAL_INPUT_SAFETY_CATEGORIES = {
    "self_harm",
    "suicidal",
    "suicide",
    "crisis_language",
    "violence",
    "overdose",
}

_MED_INFO_TERMS = (
    "medication",
    "medications",
    "medicine",
    "medicines",
    "meds",
    "pill",
    "pills",
    "dose",
    "dosage",
)
_MED_CHANGE_PATTERNS = [
    re.compile(r"\b(stop|start|increase|decrease|double|halve|skip)\b", re.IGNORECASE),
    re.compile(r"\b(change|adjust)\b.{0,20}\b(dose|dosage|medication|medications|meds)\b", re.IGNORECASE),
    re.compile(r"\b(can|should)\s+i\s+(stop|change|increase|decrease)\b", re.IGNORECASE),
]


def _is_medication_info_only_query(text: str) -> bool:
    content = (text or "").strip().lower()
    if not content:
        return False
    if not any(term in content for term in _MED_INFO_TERMS):
        return False
    if any(pattern.search(content) for pattern in _MED_CHANGE_PATTERNS):
        return False
    return True


def _normalize_category(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "_")


def _get_connector_store() -> ConnectorStore:
    global _connector_store
    if _connector_store is None:
        _connector_store = ConnectorStore(get_settings())
    return _connector_store


async def _resolve_connector_for_session(clinic_id: str | None):
    store = _get_connector_store()
    requested_id = (clinic_id or "").strip() or "demo-clinic"
    try:
        return await store.get(requested_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        if requested_id != "demo-clinic":
            return await store.get("demo-clinic")
        raise


def _trim_history(session_id: str, messages: list) -> tuple[list, str]:
    # Keep the newest turns verbatim and collapse older ones into a plain-text
    # summary so the graph sees recent detail without unbounded prompt growth.
    if len(messages) <= MAX_TURNS * 2:
        return messages, _history_summaries.get(session_id, "")

    overflow = messages[:-MAX_TURNS * 2]
    kept = messages[-MAX_TURNS * 2 :]
    previous_summary = _history_summaries.get(session_id, "")
    condensed = []
    for message in overflow:
        role = "patient" if isinstance(message, HumanMessage) else "assistant"
        condensed.append(f"{role}: {message.content}")

    merged = "\n".join(part for part in [previous_summary, *condensed] if part).strip()
    _history_summaries[session_id] = merged
    return kept, merged


async def handle_hard_stop(
    session_id: str,
    patient_id: str,
    trigger: str,
    severity: str,
    msg_key: str,
):
    # Hard stops bypass the graph entirely. We emit the deterministic message first
    # and then perform the escalation side effects.
    text = ESCALATION_MSGS.get(msg_key, ESCALATION_MSGS["general_escalation"])["text"]
    yield {"type": "escalation", "text": text, "reason": trigger, "turn_complete": True}
    await write_fhir_flag(patient_id, trigger, severity, session_id)
    if "pain" in trigger:
        await write_fhir_observation(patient_id, trigger, session_id)
    if severity == "HIGH":
        await fire_webhook(session_id, patient_id, trigger)
        await send_sms_alert(session_id, trigger)


async def handle_soft_redirect(msg_key: str, reason: str):
    # Topic-control style blocks do not escalate to emergency workflows, but they
    # still return fixed copy instead of the discarded model draft.
    text = ESCALATION_MSGS.get(msg_key, ESCALATION_MSGS["topic_control_general"])["text"]
    yield {"type": "token", "text": text}
    yield {"type": "done", "text": text, "citations": [], "reason": reason, "turn_complete": True}


async def run_agent_turn(inp: PatientInput, token: AuthToken):
    # Phase 2 turn order:
    # 1. deterministic preflight
    # 2. allergy keyword guard
    # 3. NemoGuard input safety
    # 4. LangGraph agent loop
    # 5. streamed output events
    session_id = inp.session_id
    patient_id = token.patient_id
    ctx = await read_context(session_id, patient_id)
    system_prompt = await read_prompt(session_id)

    if not ctx or not system_prompt:
        yield {"type": "error", "text": "Session context expired. Please refresh.", "turn_complete": True}
        return

    connector = await _resolve_connector_for_session(token.clinic_id)
    clinic_yaml = connector.topic_yaml or "general_medicine"
    preflight_profile = connector.specialty or clinic_yaml or "general_medicine"

    # Step 9 runs before any model call so crisis phrases, high pain scores, and
    # medication-change requests can short-circuit the turn immediately.
    preflight = get_preflight_checker().check(inp.message, profile=preflight_profile)
    if preflight.escalate:
        async for event in handle_hard_stop(
            session_id,
            patient_id,
            preflight.reason or "preflight_block",
            preflight.severity or "HIGH",
            preflight.message_key or "general_escalation",
        ):
            yield event
        return

    # Allergy mentions also stay in the deterministic path so we do not waste
    # latency on requests that should go straight to escalation handling.
    allergen = AllergyIndex(ctx).check_text(inp.message)
    if allergen:
        async for event in handle_hard_stop(
            session_id,
            patient_id,
            f"allergy_mention:{allergen}",
            "HIGH",
            "allergy_in_input",
        ):
            yield event
        return

    # Input NemoGuard is the second safety layer. It only runs once the regex and
    # allergy gates have passed.
    input_safety = await check_input_safety(inp.message, clinic_yaml)
    if not input_safety.safe:
        category = _normalize_category(input_safety.category)

        # If NemoGuard is temporarily unreachable, keep the turn moving with
        # deterministic preflight + output safety still active.
        if input_safety.reason == "nemoguard_unreachable":
            logger.warning(
                "Input safety unavailable for session=%s reason=%s category=%s; continuing turn.",
                session_id,
                input_safety.reason,
                input_safety.category,
            )
        elif input_safety.blocked_by == "content_safety" and category not in CRITICAL_INPUT_SAFETY_CATEGORIES:
            # Avoid over-blocking normal patient utterances at input stage.
            logger.info(
                "Input content safety non-critical block ignored for session=%s category=%s action=%s.",
                session_id,
                input_safety.category,
                input_safety.action,
            )
        elif input_safety.blocked_by == "topic_control" and _is_medication_info_only_query(inp.message):
            # Topic-control occasionally over-blocks benign medication clarification
            # requests ("what are my meds", "when do I take them"). Keep these
            # in-flow; preflight still blocks explicit dose/medication changes.
            logger.info(
                "Input topic-control block ignored for medication-info query session=%s category=%s.",
                session_id,
                input_safety.category,
            )
        elif input_safety.action == "redirect":
            async for event in handle_soft_redirect(
                input_safety.message_key or "topic_control_input",
                f"{input_safety.blocked_by}:{input_safety.category}",
            ):
                yield event
            return
        else:
            async for event in handle_hard_stop(
                session_id,
                patient_id,
                f"nemoguard_input:{input_safety.category or input_safety.reason}",
                input_safety.severity or "HIGH",
                input_safety.message_key or "nemoguard_input_blocked",
            ):
                yield event
            return

    history = _history.get(session_id, [])
    history.append(HumanMessage(content=inp.message))
    history, summary = _trim_history(session_id, history)

    initial_state: AgentState = {
        "messages": history,
        "session_id": session_id,
        "patient_ctx_key": f"ctx:{session_id}:{patient_id}",
        "system_prompt": system_prompt,
        "history_summary": summary,
        "image_b64": inp.image_b64,
        "modality": inp.modality,
        "clinic_yaml": clinic_yaml,
        "tool_calls": [],
        "tool_results": {},
        "draft_response": None,
        "raw_citations": [],
        "safety_result": None,
        "safety_message_key": None,
        "escalation_flag": False,
        "escalation_reason": None,
        "stop_severity": None,
        "intent_route": None,
        "safety_route": None,
        "ai_disabled": False,
    }

    final_state = await agent_graph.ainvoke(initial_state)
    safety_result = final_state.get("safety_result") or {}
    logger.info(
        "Agent turn completed state session=%s intent=%s safety_route=%s blocked_by=%s escalation=%s draft_len=%s",
        session_id,
        final_state.get("intent_route"),
        final_state.get("safety_route"),
        safety_result.get("blocked_by"),
        final_state.get("escalation_flag"),
        len((final_state.get("draft_response") or "").strip()),
    )

    if final_state.get("escalation_flag") and safety_result.get("blocked_by") == "content_safety":
        async for event in handle_hard_stop(
            session_id,
            patient_id,
            final_state.get("escalation_reason") or "content_safety",
            safety_result.get("severity", "HIGH"),
            final_state.get("safety_message_key") or "content_safety_general",
        ):
            yield event
        _history[session_id] = history
        return

    if safety_result.get("blocked_by") == "topic_control":
        if _is_medication_info_only_query(inp.message):
            logger.info(
                "Output topic-control block ignored for medication-info query session=%s category=%s.",
                session_id,
                safety_result.get("category"),
            )
        else:
            async for event in handle_soft_redirect(
                final_state.get("safety_message_key") or "topic_control_general",
                final_state.get("escalation_reason") or "topic_control",
            ):
                yield event
            _history[session_id] = history
            return

    async for event in stream_output(final_state, ctx):
        yield event

    ai_text = final_state.get("draft_response") or ""
    _history[session_id] = [*history, AIMessage(content=ai_text)]


async def stream_output(state: AgentState, ctx):
    from app.agent.nodes.output import ESCALATION_MESSAGES
    from app.citations.resolver import resolve_citations

    if state.get("escalation_flag"):
        reason = state.get("escalation_reason") or "general"
        text = ESCALATION_MESSAGES.get(_reason_to_key(reason), ESCALATION_MESSAGES["general_escalation"])["text"]
        yield {"type": "escalation", "text": text, "reason": reason, "turn_complete": True}
        return

    # The UI can render token-by-token while browser TTS consumes the coarser
    # sentence events extracted from the same final safe draft.
    draft = state.get("draft_response") or ""
    citations = resolve_citations(state.get("raw_citations", []), ctx)

    for token in draft.split():
        yield {"type": "token", "text": f"{token} "}

    sentences, remainder = extract_complete_sentences(draft)
    for sentence in sentences:
        yield {"type": "sentence", "text": sentence}
    if remainder.strip():
        yield {"type": "sentence", "text": remainder.strip()}

    yield {
        "type": "done",
        "text": draft,
        "citations": [citation.__dict__ for citation in citations],
        "turn_complete": True,
    }


def _reason_to_key(reason: str) -> str:
    lowered = reason.lower()
    mapping = {
        "pain": "pain_escalation",
        "crisis": "crisis_escalation",
        "medication": "medication_change_blocked",
        "allergy": "allergy_in_input",
        "topic": "topic_control_input",
    }
    for keyword, value in mapping.items():
        if keyword in lowered:
            return value
    return "nemoguard_input_blocked"
