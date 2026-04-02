# from __future__ import annotations
from __future__ import annotations

# from langchain_core.tools import tool
from langchain_core.tools import tool

# from app.agent.tools.schemas import EscalationToolInput, ToolTextResult, dump_tool_result
from app.agent.tools.schemas import EscalationToolInput, ToolTextResult, dump_tool_result
# from app.cache import read_patient_id_for_session
from app.cache import read_patient_id_for_session
# from app.safety.escalation import fire_webhook, write_fhir_flag
from app.safety.escalation import fire_webhook, write_fhir_flag


# @tool(args_schema=EscalationToolInput)
@tool(args_schema=EscalationToolInput)
# async def escalate_to_human(session_id: str, reason: str, patient_id: str | None = None) -> str:
async def escalate_to_human(session_id: str, reason: str, patient_id: str | None = None) -> str:
    # """Write escalation artifacts and notify the clinic webhook."""
    """Write escalation artifacts and notify the clinic webhook."""
    # resolved_patient_id = patient_id or await read_patient_id_for_session(session_id)
    resolved_patient_id = patient_id or await read_patient_id_for_session(session_id)
    # if not resolved_patient_id:
    if not resolved_patient_id:
        # return dump_tool_result(
        return dump_tool_result(
            # ToolTextResult(
            ToolTextResult(
                # tool_name="escalate_to_human",
                tool_name="escalate_to_human",
                # summary="Unable to escalate because no patient id could be resolved for this session.",
                summary="Unable to escalate because no patient id could be resolved for this session.",
            # )
            )
        # )
        )
    # await write_fhir_flag(resolved_patient_id, reason, "HIGH", session_id)
    await write_fhir_flag(resolved_patient_id, reason, "HIGH", session_id)
    # await fire_webhook(session_id, resolved_patient_id, reason)
    await fire_webhook(session_id, resolved_patient_id, reason)
    # return dump_tool_result(
    return dump_tool_result(
        # ToolTextResult(
        ToolTextResult(
            # tool_name="escalate_to_human",
            tool_name="escalate_to_human",
            # summary="Escalation complete. Your care team has been notified.",
            summary="Escalation complete. Your care team has been notified.",
            # data={"session_id": session_id, "patient_id": resolved_patient_id, "reason": reason},
            data={"session_id": session_id, "patient_id": resolved_patient_id, "reason": reason},
        # )
        )
    # )
    )
