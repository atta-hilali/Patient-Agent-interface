# import json
import json
# from pathlib import Path
from pathlib import Path

# from app.agent.state import AgentState
from app.agent.state import AgentState
# from app.cache import read_context_for_session
from app.cache import read_context_for_session
# from app.citations.resolver import resolve_citations
from app.citations.resolver import resolve_citations


_BASE_DIR = Path(__file__).resolve().parents[3]
_ESCALATION_PATH = _BASE_DIR / "config" / "escalation_messages.json"
if _ESCALATION_PATH.exists():
    ESCALATION_MESSAGES = json.loads(_ESCALATION_PATH.read_text(encoding="utf-8"))
else:
    ESCALATION_MESSAGES = {
        "general_escalation": {"text": "I am escalating this to your care team now."},
        "nemoguard_input_blocked": {"text": "I am escalating this to your care team now."},
    }


# async def output_node(state: AgentState) -> dict:
async def output_node(state: AgentState) -> dict:
    # if state.get("escalation_flag"):
    if state.get("escalation_flag"):
        # reason = state.get("escalation_reason", "general_escalation")
        reason = state.get("escalation_reason", "general_escalation")
        # msg_key = state.get("safety_message_key") or _reason_to_key(reason)
        msg_key = state.get("safety_message_key") or _reason_to_key(reason)
        # text = ESCALATION_MESSAGES.get(msg_key, ESCALATION_MESSAGES["general_escalation"])["text"]
        text = ESCALATION_MESSAGES.get(msg_key, ESCALATION_MESSAGES["general_escalation"])["text"]
        # return {"output_event": {"type": "escalation", "text": text, "reason": reason, "turn_complete": True}}
        return {"output_event": {"type": "escalation", "text": text, "reason": reason, "turn_complete": True}}

    # draft = state.get("draft_response", "")
    draft = state.get("draft_response", "")
    # ctx = await read_context_for_session(state["session_id"])
    ctx = await read_context_for_session(state["session_id"])
    # cites = resolve_citations(state.get("raw_citations", []), ctx) if ctx else []
    cites = resolve_citations(state.get("raw_citations", []), ctx) if ctx else []
    # return {
    return {
        # "output_event": {
        "output_event": {
            # "type": "done",
            "type": "done",
            # "text": draft,
            "text": draft,
            # "citations": [citation.__dict__ for citation in cites],
            "citations": [citation.__dict__ for citation in cites],
            # "turn_complete": True,
            "turn_complete": True,
        # }
        }
    # }
    }


# def _reason_to_key(reason: str) -> str:
def _reason_to_key(reason: str) -> str:
    # lowered = reason.lower()
    lowered = reason.lower()
    # if "pain" in lowered:
    if "pain" in lowered:
        # return "pain_escalation"
        return "pain_escalation"
    # if "crisis" in lowered:
    if "crisis" in lowered:
        # return "crisis_escalation"
        return "crisis_escalation"
    # if "medication" in lowered:
    if "medication" in lowered:
        # return "medication_change_blocked"
        return "medication_change_blocked"
    # if "allergy" in lowered:
    if "allergy" in lowered:
        # return "allergy_in_input"
        return "allergy_in_input"
    # if "topic" in lowered:
    if "topic" in lowered:
        # return "topic_control_input"
        return "topic_control_input"
    # return "nemoguard_input_blocked"
    return "nemoguard_input_blocked"
