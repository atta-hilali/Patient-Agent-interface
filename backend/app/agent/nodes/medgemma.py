# import json
import json

# from langchain_core.messages import HumanMessage
from langchain_core.messages import HumanMessage

# from app.agent.llm_client import call_medgemma
from app.agent.llm_client import call_medgemma
# from app.agent.state import AgentState
from app.agent.state import AgentState


# async def medgemma_node(state: AgentState) -> dict:
async def medgemma_node(state: AgentState) -> dict:
    # system_prompt = state["system_prompt"]
    system_prompt = state["system_prompt"]
    # if not system_prompt:
    if not system_prompt:
        # return {"escalation_flag": True, "escalation_reason": "system_prompt_missing"}
        return {"escalation_flag": True, "escalation_reason": "system_prompt_missing"}

    # history_summary = state.get("history_summary", "").strip()
    history_summary = state.get("history_summary", "").strip()
    # if history_summary:
    if history_summary:
        # system_prompt = f"{system_prompt}\n\nOlder conversation summary:\n{history_summary}"
        system_prompt = f"{system_prompt}\n\nOlder conversation summary:\n{history_summary}"

    # messages = list(state["messages"])
    messages = list(state["messages"])
    # if state.get("tool_results"):
    if state.get("tool_results"):
        # tool_text = "\n".join(f"[{name} result]\n{value}" for name, value in state["tool_results"].items())
        tool_text = "\n".join(f"[{name} result]\n{value}" for name, value in state["tool_results"].items())
        # messages.append(HumanMessage(content=f"Tool data:\n{tool_text}"))
        messages.append(HumanMessage(content=f"Tool data:\n{tool_text}"))

    # full = ""
    full = ""
    # stream = await call_medgemma(system_prompt, messages)
    stream = await call_medgemma(system_prompt, messages)
    # async for chunk in stream:
    async for chunk in stream:
        # full += chunk.choices[0].delta.content or ""
        full += chunk.choices[0].delta.content or ""

    # try:
    try:
        # parsed = json.loads(full)
        parsed = json.loads(full)
    # except json.JSONDecodeError:
    except json.JSONDecodeError:
        # return {"escalation_flag": True, "escalation_reason": "malformed_llm_output"}
        return {"escalation_flag": True, "escalation_reason": "malformed_llm_output"}

    # if parsed.get("escalation_flag", False):
    if parsed.get("escalation_flag", False):
        # return {
        return {
            # "escalation_flag": True,
            "escalation_flag": True,
            # "escalation_reason": "llm_self_escalation",
            "escalation_reason": "llm_self_escalation",
            # "stop_severity": "HIGH",
            "stop_severity": "HIGH",
        # }
        }

    # return {
    return {
        # "draft_response": parsed.get("response_text", ""),
        "draft_response": parsed.get("response_text", ""),
        # "raw_citations": parsed.get("citations", []),
        "raw_citations": parsed.get("citations", []),
    # }
    }
