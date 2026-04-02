# from app.agent.state import AgentState
from app.agent.state import AgentState
# from app.safety.checker import get_safety_checker
from app.safety.checker import get_safety_checker


# async def safety_node(state: AgentState) -> dict:
async def safety_node(state: AgentState) -> dict:
    # # Output safety is the last gate before anything is shown to the patient.
    # Output safety is the last gate before anything is shown to the patient.
    # result = await get_safety_checker().check_output(
    result = await get_safety_checker().check_output(
        # state.get("draft_response", ""),
        state.get("draft_response", ""),
        # state.get("clinic_yaml", "general_medicine"),
        state.get("clinic_yaml", "general_medicine"),
    # )
    )
    # if not result.safe and result.action == "redirect":
    if not result.safe and result.action == "redirect":
        # # Topic control discards the model draft and swaps in prewritten redirect text.
        # Topic control discards the model draft and swaps in prewritten redirect text.
        # return {
        return {
            # "draft_response": None,
            "draft_response": None,
            # "safety_result": result.__dict__,
            "safety_result": result.__dict__,
            # "safety_message_key": result.message_key,
            "safety_message_key": result.message_key,
            # "safety_route": "escalate",
            "safety_route": "escalate",
        # }
        }
    # if not result.safe:
    if not result.safe:
        # # Content safety discards the draft and routes to deterministic escalation handling.
        # Content safety discards the draft and routes to deterministic escalation handling.
        # return {
        return {
            # "escalation_flag": True,
            "escalation_flag": True,
            # "escalation_reason": f"{result.blocked_by}:{result.category}",
            "escalation_reason": f"{result.blocked_by}:{result.category}",
            # "safety_result": result.__dict__,
            "safety_result": result.__dict__,
            # "safety_message_key": result.message_key,
            "safety_message_key": result.message_key,
            # "draft_response": None,
            "draft_response": None,
            # "safety_route": "escalate",
            "safety_route": "escalate",
        # }
        }
    # return {"safety_result": result.__dict__, "safety_message_key": None, "safety_route": "safe"}
    return {"safety_result": result.__dict__, "safety_message_key": None, "safety_route": "safe"}
