# import json
import json

# from langchain_core.messages import HumanMessage
from langchain_core.messages import HumanMessage

# from app.agent.llm_client import call_medgemma
from app.agent.llm_client import call_medgemma
# from app.agent.state import AgentState
from app.agent.state import AgentState


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
        messages.append(HumanMessage(content=f"Tool data:\n{tool_text}"))

    full = ""
    stream = await call_medgemma(system_prompt, messages)
    async for chunk in stream:
        full += chunk.choices[0].delta.content or ""

    raw = (full or "").strip()
    if not raw:
        return {"escalation_flag": True, "escalation_reason": "empty_llm_output"}

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
